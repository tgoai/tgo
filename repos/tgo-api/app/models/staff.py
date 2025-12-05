"""Staff model."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StaffRole(str, Enum):
    """Staff role enumeration."""
    
    USER = "user"
    ADMIN = "admin"
    AGENT = "agent"


class StaffStatus(str, Enum):
    """Staff status enumeration."""
    
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"


class Staff(Base):
    """Staff model for human users and AI agents."""

    __tablename__ = "api_staff"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated project ID for multi-tenant isolation"
    )

    # Basic fields
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        comment="Staff username for login"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password for authentication (bcrypt, argon2, etc.)"
    )
    nickname: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Staff display name"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Staff avatar URL"
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        comment="Staff role: user or agent"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="offline",
        comment="Staff status: online, offline, busy"
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
        back_populates="staff",
        lazy="select"
    )
    
    assigned_visitors: Mapped[List["VisitorAssignment"]] = relationship(
        "VisitorAssignment",
        foreign_keys="VisitorAssignment.assigned_staff_id",
        back_populates="assigned_staff",
        lazy="select"
    )
    
    previous_assignments: Mapped[List["VisitorAssignment"]] = relationship(
        "VisitorAssignment",
        foreign_keys="VisitorAssignment.previous_staff_id",
        back_populates="previous_staff",
        lazy="select"
    )
    
    created_assignments: Mapped[List["VisitorAssignment"]] = relationship(
        "VisitorAssignment",
        foreign_keys="VisitorAssignment.assigned_by_staff_id",
        back_populates="assigned_by_staff",
        lazy="select"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            role.in_(["user", "admin", "agent"]),
            name="chk_api_staff_role"
        ),
        CheckConstraint(
            status.in_(["online", "offline", "busy"]),
            name="chk_api_staff_status"
        ),
    )

    def __repr__(self) -> str:
        """String representation of the staff."""
        return f"<Staff(id={self.id}, username='{self.username}', role='{self.role}')>"

    @property
    def is_deleted(self) -> bool:
        """Check if the staff is soft deleted."""
        return self.deleted_at is not None

    @property
    def is_online(self) -> bool:
        """Check if the staff is online."""
        return self.status == StaffStatus.ONLINE

    @property
    def is_agent(self) -> bool:
        """Check if the staff is an AI agent."""
        return self.role == StaffRole.AGENT
