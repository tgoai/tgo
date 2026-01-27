"""Session keeper worker for maintaining session health."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from app.domain.ports import AgentBayController

logger = logging.getLogger(__name__)


class SessionKeeper:
    """Worker that keeps AgentBay sessions alive and monitors their health.

    Responsibilities:
    - Periodically send heartbeat to keep session active
    - Monitor session health status
    - Detect disconnections and notify for reconnection
    - Track login status changes
    """

    def __init__(
        self,
        platform_id: UUID,
        session_id: str,
        controller: AgentBayController,
        check_interval: int = 30,
        on_session_lost: Optional[Callable[[UUID, str], None]] = None,
        on_login_status_change: Optional[Callable[[UUID, str, str], None]] = None,
    ):
        """Initialize the session keeper.

        Args:
            platform_id: Platform ID from tgo-api
            session_id: AgentBay session ID
            controller: AgentBay controller instance
            check_interval: Health check interval in seconds
            on_session_lost: Callback when session is lost
            on_login_status_change: Callback when login status changes
        """
        self.platform_id = platform_id
        self.session_id = session_id
        self.controller = controller
        self.check_interval = check_interval
        self.on_session_lost = on_session_lost
        self.on_login_status_change = on_login_status_change

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_heartbeat: Optional[datetime] = None
        self._consecutive_failures = 0
        self._max_failures = 3

    @property
    def last_heartbeat(self) -> Optional[datetime]:
        """Get the last successful heartbeat time."""
        return self._last_heartbeat

    @property
    def is_healthy(self) -> bool:
        """Check if the session is considered healthy."""
        return self._consecutive_failures < self._max_failures

    async def start(self) -> None:
        """Start the session keeper loop."""
        if self._running:
            logger.warning(f"Session keeper already running for {self.platform_id}")
            return

        self._running = True
        self._consecutive_failures = 0
        self._task = asyncio.create_task(self._keep_alive_loop())
        logger.info(
            f"Started session keeper for platform {self.platform_id}, "
            f"session {self.session_id}, interval {self.check_interval}s"
        )

    async def stop(self) -> None:
        """Stop the session keeper loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(f"Stopped session keeper for platform {self.platform_id}")

    async def _keep_alive_loop(self) -> None:
        """Main keep-alive loop."""
        while self._running:
            try:
                await self._check_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in keep-alive loop: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def _check_health(self) -> None:
        """Perform a health check on the session."""
        try:
            # Try to take a screenshot as a health check
            await self.controller.take_screenshot(self.session_id)

            # Success - reset failure count and update heartbeat
            self._consecutive_failures = 0
            self._last_heartbeat = datetime.now(timezone.utc)
            logger.debug(
                f"Session {self.session_id} health check passed at "
                f"{self._last_heartbeat.isoformat()}"
            )

        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(
                f"Session {self.session_id} health check failed "
                f"({self._consecutive_failures}/{self._max_failures}): {e}"
            )

            # Check if we've exceeded max failures
            if self._consecutive_failures >= self._max_failures:
                logger.error(
                    f"Session {self.session_id} considered lost after "
                    f"{self._consecutive_failures} consecutive failures"
                )
                if self.on_session_lost:
                    try:
                        await self._notify_session_lost()
                    except Exception as notify_error:
                        logger.error(f"Failed to notify session lost: {notify_error}")

    async def _notify_session_lost(self) -> None:
        """Notify that the session has been lost."""
        if self.on_session_lost:
            # Handle both sync and async callbacks
            if asyncio.iscoroutinefunction(self.on_session_lost):
                await self.on_session_lost(self.platform_id, self.session_id)
            else:
                self.on_session_lost(self.platform_id, self.session_id)

    async def force_health_check(self) -> bool:
        """Force an immediate health check.

        Returns:
            True if the session is healthy
        """
        try:
            await self.controller.take_screenshot(self.session_id)
            self._consecutive_failures = 0
            self._last_heartbeat = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.warning(f"Forced health check failed: {e}")
            self._consecutive_failures += 1
            return False
