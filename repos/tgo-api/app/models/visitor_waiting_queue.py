"""Visitor Waiting Queue model for managing visitors waiting for staff assignment."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.visitor import Visitor
    from app.models.visitor_session import VisitorSession
    from app.models.staff import Staff


class WaitingStatus(str, Enum):
    """Waiting queue status enumeration."""
    
    WAITING = "waiting"      # Visitor is waiting in queue
    ASSIGNED = "assigned"    # Visitor has been assigned to a staff
    CANCELLED = "cancelled"  # Visitor cancelled the wait (left)
    EXPIRED = "expired"      # Waiting timed out


class QueueSource(str, Enum):
    """Queue entry source enumeration."""
    
    AI_REQUEST = "ai_request"      # AI agent requested manual service
    VISITOR_REQUEST = "visitor"    # Visitor explicitly requested human service
    TRANSFER = "transfer"          # Staff transferred visitor
    SYSTEM = "system"              # System automatic (e.g., timeout transfer)
    NO_STAFF = "no_staff"          # No available staff, auto-queued


class QueueUrgency(str, Enum):
    """Queue urgency level enumeration."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Urgency to priority mapping
URGENCY_PRIORITY_MAP = {
    QueueUrgency.LOW.value: 0,
    QueueUrgency.NORMAL.value: 1,
    QueueUrgency.HIGH.value: 2,
    QueueUrgency.URGENT.value: 3,
}


class VisitorWaitingQueue(Base):
    """Visitor waiting queue for managing visitors awaiting staff assignment.
    
    This is the unified queue for all human service requests, including:
    - AI agent requests for manual service
    - Visitor explicit requests for human service
    - Automatic queuing when no staff is available
    - Staff transfers
    """

    __tablename__ = "api_visitor_waiting_queue"

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
        comment="Visitor waiting in queue",
    )
    session_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_visitor_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated visitor session",
    )
    assigned_staff_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member who picked this visitor from queue",
    )

    # Source and urgency
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QueueSource.NO_STAFF.value,
        comment="Queue entry source: ai_request, visitor, transfer, system, no_staff",
    )
    urgency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=QueueUrgency.NORMAL.value,
        comment="Urgency level: low, normal, high, urgent",
    )

    # Queue position and priority
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Queue position (lower = higher priority)",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Priority level (higher = more urgent), derived from urgency",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=WaitingStatus.WAITING.value,
        comment="Queue status: waiting, assigned, cancelled, expired",
    )

    # Context information
    visitor_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Message that triggered the transfer request",
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for entering queue (e.g., 'No available staff', 'AI requested')",
    )

    # Channel information (from AI events)
    channel_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Associated communication channel identifier",
    )
    channel_type: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Associated communication channel type code",
    )

    # Metadata for additional context
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Additional contextual metadata",
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of assignment retry attempts",
    )
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Timestamp of the last assignment attempt",
    )

    # Timestamps
    entered_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="When visitor entered the queue",
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="When visitor was assigned to a staff",
    )
    exited_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="When visitor exited the queue (assigned, cancelled, or expired)",
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Record creation timestamp",
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
        lazy="select",
    )
    session: Mapped[Optional["VisitorSession"]] = relationship(
        "VisitorSession",
        lazy="select",
    )
    assigned_staff: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorWaitingQueue(id={self.id}, visitor_id={self.visitor_id}, "
            f"source={self.source}, status={self.status}, position={self.position})>"
        )

    @property
    def is_waiting(self) -> bool:
        """Check if visitor is still waiting."""
        return self.status == WaitingStatus.WAITING.value

    @property
    def wait_duration_seconds(self) -> Optional[int]:
        """Calculate how long the visitor has been waiting."""
        if self.exited_at:
            return int((self.exited_at - self.entered_at).total_seconds())
        return int((datetime.utcnow() - self.entered_at).total_seconds())

    def assign_to_staff(self, staff_id: UUID) -> None:
        """Mark this queue entry as assigned to a staff member."""
        now = datetime.utcnow()
        self.status = WaitingStatus.ASSIGNED.value
        self.assigned_staff_id = staff_id
        self.assigned_at = now
        self.exited_at = now
        self.updated_at = now

    def cancel(self) -> None:
        """Mark this queue entry as cancelled."""
        now = datetime.utcnow()
        self.status = WaitingStatus.CANCELLED.value
        self.exited_at = now
        self.updated_at = now

    def expire(self) -> None:
        """Mark this queue entry as expired."""
        now = datetime.utcnow()
        self.status = WaitingStatus.EXPIRED.value
        self.exited_at = now
        self.updated_at = now

    def record_attempt(self) -> None:
        """Record an assignment attempt."""
        now = datetime.utcnow()
        self.retry_count += 1
        self.last_attempt_at = now
        self.updated_at = now

    @staticmethod
    def urgency_to_priority(urgency: str) -> int:
        """Convert urgency level to priority number."""
        return URGENCY_PRIORITY_MAP.get(urgency, 1)
