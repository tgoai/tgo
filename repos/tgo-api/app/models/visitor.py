"""Visitor model."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.platform import Platform
from app.models.project import Project
from app.models.visitor_ai_insight import VisitorAIInsight
from app.models.visitor_ai_profile import VisitorAIProfile
from app.models.visitor_system_info import VisitorSystemInfo

if TYPE_CHECKING:
    from app.models.visitor_activity import VisitorActivity
    from app.models.visitor_tag import VisitorTag
    from app.models.visitor_customer_update import VisitorCustomerUpdate
    from app.models.visitor_session import VisitorSession


class VisitorServiceStatus(str, Enum):
    """Visitor service status enumeration.
    
    State transitions:
    - NEW: Initial state when visitor is created
    - QUEUED: Visitor is in the waiting queue
    - ACTIVE: Staff is actively serving the visitor
    - CLOSED: Service session is closed
    
    Allowed transitions:
    - NEW -> QUEUED (visitor requests human service)
    - NEW -> ACTIVE (direct assignment without queue)
    - QUEUED -> ACTIVE (staff assigned from queue)
    - ACTIVE -> CLOSED (service ends)
    - CLOSED -> QUEUED (visitor requests service again)
    - CLOSED -> ACTIVE (visitor re-engaged)
    """
    
    NEW = "new"                       # Visitor just created, no service requested
    QUEUED = "queued"                 # In waiting queue for human service
    ACTIVE = "active"                 # Currently being served by staff
    CLOSED = "closed"                 # Service session closed


# Statuses indicating visitor is unassigned (can be assigned to staff)
UNASSIGNED_STATUSES = {VisitorServiceStatus.NEW.value, VisitorServiceStatus.CLOSED.value}


class Visitor(Base):
    """Visitor model for external users/customers."""

    __tablename__ = "api_visitors"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated project ID for multi-tenant isolation"
    )
    platform_id: Mapped[UUID] = mapped_column(
        nullable=False,
        comment="Associated platform ID"
    )

    # Basic fields
    platform_open_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Visitor unique identifier on this platform"
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Visitor real name"
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Visitor nickname on this platform (English)"
    )
    nickname_zh: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Visitor nickname in Chinese"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Visitor avatar URL on this platform"
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="Visitor phone number on this platform"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Visitor email on this platform"
    )
    company: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Visitor company or organization"
    )
    job_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Visitor job title or position"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Acquisition source describing how the visitor found us"
    )
    note: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about the visitor"
    )
    custom_attributes: Mapped[dict[str, str | None]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Arbitrary custom attributes set by staff"
    )

    # Activity tracking
    first_visit_time: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="When the visitor first accessed the system"
    )
    last_visit_time: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Visitor most recent activity/visit time"
    )
    last_offline_time: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Most recent time visitor went offline (NULL when never offline or currently online)"
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the visitor is currently online/active"
    )
    ai_disabled: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
        comment="Whether AI responses are disabled for this visitor"
    )
    
    # Locale and network info
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Visitor timezone (e.g., 'Asia/Shanghai', 'America/New_York')"
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Visitor preferred language code (e.g., 'en', 'zh-CN')"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="Visitor IP address (supports both IPv4 and IPv6)"
    )
    
    # Geolocation (derived from IP address)
    geo_country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Country name derived from IP address"
    )
    geo_country_code: Mapped[Optional[str]] = mapped_column(
        String(2),
        nullable=True,
        comment="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CN')"
    )
    geo_region: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Region/state/province name"
    )
    geo_city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="City name"
    )
    geo_isp: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Internet Service Provider (available with ip2region)"
    )
    
    # Service status
    service_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=VisitorServiceStatus.NEW.value,
        comment="Service status: new, queued, active, closed"
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

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="visitors",
        lazy="select"
    )

    platform: Mapped["Platform"] = relationship(
        "Platform",
        primaryjoin="foreign(Visitor.platform_id) == Platform.id",
        foreign_keys="Visitor.platform_id",
        back_populates="visitors",
        lazy="select"
    )

    visitor_tags: Mapped[List["VisitorTag"]] = relationship(
        "VisitorTag",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select"
    )

    ai_profile: Mapped[Optional["VisitorAIProfile"]] = relationship(
        "VisitorAIProfile",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select",
        uselist=False
    )
    ai_insight: Mapped[Optional["VisitorAIInsight"]] = relationship(
        "VisitorAIInsight",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select",
        uselist=False
    )
    system_info: Mapped[Optional["VisitorSystemInfo"]] = relationship(
        "VisitorSystemInfo",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select",
        uselist=False
    )
    activities: Mapped[List["VisitorActivity"]] = relationship(
        "VisitorActivity",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select"
    )
    customer_updates: Mapped[List["VisitorCustomerUpdate"]] = relationship(
        "VisitorCustomerUpdate",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select",
    )
    sessions: Mapped[List["VisitorSession"]] = relationship(
        "VisitorSession",
        back_populates="visitor",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        """String representation of the visitor."""
        display_name = self.name or self.nickname or self.platform_open_id
        return f"<Visitor(id={self.id}, name='{display_name}')>"

    @property
    def is_deleted(self) -> bool:
        """Check if the visitor is soft deleted."""
        return self.deleted_at is not None

    @property
    def platform_type(self) -> Optional[str]:
        """Convenience accessor for the associated platform type.
        Returns the platform.type string (e.g., 'website', 'wechat') when available.
        """
        try:
            return self.platform.type if self.platform is not None else None
        except Exception:
            return None

    @property
    def display_name(self) -> str:
        """Get the best available display name for the visitor."""
        return self.name or self.nickname or self.platform_open_id

    @property
    def is_unassigned(self) -> bool:
        """Check if visitor is unassigned (can be assigned to staff)."""
        return self.service_status in UNASSIGNED_STATUSES

    def set_status_queued(self) -> None:
        """Set visitor status to QUEUED."""
        self.service_status = VisitorServiceStatus.QUEUED.value
        self.updated_at = datetime.utcnow()

    def set_status_active(self) -> None:
        """Set visitor status to ACTIVE."""
        self.service_status = VisitorServiceStatus.ACTIVE.value
        self.updated_at = datetime.utcnow()

    def set_status_closed(self) -> None:
        """Set visitor status to CLOSED."""
        self.service_status = VisitorServiceStatus.CLOSED.value
        self.updated_at = datetime.utcnow()
