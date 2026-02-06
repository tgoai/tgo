"""Device Service - Database operations for devices."""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple, List

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.device import Device, DeviceSession, DeviceStatus, DeviceType
from app.schemas.device import DeviceResponse, DeviceUpdateRequest
from app.services.bind_code_service import bind_code_service

logger = get_logger("services.device_service")


class DeviceService:
    """Service for device database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_devices(
        self,
        project_id: uuid.UUID,
        device_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[DeviceResponse], int]:
        """List devices for a project."""
        # Build query
        conditions = [Device.project_id == project_id]

        if device_type:
            conditions.append(Device.device_type == device_type)
        if status:
            conditions.append(Device.status == status)

        # Count total
        count_query = select(func.count(Device.id)).where(and_(*conditions))
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get devices
        query = (
            select(Device)
            .where(and_(*conditions))
            .order_by(Device.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        devices = result.scalars().all()

        return [DeviceResponse.model_validate(d) for d in devices], total

    async def get_device(
        self,
        device_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Optional[DeviceResponse]:
        """Get a device by ID."""
        query = select(Device).where(
            and_(Device.id == device_id, Device.project_id == project_id)
        )
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()

        if device:
            return DeviceResponse.model_validate(device)
        return None

    async def generate_bind_code(
        self,
        project_id: uuid.UUID,
    ) -> Tuple[str, datetime]:
        """Generate a new bind code using Redis."""
        return await bind_code_service.generate(project_id)

    async def register_device(
        self,
        bind_code: str,
        device_name: str,
        device_type: str,
        os: str,
        os_version: Optional[str],
        screen_resolution: Optional[str],
    ) -> Optional[Device]:
        """Register a device using a bind code."""
        logger.info(f"[DEBUG] register_device called: bind_code={bind_code}, device_name={device_name}, os={os}")
        
        # Validate bind code from Redis
        logger.info(f"[DEBUG] Validating bind code from Redis...")
        project_id = await bind_code_service.validate(bind_code)
        if not project_id:
            logger.warning(f"[DEBUG] Invalid or expired bind code: {bind_code}")
            return None

        logger.info(f"[DEBUG] Bind code valid, project_id={project_id}")

        # Create new device record
        try:
            device = Device(
                project_id=project_id,
                device_name=device_name,
                device_type=DeviceType(device_type),
                os=os,
                os_version=os_version,
                screen_resolution=screen_resolution,
                status=DeviceStatus.ONLINE,
                last_seen_at=datetime.now(timezone.utc),
                device_token=str(uuid.uuid4()),
            )
            logger.info(f"[DEBUG] Device object created: {device}")

            self.db.add(device)
            logger.info(f"[DEBUG] Device added to session, committing...")
            await self.db.commit()
            logger.info(f"[DEBUG] Commit successful, refreshing...")
            await self.db.refresh(device)

            logger.info(f"[DEBUG] Device registered successfully: {device_name} ({device.id}) for project {project_id}")
            return device
        except Exception as e:
            logger.error(f"[DEBUG] Error creating device record: {e}", exc_info=True)
            raise

    async def update_device(
        self,
        device_id: uuid.UUID,
        project_id: uuid.UUID,
        update_data: DeviceUpdateRequest,
    ) -> Optional[DeviceResponse]:
        """Update a device."""
        query = select(Device).where(
            and_(Device.id == device_id, Device.project_id == project_id)
        )
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()

        if not device:
            return None

        # Update fields
        if update_data.device_name is not None:
            device.device_name = update_data.device_name
        if update_data.ai_provider_id is not None:
            device.ai_provider_id = update_data.ai_provider_id if update_data.ai_provider_id else None
        if update_data.model is not None:
            device.model = update_data.model if update_data.model else None

        await self.db.commit()
        await self.db.refresh(device)

        return DeviceResponse.model_validate(device)

    async def update_device_status(
        self,
        device_id: uuid.UUID,
        status: DeviceStatus,
    ) -> None:
        """Update device status."""
        query = select(Device).where(Device.id == device_id)
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()

        if device:
            device.status = status
            if status == DeviceStatus.ONLINE:
                device.last_seen_at = datetime.now(timezone.utc)
            await self.db.commit()

    async def delete_device(
        self,
        device_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> bool:
        """Delete a device."""
        query = select(Device).where(
            and_(Device.id == device_id, Device.project_id == project_id)
        )
        result = await self.db.execute(query)
        device = result.scalar_one_or_none()

        if not device:
            return False

        await self.db.delete(device)
        await self.db.commit()

        logger.info(f"Device deleted: {device_id}")
        return True

    async def get_device_by_token(self, device_token: str) -> Optional[Device]:
        """Get a device by its token (for reconnection)."""
        query = select(Device).where(Device.device_token == device_token)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    # Session management

    async def create_session(
        self,
        device_id: uuid.UUID,
        agent_id: Optional[uuid.UUID] = None,
    ) -> DeviceSession:
        """Create a new device session."""
        session = DeviceSession(
            device_id=device_id,
            agent_id=agent_id,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def end_session(self, session_id: uuid.UUID) -> None:
        """End a device session."""
        query = select(DeviceSession).where(DeviceSession.id == session_id)
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if session:
            session.ended_at = datetime.now(timezone.utc)
            await self.db.commit()

    async def increment_session_stats(
        self,
        session_id: uuid.UUID,
        screenshots: int = 0,
        actions: int = 0,
    ) -> None:
        """Increment session statistics."""
        query = select(DeviceSession).where(DeviceSession.id == session_id)
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if session:
            session.screenshots_count += screenshots
            session.actions_count += actions
            await self.db.commit()
