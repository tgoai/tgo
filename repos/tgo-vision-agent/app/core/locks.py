"""Distributed lock mechanism for concurrent operation control."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class SessionLock:
    """In-memory lock for session operations.

    Ensures only one operation can be performed on a session at a time.
    For single-instance deployments, this provides adequate protection.
    For multi-instance deployments, use Redis-based locks.
    """

    _instance: Optional["SessionLock"] = None
    _locks: dict[str, asyncio.Lock]
    _lock_times: dict[str, float]

    def __new__(cls) -> "SessionLock":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._locks = {}
            cls._instance._lock_times = {}
        return cls._instance

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """Get or create a lock for a session."""
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    @asynccontextmanager
    async def acquire(
        self,
        session_id: str,
        timeout: float = 30.0,
    ) -> AsyncGenerator[bool, None]:
        """Acquire a lock for a session.

        Args:
            session_id: Session ID to lock
            timeout: Maximum time to wait for lock (seconds)

        Yields:
            True if lock acquired, False if timeout

        Usage:
            async with session_lock.acquire(session_id) as acquired:
                if acquired:
                    # Do work
                else:
                    # Handle timeout
        """
        lock = self._get_lock(session_id)
        acquired = False

        try:
            # Try to acquire with timeout
            acquired = await asyncio.wait_for(
                lock.acquire(),
                timeout=timeout,
            )
            if acquired:
                self._lock_times[session_id] = time.time()
                logger.debug(f"Lock acquired for session {session_id}")
            yield acquired
        except asyncio.TimeoutError:
            logger.warning(f"Lock timeout for session {session_id}")
            yield False
        finally:
            if acquired and lock.locked():
                lock.release()
                if session_id in self._lock_times:
                    held_time = time.time() - self._lock_times[session_id]
                    logger.debug(
                        f"Lock released for session {session_id} "
                        f"(held for {held_time:.2f}s)"
                    )
                    del self._lock_times[session_id]

    def is_locked(self, session_id: str) -> bool:
        """Check if a session is currently locked."""
        if session_id not in self._locks:
            return False
        return self._locks[session_id].locked()

    def cleanup_session(self, session_id: str) -> None:
        """Clean up lock for a deleted session."""
        if session_id in self._locks:
            del self._locks[session_id]
        if session_id in self._lock_times:
            del self._lock_times[session_id]


class PlatformLock:
    """Lock for platform-level operations.

    Wraps SessionLock but uses platform_id as the key.
    """

    def __init__(self) -> None:
        self._session_lock = SessionLock()

    @asynccontextmanager
    async def acquire(
        self,
        platform_id: UUID,
        timeout: float = 30.0,
    ) -> AsyncGenerator[bool, None]:
        """Acquire a lock for a platform.

        Args:
            platform_id: Platform ID to lock
            timeout: Maximum time to wait for lock (seconds)

        Yields:
            True if lock acquired, False if timeout
        """
        lock_key = f"platform:{platform_id}"
        async with self._session_lock.acquire(lock_key, timeout) as acquired:
            yield acquired

    def is_locked(self, platform_id: UUID) -> bool:
        """Check if a platform is currently locked."""
        lock_key = f"platform:{platform_id}"
        return self._session_lock.is_locked(lock_key)


# Global lock instances
_session_lock: Optional[SessionLock] = None
_platform_lock: Optional[PlatformLock] = None


def get_session_lock() -> SessionLock:
    """Get the global session lock instance."""
    global _session_lock
    if _session_lock is None:
        _session_lock = SessionLock()
    return _session_lock


def get_platform_lock() -> PlatformLock:
    """Get the global platform lock instance."""
    global _platform_lock
    if _platform_lock is None:
        _platform_lock = PlatformLock()
    return _platform_lock
