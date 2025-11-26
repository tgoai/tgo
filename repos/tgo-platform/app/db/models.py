from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Integer, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Platform(Base):
    """Third-party platform configuration (multi-tenant, soft delete, credentials)."""

    __tablename__ = "pt_platforms"

    # Primary key (UUID)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Project/Tenant id
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Platform identity
    name: Mapped[str] = mapped_column(String(100), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Platform-specific configuration
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Activation state
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional per-platform API key
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)




class EmailInbox(Base):
    """Raw inbound emails stored for two-stage processing pipeline."""

    __tablename__ = "pt_email_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)

    # Message identity
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_uid: Mapped[str] = mapped_column(String(255), nullable=False)

    # Sender and content
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ai_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_headers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("platform_id", "message_id", name="uq_email_inbox_platform_message"),
        Index("ix_email_inbox_platform_status", "platform_id", "status"),
        Index("ix_email_inbox_status_fetched", "status", "fetched_at"),
    )


class WeComInbox(Base):
    """Inbound WeCom messages stored for async processing pipeline."""

    __tablename__ = "pt_wecom_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)

    # Message identity
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Sender and content
    from_user: Mapped[str] = mapped_column(String(255), nullable=False)
    # Customer service account identifier (when applicable)
    open_kfid: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    msg_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    is_from_colleague: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)

    ai_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("platform_id", "message_id", name="uq_wecom_inbox_platform_message"),
        Index("ix_wecom_inbox_platform_status", "platform_id", "status"),
        Index("ix_wecom_inbox_status_fetched", "status", "fetched_at"),
    )



class WuKongIMInbox(Base):
    """Inbound WuKongIM messages stored for async processing pipeline."""

    __tablename__ = "pt_wukongim_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)

    # Identity and dedup
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_msg_no: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Message metadata
    from_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[int] = mapped_column(Integer, nullable=False)
    message_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # decoded plain text/JSON content
    platform_open_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # visitor's platform-specific ID

    # Raw and processing
    raw_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("platform_id", "message_id", name="uq_wukongim_inbox_platform_message"),
        Index("ix_wukongim_inbox_platform_status_fetched", "platform_id", "status", "fetched_at"),
        Index("ix_wukongim_inbox_platform_client_msg_no", "platform_id", "client_msg_no"),
    )

