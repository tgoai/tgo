"""Platform model."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.visitor import Visitor

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, func, event, inspect as sa_inspect
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from app.core.database import Base


class PlatformType(str, Enum):
    """Platform type enumeration."""

    WEBSITE = "website"
    WECHAT = "wechat"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    EMAIL = "email"
    SMS = "sms"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    DISCORD = "discord"
    SLACK = "slack"
    TEAMS = "teams"
    PHONE = "phone"
    DOUYIN = "douyin"
    TIKTOK = "tiktok"
    CUSTOM = "custom"
    WECOM = "wecom"  # 企业微信
    WECOM_BOT = "wecom_bot"  # 企业微信机器人
    FEISHU_BOT = "feishu_bot"  # 飞书机器人
    DINGTALK_BOT = "dingtalk_bot"  # 钉钉机器人
    # Vision Agent 支持的平台类型 (通过 UI 自动化)
    WECHAT_PERSONAL = "wechat_personal"  # 个人微信


class PlatformTypeDefinition(Base):
    """Database-backed metadata for supported platform types."""

    __tablename__ = "api_platform_types"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Basic fields
    type: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Stable identifier (e.g., wechat, website, email)"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable platform name"
    )
    name_en: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="English name of the platform type (e.g., 'WeCom', 'Website')",
    )
    is_supported: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this platform type is currently supported",
    )
    icon: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="SVG icon markup for display"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )

    # Relationships
    platforms: Mapped[List["Platform"]] = relationship(
        "Platform",
        primaryjoin="PlatformTypeDefinition.type == foreign(Platform.type)",
        viewonly=True,
        lazy="select"
    )

    def __repr__(self) -> str:
        """String representation of the platform type."""
        return f"<PlatformTypeDefinition(id={self.id}, type='{self.type}')>"


class PlatformSyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


class PlatformAIMode(str, Enum):
    """Platform AI mode enumeration."""
    AUTO = "auto"           # 自动：AI 自动处理所有消息
    ASSIST = "assist"       # 辅助：人工优先，超时后 AI 接管
    OFF = "off"             # 关闭：AI 不处理消息


class Platform(Base):
    """Platform model for communication platforms."""

    __tablename__ = "api_platforms"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated project ID for multi-tenant isolation"
    )

    # Basic fields
    name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Platform name (e.g., WeChat, WhatsApp)"
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Platform type from predefined enum"
    )
    api_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Platform-specific API key for integrations"
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Platform-specific configuration"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether platform is active"
    )
    # AI configuration
    agent_ids: Mapped[Optional[List[UUID]]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)),
        nullable=True,
        comment="List of AI Agent IDs assigned to this platform"
    )
    ai_mode: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default=PlatformAIMode.AUTO.value,
        comment="AI mode: auto (AI handles all), assist (human first, AI fallback), off (AI disabled)"
    )
    fallback_to_ai_timeout: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=0,
        comment="Timeout in seconds before AI takes over when ai_mode=assist. 0 means AI never takes over."
    )

    # Website usage tracking
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the platform (specifically website type) has been used"
    )
    used_website_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="The URL of the website where this platform was first used"
    )
    used_website_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="The title of the website where this platform was first used"
    )


    # Logo storage
    logo_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="Relative path to logo file under PLATFORM_LOGO_UPLOAD_DIR",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Soft deletion timestamp"
    )

    # Sync tracking fields
    sync_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PlatformSyncStatus.PENDING.value,
        comment="Synchronization status with Platform Service (pending|synced|failed)",
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp of last successful sync",
    )
    sync_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last synchronization error message",
    )
    sync_retry_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of sync retry attempts",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="platforms",
        lazy="select"
    )

    visitors: Mapped[List["Visitor"]] = relationship(
        "Visitor",
        primaryjoin="Platform.id == foreign(Visitor.platform_id)",
        foreign_keys="Visitor.platform_id",
        back_populates="platform",
        lazy="select"
    )

    platform_type: Mapped[Optional["PlatformTypeDefinition"]] = relationship(
        "PlatformTypeDefinition",
        primaryjoin="foreign(Platform.type) == PlatformTypeDefinition.type",
        viewonly=True,
        uselist=False,
        lazy="select"
    )

    def __repr__(self) -> str:
        """String representation of the platform."""
        return f"<Platform(id={self.id}, name='{self.name}', type='{self.type}')>"

    @property
    def is_deleted(self) -> bool:
        """Check if the platform is soft deleted."""
        return self.deleted_at is not None

    @property
    def icon(self) -> Optional[str]:
        """Return SVG icon markup for the platform type, when available."""
        return self.platform_type.icon if self.platform_type else None

    @property
    def is_supported(self) -> Optional[bool]:
        """Whether this platform type is currently supported.

        Delegates to the related PlatformTypeDefinition when available.
        """
        return self.platform_type.is_supported if self.platform_type else None

    @property
    def name_en(self) -> Optional[str]:
        """English name of the platform type.

        Delegates to the related PlatformTypeDefinition when available.
        """
        return self.platform_type.name_en if self.platform_type else None


# --- SQLAlchemy event listeners to trigger synchronization ---
@event.listens_for(Platform, "after_insert")
def _platform_after_insert(mapper, connection, target: Platform) -> None:
    try:
        from app.services.platform_sync import trigger_platform_sync
        trigger_platform_sync(str(target.id))
    except Exception:  # pragma: no cover
        pass


@event.listens_for(Platform, "after_update")
def _platform_after_update(mapper, connection, target: Platform) -> None:
    try:
        from app.services.platform_sync import trigger_platform_sync
        insp = sa_inspect(target)
        changed = {attr.key for attr in insp.attrs if attr.history.has_changes()}
        sync_fields = {"sync_status", "last_synced_at", "sync_error", "sync_retry_count"}
        if not changed or changed.issubset(sync_fields):
            return
        trigger_platform_sync(str(target.id))
    except Exception:  # pragma: no cover
        pass


@event.listens_for(Platform, "after_delete")
def _platform_after_delete(mapper, connection, target: Platform) -> None:
    try:
        from app.services.platform_sync import trigger_platform_delete
        trigger_platform_delete(str(target.id))
    except Exception:  # pragma: no cover
        pass
