"""Device database models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DeviceType(str, PyEnum):
    """Device type enumeration."""

    DESKTOP = "desktop"
    MOBILE = "mobile"

    def __str__(self) -> str:
        return self.value


class DeviceStatus(str, PyEnum):
    """Device status enumeration."""

    ONLINE = "online"
    OFFLINE = "offline"

    def __str__(self) -> str:
        return self.value


class Device(Base):
    """Device model for storing connected devices."""

    __tablename__ = "dc_devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    device_type: Mapped[DeviceType] = mapped_column(
        Enum(DeviceType, name="dc_device_type", values_callable=lambda x: [e.value for e in x]),
        default=DeviceType.DESKTOP,
        nullable=False,
    )
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    os: Mapped[str] = mapped_column(String(50), nullable=False)
    os_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    screen_resolution: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, name="dc_device_status", values_callable=lambda x: [e.value for e in x]),
        default=DeviceStatus.OFFLINE,
        nullable=False,
    )
    bind_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    bind_code_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    device_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    sessions: Mapped[list["DeviceSession"]] = relationship(
        "DeviceSession",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Device {self.device_name} ({self.id})>"


class DeviceSession(Base):
    """Device session model for tracking usage sessions."""

    __tablename__ = "dc_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dc_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    screenshots_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<DeviceSession {self.id} (device={self.device_id})>"
