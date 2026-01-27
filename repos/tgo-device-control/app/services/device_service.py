"""Device Service - Database operations for devices."""

import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.device import Device, DeviceSession, DeviceStatus, DeviceType
from app.schemas.device import DeviceResponse, DeviceUpdateRequest

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

    async def get_device_by_bind_code(self, bind_code: str) -> Optional[Device]:
        """Get a device by bind code (for registration)."""
        now = datetime.now(timezone.utc)
        query = select(Device).where(
            and_(
                Device.bind_code == bind_code,
                Device.bind_code_expires_at > now,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def generate_bind_code(
        self,
        project_id: uuid.UUID,
    ) -> Tuple[str, datetime]:
        """Generate a new bind code and create a placeholder device."""
        # Generate random code
        code_length = settings.BIND_CODE_LENGTH
        bind_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=code_length))

        # Calculate expiry
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.BIND_CODE_EXPIRY_MINUTES
        )

        # Create placeholder device
        device = Device(
            project_id=project_id,
            device_name="Pending",
            device_type=DeviceType.DESKTOP,
            os="unknown",
            status=DeviceStatus.OFFLINE,
            bind_code=bind_code,
            bind_code_expires_at=expires_at,
        )

        self.db.add(device)
        await self.db.commit()

        logger.info(f"Generated bind code {bind_code} for project {project_id}")
        return bind_code, expires_at

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
        device = await self.get_device_by_bind_code(bind_code)
        if not device:
            logger.warning(f"Invalid or expired bind code: {bind_code}")
            return None

        # Update device info
        device.device_name = device_name
        device.device_type = DeviceType(device_type)
        device.os = os
        device.os_version = os_version
        device.screen_resolution = screen_resolution
        device.status = DeviceStatus.ONLINE
        device.bind_code = None
        device.bind_code_expires_at = None
        device.last_seen_at = datetime.now(timezone.utc)

        # Generate device token
        device.device_token = str(uuid.uuid4())

        await self.db.commit()
        await self.db.refresh(device)

        logger.info(f"Device registered: {device_name} ({device.id})")
        return device

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
