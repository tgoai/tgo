"""Tests for lock utilities."""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.locks import SessionLock, PlatformLock, get_session_lock, get_platform_lock


class TestSessionLock:
    """Tests for SessionLock class."""

    @pytest.mark.asyncio
    async def test_acquire_lock(self):
        """Test acquiring a lock."""
        lock = SessionLock()
        session_id = "test-session-1"

        async with lock.acquire(session_id) as acquired:
            assert acquired is True
            assert lock.is_locked(session_id) is True

        assert lock.is_locked(session_id) is False

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_access(self):
        """Test that lock prevents concurrent access."""
        lock = SessionLock()
        session_id = "test-session-2"
        results = []

        async def task(task_id: int):
            async with lock.acquire(session_id, timeout=5.0) as acquired:
                if acquired:
                    results.append(f"start-{task_id}")
                    await asyncio.sleep(0.1)
                    results.append(f"end-{task_id}")

        # Run two tasks concurrently
        await asyncio.gather(task(1), task(2))

        # Tasks should have run sequentially
        assert len(results) == 4
        # First task should complete before second starts
        assert results[0].startswith("start")
        assert results[1].startswith("end")

    @pytest.mark.asyncio
    async def test_lock_timeout(self):
        """Test lock acquisition timeout."""
        lock = SessionLock()
        session_id = "test-session-3"

        # Acquire lock in one task
        async def holder():
            async with lock.acquire(session_id) as acquired:
                assert acquired
                await asyncio.sleep(1.0)

        # Try to acquire with short timeout
        async def waiter():
            await asyncio.sleep(0.1)  # Let holder acquire first
            async with lock.acquire(session_id, timeout=0.1) as acquired:
                return acquired

        holder_task = asyncio.create_task(holder())
        result = await waiter()

        assert result is False
        holder_task.cancel()
        try:
            await holder_task
        except asyncio.CancelledError:
            pass

    def test_is_locked_returns_false_for_unknown_session(self):
        """Test is_locked returns False for unknown session."""
        lock = SessionLock()
        assert lock.is_locked("unknown-session") is False

    @pytest.mark.asyncio
    async def test_cleanup_session(self):
        """Test session cleanup removes lock."""
        lock = SessionLock()
        session_id = "test-session-4"

        async with lock.acquire(session_id):
            pass

        lock.cleanup_session(session_id)
        # Should not raise after cleanup


class TestPlatformLock:
    """Tests for PlatformLock class."""

    @pytest.mark.asyncio
    async def test_acquire_platform_lock(self):
        """Test acquiring a platform lock."""
        lock = PlatformLock()
        platform_id = uuid4()

        async with lock.acquire(platform_id) as acquired:
            assert acquired is True
            assert lock.is_locked(platform_id) is True

        assert lock.is_locked(platform_id) is False


class TestGlobalLocks:
    """Tests for global lock getters."""

    def test_get_session_lock_returns_singleton(self):
        """Test get_session_lock returns same instance."""
        lock1 = get_session_lock()
        lock2 = get_session_lock()
        assert lock1 is lock2

    def test_get_platform_lock_returns_singleton(self):
        """Test get_platform_lock returns same instance."""
        lock1 = get_platform_lock()
        lock2 = get_platform_lock()
        assert lock1 is lock2
