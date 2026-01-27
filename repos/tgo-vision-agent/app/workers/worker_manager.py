"""Worker manager for coordinating MessagePoller workers with Agent architecture."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from app.core.agentbay_client import AgentBayClientFactory
from app.core.config import settings
from app.core.encryption import decrypt_api_key
from app.core.llm.reasoning import ReasoningClient
from app.core.llm.vision import VisionClient
from app.db.base import SessionLocal
from app.db.models import VisionAgentSession
from app.domain.agent.agent_loop import AgentLoop
from app.domain.entities import SessionStatus
from app.services.platform_callback import PlatformCallbackService
from app.workers.message_poller import MessagePoller
from app.workers.session_keeper import SessionKeeper

logger = logging.getLogger(__name__)


class WorkerInfo:
    """Container for worker instances associated with a session."""

    def __init__(
        self,
        platform_id: UUID,
        session_id: str,
        agent: Optional[AgentLoop] = None,
        message_poller: Optional[MessagePoller] = None,
        session_keeper: Optional[SessionKeeper] = None,
    ):
        self.platform_id = platform_id
        self.session_id = session_id
        self.agent = agent
        self.message_poller = message_poller
        self.session_keeper = session_keeper


class WorkerManager:
    """Singleton manager for all worker instances.

    Manages the lifecycle of AgentLoop, MessagePoller and SessionKeeper
    for each active session.
    """

    _instance: Optional["WorkerManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "WorkerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._workers: dict[UUID, WorkerInfo] = {}
        self._platform_callback = PlatformCallbackService()
        logger.info("WorkerManager initialized")

    @classmethod
    def get_instance(cls) -> "WorkerManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start_workers_for_session(
        self,
        platform_id: UUID,
        app_type: str,
        agentbay_session_id: str,
        environment_type: str = "mobile",
        api_key: Optional[str] = None,
        vision_provider_id: Optional[str] = None,
        vision_model_id: Optional[str] = None,
        reasoning_provider_id: Optional[str] = None,
        reasoning_model_id: Optional[str] = None,
        poll_interval: int = 10,
    ) -> bool:
        """Start workers for a session.

        Args:
            platform_id: Platform ID from tgo-api
            app_type: Application type (wechat, douyin, etc.)
            agentbay_session_id: AgentBay session ID
            environment_type: Environment type (mobile/desktop)
            api_key: AgentBay API key
            vision_provider_id: Vision model provider ID
            vision_model_id: Vision model ID
            reasoning_provider_id: Reasoning model provider ID
            reasoning_model_id: Reasoning model ID
            poll_interval: Message polling interval in seconds

        Returns:
            True if workers started successfully
        """
        async with self._lock:
            # Check if workers already exist
            if platform_id in self._workers:
                logger.warning(f"Workers already exist for platform {platform_id}")
                return True

            try:
                # Validate required model configuration
                if not vision_provider_id or not vision_model_id:
                    logger.error("Vision model configuration is required")
                    return False
                if not reasoning_provider_id or not reasoning_model_id:
                    logger.error("Reasoning model configuration is required")
                    return False

                # Create AgentBay controller
                controller = AgentBayClientFactory.create_controller(
                    environment_type=environment_type,
                    api_key=api_key or settings.agentbay_api_key,
                )

                # Restore the session connection
                restored = await controller.restore_session(agentbay_session_id)
                if not restored:
                    logger.error(f"Failed to restore session {agentbay_session_id}")
                    return False

                # Create dual model clients
                reasoning_client = ReasoningClient(
                    provider_id=reasoning_provider_id,
                    model_id=reasoning_model_id,
                )
                vision_client = VisionClient(
                    provider_id=vision_provider_id,
                    model_id=vision_model_id,
                )

                # Create AgentLoop
                agent = AgentLoop(
                    reasoning=reasoning_client,
                    vision=vision_client,
                    controller=controller,
                    session_id=agentbay_session_id,
                )

                # Create message poller
                message_poller = MessagePoller(
                    platform_id=platform_id,
                    app_type=app_type,
                    agent=agent,
                    poll_interval=poll_interval,
                    message_callback=self._platform_callback,
                )

                # Create session keeper
                session_keeper = SessionKeeper(
                    platform_id=platform_id,
                    session_id=agentbay_session_id,
                    controller=controller,
                    check_interval=30,
                    on_session_lost=self._handle_session_lost,
                )

                # Start workers
                await message_poller.start()
                await session_keeper.start()

                # Store worker info
                self._workers[platform_id] = WorkerInfo(
                    platform_id=platform_id,
                    session_id=agentbay_session_id,
                    agent=agent,
                    message_poller=message_poller,
                    session_keeper=session_keeper,
                )

                logger.info(f"Started workers for platform {platform_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to start workers for platform {platform_id}: {e}")
                return False

    async def stop_workers_for_session(self, platform_id: UUID) -> bool:
        """Stop workers for a session."""
        async with self._lock:
            worker_info = self._workers.get(platform_id)
            if not worker_info:
                logger.warning(f"No workers found for platform {platform_id}")
                return True

            try:
                if worker_info.message_poller:
                    await worker_info.message_poller.stop()

                if worker_info.session_keeper:
                    await worker_info.session_keeper.stop()

                del self._workers[platform_id]

                logger.info(f"Stopped workers for platform {platform_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to stop workers for platform {platform_id}: {e}")
                return False

    async def restore_active_sessions(self) -> int:
        """Restore workers for all active sessions from database."""
        restored_count = 0

        try:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(VisionAgentSession).where(
                        VisionAgentSession.status == SessionStatus.ACTIVE.value
                    )
                )
                sessions = list(result.scalars().all())

                logger.info(f"Found {len(sessions)} active sessions to restore")

                for session in sessions:
                    try:
                        config = session.config or {}
                        encrypted_key = config.get("agentbay_api_key")
                        api_key = decrypt_api_key(encrypted_key) if encrypted_key else None

                        success = await self.start_workers_for_session(
                            platform_id=session.platform_id,
                            app_type=session.app_type,
                            agentbay_session_id=session.agentbay_session_id,
                            environment_type=session.environment_type,
                            api_key=api_key,
                            vision_provider_id=config.get("vision_provider_id"),
                            vision_model_id=config.get("vision_model_id"),
                            reasoning_provider_id=config.get("reasoning_provider_id"),
                            reasoning_model_id=config.get("reasoning_model_id"),
                            poll_interval=settings.default_poll_interval_seconds,
                        )

                        if success:
                            restored_count += 1
                            logger.info(
                                f"Restored workers for session {session.id}"
                            )

                    except Exception as e:
                        logger.error(f"Error restoring session {session.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to restore active sessions: {e}")

        logger.info(f"Restored {restored_count} session workers")
        return restored_count

    async def shutdown(self) -> None:
        """Shutdown all workers gracefully."""
        logger.info("Shutting down all workers...")
        platform_ids = list(self._workers.keys())
        for platform_id in platform_ids:
            await self.stop_workers_for_session(platform_id)
        logger.info("All workers shut down")

    def get_worker_status(self, platform_id: UUID) -> Optional[dict]:
        """Get status of workers for a platform."""
        worker_info = self._workers.get(platform_id)
        if not worker_info:
            return None

        return {
            "platform_id": str(platform_id),
            "session_id": worker_info.session_id,
            "message_poller_running": (
                worker_info.message_poller._running
                if worker_info.message_poller
                else False
            ),
            "session_keeper_running": (
                worker_info.session_keeper._running
                if worker_info.session_keeper
                else False
            ),
        }

    def get_agent(self, platform_id: UUID) -> Optional[AgentLoop]:
        """Get the AgentLoop for a platform."""
        worker_info = self._workers.get(platform_id)
        return worker_info.agent if worker_info else None

    def list_active_workers(self) -> list[dict]:
        """List all active workers."""
        return [
            self.get_worker_status(platform_id)
            for platform_id in self._workers.keys()
        ]

    async def _handle_session_lost(
        self, platform_id: UUID, session_id: str
    ) -> None:
        """Handle session lost callback."""
        logger.warning(f"Session lost for platform {platform_id}: {session_id}")

        await self.stop_workers_for_session(platform_id)

        try:
            async with SessionLocal() as db:
                result = await db.execute(
                    select(VisionAgentSession).where(
                        VisionAgentSession.platform_id == platform_id
                    )
                )
                session = result.scalar_one_or_none()
                if session:
                    session.status = SessionStatus.TERMINATED.value
                    await db.commit()
        except Exception as e:
            logger.error(f"Failed to update session status: {e}")


def get_worker_manager() -> WorkerManager:
    """Get the global WorkerManager instance."""
    return WorkerManager.get_instance()
