"""Registry for mapping client_msg_no to AI run metadata.

This is used to support cancelling running AI supervisor runs by client_msg_no.
- ai_processor records the mapping when the stream emits agent_execution_started (run_id available)
- HTTP endpoint can request cancellation by client_msg_no; if run_id not known yet, we mark pending
- When run_id arrives and pending is set, ai_processor will immediately invoke cancel

If REDIS_URL is configured, uses Redis as shared storage (required for multi-process deployments).
Otherwise falls back to in-memory storage (single-process only).
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("run_registry")

DEFAULT_TTL_SECONDS = 15 * 60  # 15 minutes
REDIS_KEY_PREFIX = "tgo:run_registry:"


@dataclass
class RunEntry:
    client_msg_no: str
    project_id: Optional[str]
    api_key: Optional[str]
    session_id: Optional[str]
    run_id: Optional[str] = None
    pending_cancel: bool = False
    cancel_reason: Optional[str] = None
    ts: float = 0.0  # last update timestamp

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunEntry":
        return cls(
            client_msg_no=data.get("client_msg_no", ""),
            project_id=data.get("project_id"),
            api_key=data.get("api_key"),
            session_id=data.get("session_id"),
            run_id=data.get("run_id"),
            pending_cancel=data.get("pending_cancel", False),
            cancel_reason=data.get("cancel_reason"),
            ts=data.get("ts", 0.0),
        )


class InMemoryRunRegistry:
    """In-memory registry (single-process only)."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._by_client: Dict[str, RunEntry] = {}
        self._lock = asyncio.Lock()

    async def _prune_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._by_client.items() if now - (v.ts or 0.0) > self._ttl]
        for k in expired:
            self._by_client.pop(k, None)

    async def get(self, client_msg_no: str) -> Optional[RunEntry]:
        async with self._lock:
            await self._prune_locked()
            return self._by_client.get(client_msg_no)

    async def clear(self, client_msg_no: str) -> None:
        async with self._lock:
            self._by_client.pop(client_msg_no, None)

    async def mark_cancel_pending(
        self,
        client_msg_no: str,
        *,
        reason: Optional[str],
        project_id: Optional[str],
        api_key: Optional[str],
    ) -> None:
        async with self._lock:
            await self._prune_locked()
            entry = self._by_client.get(client_msg_no)
            now = time.time()
            if entry is None:
                entry = RunEntry(
                    client_msg_no=client_msg_no,
                    project_id=project_id,
                    api_key=api_key,
                    session_id=None,
                    run_id=None,
                    pending_cancel=True,
                    cancel_reason=reason,
                    ts=now,
                )
                self._by_client[client_msg_no] = entry
            else:
                entry.pending_cancel = True
                entry.cancel_reason = reason
                if project_id:
                    entry.project_id = entry.project_id or project_id
                if api_key:
                    entry.api_key = entry.api_key or api_key
                entry.ts = now

    async def set_mapping_and_check_pending(
        self,
        *,
        client_msg_no: str,
        run_id: str,
        project_id: Optional[str],
        api_key: Optional[str],
        session_id: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        async with self._lock:
            await self._prune_locked()
            now = time.time()
            entry = self._by_client.get(client_msg_no)
            if entry is None:
                entry = RunEntry(
                    client_msg_no=client_msg_no,
                    project_id=project_id,
                    api_key=api_key,
                    session_id=session_id,
                    run_id=run_id,
                    pending_cancel=False,
                    cancel_reason=None,
                    ts=now,
                )
                self._by_client[client_msg_no] = entry
                return (False, None)

            entry.run_id = run_id
            entry.session_id = session_id or entry.session_id
            entry.project_id = entry.project_id or project_id
            entry.api_key = entry.api_key or api_key
            entry.ts = now
            if entry.pending_cancel:
                reason = entry.cancel_reason
                entry.pending_cancel = False
                return (True, reason)
            return (False, None)


class RedisRunRegistry:
    """Redis-backed registry for multi-process deployments."""

    def __init__(self, redis_url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._redis_url = redis_url
        self._redis: Any = None
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> Any:
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info("Redis connection established for run_registry")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        return self._redis

    def _key(self, client_msg_no: str) -> str:
        return f"{REDIS_KEY_PREFIX}{client_msg_no}"

    async def get(self, client_msg_no: str) -> Optional[RunEntry]:
        try:
            redis = await self._get_redis()
            data = await redis.get(self._key(client_msg_no))
            if data:
                return RunEntry.from_dict(json.loads(data))
            return None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    async def clear(self, client_msg_no: str) -> None:
        try:
            redis = await self._get_redis()
            await redis.delete(self._key(client_msg_no))
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")

    async def _save_entry(self, entry: RunEntry) -> None:
        redis = await self._get_redis()
        await redis.setex(
            self._key(entry.client_msg_no),
            self._ttl,
            json.dumps(entry.to_dict()),
        )

    async def mark_cancel_pending(
        self,
        client_msg_no: str,
        *,
        reason: Optional[str],
        project_id: Optional[str],
        api_key: Optional[str],
    ) -> None:
        try:
            async with self._lock:
                entry = await self.get(client_msg_no)
                now = time.time()
                if entry is None:
                    entry = RunEntry(
                        client_msg_no=client_msg_no,
                        project_id=project_id,
                        api_key=api_key,
                        session_id=None,
                        run_id=None,
                        pending_cancel=True,
                        cancel_reason=reason,
                        ts=now,
                    )
                else:
                    entry.pending_cancel = True
                    entry.cancel_reason = reason
                    if project_id:
                        entry.project_id = entry.project_id or project_id
                    if api_key:
                        entry.api_key = entry.api_key or api_key
                    entry.ts = now
                await self._save_entry(entry)
                logger.debug(
                    "Marked cancel pending in Redis",
                    extra={"client_msg_no": client_msg_no, "reason": reason},
                )
        except Exception as e:
            logger.error(f"Redis mark_cancel_pending failed: {e}")
            raise

    async def set_mapping_and_check_pending(
        self,
        *,
        client_msg_no: str,
        run_id: str,
        project_id: Optional[str],
        api_key: Optional[str],
        session_id: Optional[str],
    ) -> Tuple[bool, Optional[str]]:
        try:
            async with self._lock:
                entry = await self.get(client_msg_no)
                now = time.time()
                if entry is None:
                    entry = RunEntry(
                        client_msg_no=client_msg_no,
                        project_id=project_id,
                        api_key=api_key,
                        session_id=session_id,
                        run_id=run_id,
                        pending_cancel=False,
                        cancel_reason=None,
                        ts=now,
                    )
                    await self._save_entry(entry)
                    return (False, None)

                entry.run_id = run_id
                entry.session_id = session_id or entry.session_id
                entry.project_id = entry.project_id or project_id
                entry.api_key = entry.api_key or api_key
                entry.ts = now

                if entry.pending_cancel:
                    reason = entry.cancel_reason
                    entry.pending_cancel = False
                    await self._save_entry(entry)
                    logger.info(
                        "Found pending cancel in Redis, will execute",
                        extra={"client_msg_no": client_msg_no, "run_id": run_id},
                    )
                    return (True, reason)

                await self._save_entry(entry)
                return (False, None)
        except Exception as e:
            logger.error(f"Redis set_mapping_and_check_pending failed: {e}")
            return (False, None)


def _create_registry() -> InMemoryRunRegistry | RedisRunRegistry:
    """Create the appropriate registry based on configuration."""
    redis_url = settings.REDIS_URL
    if redis_url:
        logger.info("Using Redis-backed run_registry", extra={"redis_url": redis_url[:20] + "..."})
        return RedisRunRegistry(redis_url)
    else:
        logger.warning(
            "REDIS_URL not configured, using in-memory run_registry. "
            "Cancel requests will NOT work across processes!"
        )
        return InMemoryRunRegistry()


# Global instance - will use Redis if configured, otherwise in-memory
run_registry = _create_registry()
