"""Visitor Session model for tracking visitor conversation sessions."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionStatus(str, Enum):
    """Session status enumeration."""
    
    OPEN = "open"       # 会话进行中
    CLOSED = "closed"   # 会话已关闭


class VisitorSession(Base):
    """Visitor session model for tracking conversation sessions.

    This table tracks individual conversation sessions between visitors
    and staff members, including session duration and status.
    """

    __tablename__ = "api_visitor_sessions"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated project ID",
    )
    visitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_visitors.id", ondelete="CASCADE"),
        nullable=False,
        comment="Visitor who initiated this session",
    )
    staff_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member currently handling this session",
    )
    platform_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_platforms.id", ondelete="SET NULL"),
        nullable=True,
        comment="Platform where this session originated",
    )

    # Session status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SessionStatus.OPEN.value,
        comment="Session status: open, closed",
    )

    # Time tracking
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp when session was closed",
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total session duration in seconds",
    )

    # Message statistics
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of messages in this session",
    )
    visitor_message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of messages sent by visitor",
    )
    staff_message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of messages sent by staff",
    )
    ai_message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of messages sent by AI",
    )

    # Last activity
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp of the last message in this session",
    )
    last_message_seq: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Sequence number of the last message in this session",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Session start timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        lazy="select",
    )
    visitor: Mapped["Visitor"] = relationship(
        "Visitor",
        back_populates="sessions",
        lazy="select",
    )
    staff: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        lazy="select",
    )
    platform: Mapped[Optional["Platform"]] = relationship(
        "Platform",
        lazy="select",
    )
    assignment_histories: Mapped[List["VisitorAssignmentHistory"]] = relationship(
        "VisitorAssignmentHistory",
        back_populates="session",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorSession(id={self.id}, visitor_id={self.visitor_id}, "
            f"status={self.status})>"
        )

    def close(self) -> None:
        """Close the session and calculate duration."""
        if self.status != SessionStatus.CLOSED.value:
            self.status = SessionStatus.CLOSED.value
            self.closed_at = datetime.utcnow()
            if self.created_at:
                self.duration_seconds = int(
                    (self.closed_at - self.created_at).total_seconds()
                )

    @property
    def is_open(self) -> bool:
        """Check if session is currently open."""
        return self.status == SessionStatus.OPEN.value

    @property
    def is_closed(self) -> bool:
        """Check if session is closed."""
        return self.status == SessionStatus.CLOSED.value
