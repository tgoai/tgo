"""Database models for tgo-vision-agent."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VisionAgentInbox(Base):
    """Inbox table for storing messages from UI automation.

    Supports all application types (WeChat, Douyin, Xiaohongshu, etc.)
    """

    __tablename__ = "va_inbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    app_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Application type: wechat, douyin, xiaohongshu, etc.",
    )
    contact_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Contact ID within the application",
    )
    contact_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Contact display name",
    )
    message_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message content",
    )
    message_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="text",
        comment="Message type: text, image, voice, video, etc.",
    )
    direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Message direction: inbound or outbound",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Processing status: pending, processing, completed, failed",
    )
    screenshot_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to screenshot for debugging",
    )
    app_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Application-specific metadata",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed",
    )
    retry_count: Mapped[int] = mapped_column(
        default=0,
        comment="Number of retry attempts",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class VisionAgentSession(Base):
    """AgentBay session management table."""

    __tablename__ = "va_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
        comment="Platform ID from tgo-api (one session per platform)",
    )
    app_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Application type: wechat, douyin, xiaohongshu, etc.",
    )
    agentbay_session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="AgentBay session ID",
    )
    environment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mobile",
        comment="Environment type: mobile or desktop",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
        comment="Session status: active, paused, terminated",
    )
    app_login_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="offline",
        comment="App login status: logged_in, qr_pending, offline",
    )
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last heartbeat timestamp",
    )
    last_screenshot_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last screenshot timestamp",
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Session configuration",
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


class MessageFingerprint(Base):
    """Message fingerprint table for deduplication."""

    __tablename__ = "va_message_fingerprints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    platform_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hash of message content + contact + approximate time",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiration time for automatic cleanup",
    )
