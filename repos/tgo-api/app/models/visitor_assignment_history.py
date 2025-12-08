"""Visitor Assignment History model for tracking LLM-based assignment decisions."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, func, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AssignmentSource(str, Enum):
    """Source of assignment decision."""
    
    LLM = "llm"           # LLM自动分配
    MANUAL = "manual"     # 人工手动分配
    RULE = "rule"         # 规则分配（如轮询、负载均衡等）
    TRANSFER = "transfer" # 转接


class VisitorAssignmentHistory(Base):
    """History record for visitor assignments.

    This table tracks all assignment decisions made for visitors,
    including LLM reasoning and metadata for analysis.
    """

    __tablename__ = "api_visitor_assignment_history"

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
        comment="Visitor being assigned",
    )
    assigned_staff_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member assigned to handle the visitor",
    )
    previous_staff_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Previous staff member (for transfers)",
    )
    assigned_by_staff_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff who initiated the assignment (for manual assignments)",
    )
    assignment_rule_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_visitor_assignment_rules.id", ondelete="SET NULL"),
        nullable=True,
        comment="Assignment rule used (for LLM assignments)",
    )
    session_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_visitor_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated visitor session",
    )

    # Assignment details
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AssignmentSource.LLM.value,
        comment="Source of assignment: llm, manual, rule, transfer",
    )
    
    # LLM-specific fields
    model_used: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="LLM model used for this assignment",
    )
    prompt_used: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Prompt sent to LLM",
    )
    llm_response: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full LLM response",
    )
    reasoning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="LLM reasoning for the assignment decision",
    )
    
    # Visitor context at assignment time
    visitor_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Visitor's message/question at assignment time",
    )
    visitor_context: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional visitor context (intent, sentiment, etc.)",
    )
    
    # Staff candidates considered
    candidate_staff_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="List of staff IDs considered for assignment",
    )
    candidate_scores: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Scores/rankings for each candidate",
    )
    
    # Performance metrics
    response_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="LLM response time in milliseconds",
    )
    token_usage: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Token usage statistics",
    )
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or comments",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Assignment timestamp",
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
    assigned_staff: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        foreign_keys=[assigned_staff_id],
        lazy="select",
    )
    previous_staff: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        foreign_keys=[previous_staff_id],
        lazy="select",
    )
    assigned_by_staff: Mapped[Optional["Staff"]] = relationship(
        "Staff",
        foreign_keys=[assigned_by_staff_id],
        lazy="select",
    )
    assignment_rule: Mapped[Optional["VisitorAssignmentRule"]] = relationship(
        "VisitorAssignmentRule",
        lazy="select",
    )
    session: Mapped[Optional["VisitorSession"]] = relationship(
        "VisitorSession",
        back_populates="assignment_histories",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<VisitorAssignmentHistory(id={self.id}, visitor_id={self.visitor_id}, "
            f"assigned_staff_id={self.assigned_staff_id}, source={self.source})>"
        )
