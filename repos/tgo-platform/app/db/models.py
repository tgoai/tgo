from __future__ import annotations
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Integer, BigInteger, Text, ForeignKey, UniqueConstraint, Index
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
    """Inbound WeCom messages stored for async processing pipeline.

    Supports both WeCom Customer Service (客服) and WeCom Bot (群机器人) messages,
    distinguished by the source_type field.
    """

    __tablename__ = "pt_wecom_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)

    # Message identity
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Source type to distinguish between WeCom KF (客服) and WeCom Bot (群机器人)
    # Values: "wecom_kf" (customer service), "wecom_bot" (group bot)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="wecom_kf", index=True)

    # Sender and content
    from_user: Mapped[str] = mapped_column(String(255), nullable=False)
    # Customer service account identifier (when applicable for wecom_kf)
    # For wecom_bot, this stores the ChatId
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


class FeishuInbox(Base):
    """Inbound Feishu Bot messages stored for async processing pipeline.

    Stores messages received from Feishu Bot callbacks for two-stage processing.
    The message_id from Feishu is used for replying via the Reply API.
    """

    __tablename__ = "pt_feishu_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)

    # Message identity (Feishu message_id, used for reply API)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Sender info
    from_user: Mapped[str] = mapped_column(String(255), nullable=False)  # open_id or user_id
    from_user_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open_id")  # open_id, user_id, union_id

    # Chat context
    chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # Group chat ID (null for P2P)
    chat_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="p2p")  # p2p, group

    # Message content
    msg_type: Mapped[str] = mapped_column(String(50), nullable=False)  # text, image, file, etc.
    content: Mapped[str] = mapped_column(Text, nullable=True)  # Extracted text content

    # AI response
    ai_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw event payload (stores full event for debugging and message_id extraction)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # From Feishu create_time
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("platform_id", "message_id", name="uq_feishu_inbox_platform_message"),
        Index("ix_feishu_inbox_platform_status", "platform_id", "status"),
        Index("ix_feishu_inbox_status_fetched", "status", "fetched_at"),
    )


class DingTalkInbox(Base):
    """Inbound DingTalk Bot messages stored for async processing pipeline.

    Stores messages received from DingTalk Bot callbacks for two-stage processing.
    The sessionWebhook is used for replying to messages.
    """

    __tablename__ = "pt_dingtalk_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)

    # Message identity
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Sender info
    from_user: Mapped[str] = mapped_column(String(255), nullable=False)  # senderId or staffId
    sender_nick: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Sender nickname

    # Conversation context
    conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    conversation_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1")  # 1=single, 2=group

    # Message content
    msg_type: Mapped[str] = mapped_column(String(50), nullable=False)  # text, picture, richText, etc.
    content: Mapped[str] = mapped_column(Text, nullable=True)  # Extracted text content

    # Session webhook for replying (important!)
    session_webhook: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_webhook_expired_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Expiry timestamp (milliseconds)

    # AI response
    ai_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw event payload
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
        UniqueConstraint("platform_id", "message_id", name="uq_dingtalk_inbox_platform_message"),
        Index("ix_dingtalk_inbox_platform_status", "platform_id", "status"),
        Index("ix_dingtalk_inbox_status_fetched", "status", "fetched_at"),
    )


class TelegramInbox(Base):
    """Inbound Telegram Bot messages stored for async processing pipeline.

    Stores messages received from Telegram Bot webhook callbacks for two-stage processing.
    The chat_id is used for replying to messages via sendMessage API.
    """

    __tablename__ = "pt_telegram_inbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Associations
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pt_platforms.id", ondelete="CASCADE"), index=True, nullable=False)

    # Message identity (Telegram message_id, unique per chat)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    update_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Telegram update_id for deduplication

    # Sender info
    from_user: Mapped[str] = mapped_column(String(255), nullable=False)  # Telegram user_id
    from_username: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Telegram @username
    from_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # First name + Last name

    # Chat context
    chat_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # Chat ID for replying
    chat_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="private")  # private, group, supergroup, channel

    # Message content
    msg_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="text")  # text, photo, document, etc.
    content: Mapped[str] = mapped_column(Text, nullable=True)  # Extracted text content

    # AI response
    ai_reply: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw event payload (stores full update for debugging)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # From Telegram message.date
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Processing status
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint("platform_id", "message_id", "chat_id", name="uq_telegram_inbox_platform_message_chat"),
        Index("ix_telegram_inbox_platform_status", "platform_id", "status"),
        Index("ix_telegram_inbox_status_fetched", "status", "fetched_at"),
        Index("ix_telegram_inbox_update_id", "update_id"),
    )


