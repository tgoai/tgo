"""Message handling service for sending and receiving messages."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import VisionAgentInbox, VisionAgentSession, MessageFingerprint
from app.domain.entities import Contact, MessageDirection
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


class MessageService:
    """Service for handling message send/receive operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_service = SessionService(db)

    async def send_message(
        self,
        platform_id: uuid.UUID,
        app_type: str,
        contact_id: str,
        content: str,
        message_type: str = "text",
    ) -> dict:
        """Send a message to a contact via UI automation.

        Args:
            platform_id: Platform ID from tgo-api
            app_type: Application type (wechat, douyin, etc.)
            contact_id: Contact identifier within the app
            content: Message content to send
            message_type: Type of message (text, image, etc.)

        Returns:
            Result dict with success status and message_id

        Raises:
            ValueError: If no active session exists for the platform
        """
        from app.core.locks import get_platform_lock

        # Get session for this platform
        session = await self.session_service.get_session_by_platform(platform_id)
        if not session:
            raise ValueError(f"No session found for platform {platform_id}")

        if session.status != "active":
            raise ValueError(f"Session is not active: {session.status}")

        if session.app_login_status != "logged_in":
            raise ValueError(f"App not logged in: {session.app_login_status}")

        # Create outbound inbox record first
        inbox_record = VisionAgentInbox(
            id=uuid.uuid4(),
            platform_id=platform_id,
            app_type=app_type,
            contact_id=contact_id,
            contact_name=contact_id,  # Will be updated if we can get the name
            message_content=content,
            message_type=message_type,
            direction=MessageDirection.OUTBOUND.value,
            status="processing",
        )
        self.db.add(inbox_record)
        await self.db.commit()

        # Acquire platform lock to prevent concurrent UI operations
        platform_lock = get_platform_lock()
        async with platform_lock.acquire(platform_id, timeout=60.0) as acquired:
            if not acquired:
                inbox_record.status = "failed"
                inbox_record.error_message = "Could not acquire platform lock (timeout)"
                await self.db.commit()
                return {
                    "success": False,
                    "error": "Platform is busy, please try again later",
                }

            try:
                from app.workers.worker_manager import get_worker_manager
                from app.domain.base.app_automator import AppAutomatorFactory

                # Get AgentLoop from WorkerManager
                worker_manager = get_worker_manager()
                agent = worker_manager.get_agent(platform_id)
                if not agent:
                    raise RuntimeError(f"No active agent found for platform {platform_id}. Please start the session first.")

                # Create automator
                automator = AppAutomatorFactory.create(
                    app_type=app_type,
                    agent=agent,
                    session_id=session.agentbay_session_id,
                )

                # Send the message via AgentLoop
                result = await automator.send_message(contact_id, content)

                if result.success:
                    inbox_record.status = "completed"
                    inbox_record.processed_at = datetime.utcnow()
                    await self.db.commit()

                    logger.info(
                        f"Message sent to {contact_id} on platform {platform_id}"
                    )
                    return {
                        "success": True,
                        "message_id": str(inbox_record.id),
                    }
                else:
                    inbox_record.status = "failed"
                    inbox_record.error_message = result.message
                    await self.db.commit()
                    return {
                        "success": False,
                        "error": f"Failed to send message: {result.message}",
                    }

            except Exception as e:
                logger.error(f"Failed to send message: {e}")
                inbox_record.status = "failed"
                inbox_record.error_message = str(e)
                inbox_record.retry_count += 1
                await self.db.commit()
                raise

    async def store_inbound_message(
        self,
        platform_id: uuid.UUID,
        app_type: str,
        contact_id: str,
        contact_name: str,
        content: str,
        message_type: str = "text",
        screenshot_path: Optional[str] = None,
    ) -> Optional[VisionAgentInbox]:
        """Store an inbound message in the inbox.

        Performs deduplication to avoid storing the same message twice.

        Args:
            platform_id: Platform ID
            app_type: Application type
            contact_id: Contact identifier
            contact_name: Contact display name
            content: Message content
            message_type: Type of message
            screenshot_path: Optional path to screenshot

        Returns:
            Created inbox record, or None if duplicate
        """
        # Check for duplicate using fingerprint
        fingerprint = self._compute_fingerprint(platform_id, contact_id, content)
        
        existing = await self.db.execute(
            select(MessageFingerprint).where(
                and_(
                    MessageFingerprint.platform_id == platform_id,
                    MessageFingerprint.fingerprint == fingerprint,
                    MessageFingerprint.expires_at > datetime.utcnow(),
                )
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(f"Duplicate message detected for {contact_id}")
            return None

        # Store fingerprint for deduplication
        fp = MessageFingerprint(
            id=uuid.uuid4(),
            platform_id=platform_id,
            fingerprint=fingerprint,
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        self.db.add(fp)

        # Create inbox record
        inbox_record = VisionAgentInbox(
            id=uuid.uuid4(),
            platform_id=platform_id,
            app_type=app_type,
            contact_id=contact_id,
            contact_name=contact_name,
            message_content=content,
            message_type=message_type,
            direction=MessageDirection.INBOUND.value,
            status="pending",
            screenshot_path=screenshot_path,
        )
        self.db.add(inbox_record)
        await self.db.commit()
        await self.db.refresh(inbox_record)

        logger.info(
            f"Stored inbound message from {contact_name} ({contact_id}) "
            f"on platform {platform_id}"
        )
        return inbox_record

    def _compute_fingerprint(
        self,
        platform_id: uuid.UUID,
        contact_id: str,
        content: str,
    ) -> str:
        """Compute a fingerprint for deduplication.

        Uses a hash of platform_id + contact_id + content.
        Time is not included to allow for similar messages at different times.
        """
        data = f"{platform_id}:{contact_id}:{content}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def list_messages(
        self,
        platform_id: uuid.UUID,
        app_type: Optional[str] = None,
        contact_id: Optional[str] = None,
        direction: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VisionAgentInbox], int]:
        """List messages from the inbox.

        Args:
            platform_id: Platform ID to filter by
            app_type: Optional app type filter
            contact_id: Optional contact ID filter
            direction: Optional direction filter (inbound/outbound)
            status: Optional status filter
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            Tuple of (messages, total_count)
        """
        query = select(VisionAgentInbox).where(
            VisionAgentInbox.platform_id == platform_id
        )

        if app_type:
            query = query.where(VisionAgentInbox.app_type == app_type)
        if contact_id:
            query = query.where(VisionAgentInbox.contact_id == contact_id)
        if direction:
            query = query.where(VisionAgentInbox.direction == direction)
        if status:
            query = query.where(VisionAgentInbox.status == status)

        # Build count query with same filters
        count_query = select(func.count(VisionAgentInbox.id)).where(
            VisionAgentInbox.platform_id == platform_id
        )
        if app_type:
            count_query = count_query.where(VisionAgentInbox.app_type == app_type)
        if contact_id:
            count_query = count_query.where(VisionAgentInbox.contact_id == contact_id)
        if direction:
            count_query = count_query.where(VisionAgentInbox.direction == direction)
        if status:
            count_query = count_query.where(VisionAgentInbox.status == status)

        # Get total count efficiently
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(VisionAgentInbox.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        return messages, total

    async def get_message(self, message_id: uuid.UUID) -> Optional[VisionAgentInbox]:
        """Get a specific message by ID."""
        result = await self.db.execute(
            select(VisionAgentInbox).where(VisionAgentInbox.id == message_id)
        )
        return result.scalar_one_or_none()

    async def update_message_status(
        self,
        message_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[VisionAgentInbox]:
        """Update message status."""
        message = await self.get_message(message_id)
        if not message:
            return None

        message.status = status
        if error_message:
            message.error_message = error_message
        if status == "completed":
            message.processed_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_pending_messages_count(
        self,
        platform_id: uuid.UUID,
    ) -> int:
        """Get count of pending messages for a platform."""
        result = await self.db.execute(
            select(func.count(VisionAgentInbox.id)).where(
                and_(
                    VisionAgentInbox.platform_id == platform_id,
                    VisionAgentInbox.status == "pending",
                )
            )
        )
        return result.scalar() or 0
