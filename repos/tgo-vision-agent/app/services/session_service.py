"""Session management service for AgentBay sessions with dual-model support."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agentbay_client import AgentBayClientFactory
from app.core.encryption import encrypt_api_key, decrypt_api_key
from app.db.models import VisionAgentSession
from app.domain.entities import AppLoginStatus, SessionStatus

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing AgentBay sessions with dual-model configuration."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        platform_id: uuid.UUID,
        app_type: str,
        environment_type: str = "mobile",
        image_id: Optional[str] = None,
        agentbay_api_key: Optional[str] = None,
        vision_provider_id: Optional[str] = None,
        vision_model_id: Optional[str] = None,
        reasoning_provider_id: Optional[str] = None,
        reasoning_model_id: Optional[str] = None,
    ) -> VisionAgentSession:
        """Create a new AgentBay session with dual-model configuration.

        Args:
            platform_id: Platform ID from tgo-api
            app_type: Application type (wechat, douyin, etc.)
            environment_type: Environment type (mobile or desktop)
            image_id: Optional AgentBay image ID
            agentbay_api_key: Optional API key
            vision_provider_id: Vision model provider ID (required)
            vision_model_id: Vision model ID (required)
            reasoning_provider_id: Reasoning model provider ID (required)
            reasoning_model_id: Reasoning model ID (required)

        Returns:
            Created VisionAgentSession
        """
        # Validate required model configuration
        if not vision_provider_id or not vision_model_id:
            raise ValueError("Vision model configuration (vision_provider_id and vision_model_id) is required")
        if not reasoning_provider_id or not reasoning_model_id:
            raise ValueError("Reasoning model configuration (reasoning_provider_id and reasoning_model_id) is required")

        # Check if session already exists - delete for idempotency
        existing = await self.get_session_by_platform(platform_id)
        if existing:
            logger.info(f"Session already exists for platform {platform_id}, replacing")
            await self.delete_session(existing.id)

        # Create AgentBay session
        controller = AgentBayClientFactory.create_controller(
            environment_type=environment_type,
            api_key=agentbay_api_key or "",
        )

        try:
            agentbay_session_id = await controller.create_session(
                environment_type=environment_type,
                image_id=image_id,
            )
        except ValueError as e:
            logger.error(f"Failed to create AgentBay session: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create AgentBay session: {e}")
            raise ValueError(f"创建 AgentBay 会话失败: {e}") from e

        # Build session configuration
        config = {
            "vision_provider_id": vision_provider_id,
            "vision_model_id": vision_model_id,
            "reasoning_provider_id": reasoning_provider_id,
            "reasoning_model_id": reasoning_model_id,
        }
        if agentbay_api_key:
            config["agentbay_api_key"] = encrypt_api_key(agentbay_api_key)

        # Create database record
        session = VisionAgentSession(
            id=uuid.uuid4(),
            platform_id=platform_id,
            app_type=app_type,
            agentbay_session_id=agentbay_session_id,
            environment_type=environment_type,
            status=SessionStatus.ACTIVE.value,
            app_login_status=AppLoginStatus.OFFLINE.value,
            config=config,
            last_heartbeat=datetime.utcnow(),
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(
            f"Created session {session.id} for platform {platform_id} "
            f"(AgentBay: {agentbay_session_id}, Vision: {vision_model_id}, Reasoning: {reasoning_model_id})"
        )

        return session

    async def get_session(self, session_id: uuid.UUID) -> Optional[VisionAgentSession]:
        """Get a session by ID."""
        result = await self.db.execute(
            select(VisionAgentSession).where(VisionAgentSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_session_by_platform(
        self, platform_id: uuid.UUID
    ) -> Optional[VisionAgentSession]:
        """Get a session by platform ID."""
        result = await self.db.execute(
            select(VisionAgentSession).where(
                VisionAgentSession.platform_id == platform_id
            )
        )
        return result.scalar_one_or_none()

    async def update_session_status(
        self,
        session_id: uuid.UUID,
        status: Optional[str] = None,
        app_login_status: Optional[str] = None,
    ) -> Optional[VisionAgentSession]:
        """Update session status fields."""
        updates = {}
        if status:
            updates["status"] = status
        if app_login_status:
            updates["app_login_status"] = app_login_status
        updates["last_heartbeat"] = datetime.utcnow()

        if not updates:
            return await self.get_session(session_id)

        await self.db.execute(
            update(VisionAgentSession)
            .where(VisionAgentSession.id == session_id)
            .values(**updates)
        )
        await self.db.commit()

        return await self.get_session(session_id)

    async def delete_session(self, session_id: uuid.UUID) -> bool:
        """Delete/terminate a session."""
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return False

        # Terminate AgentBay session
        try:
            encrypted_key = (session.config or {}).get("agentbay_api_key")
            api_key = decrypt_api_key(encrypted_key) if encrypted_key else ""
            controller = AgentBayClientFactory.create_controller(
                environment_type=session.environment_type,
                api_key=api_key,
            )
            await controller.delete_session(session.agentbay_session_id)
        except Exception as e:
            logger.warning(f"Failed to terminate AgentBay session: {e}")

        # Delete from database
        await self.db.delete(session)
        await self.db.commit()

        logger.info(f"Deleted session {session_id}")
        return True

    async def list_active_sessions(self) -> list[VisionAgentSession]:
        """List all active sessions."""
        result = await self.db.execute(
            select(VisionAgentSession).where(
                VisionAgentSession.status == SessionStatus.ACTIVE.value
            )
        )
        return list(result.scalars().all())
