"""Team model for organizing AI agents."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.project import Project
    from app.models.llm_provider import LLMProvider


class Team(BaseModel):
    """
    Team model for team-based organization of agents.

    Teams provide a way to organize agents with shared configuration,
    model settings, and instructions.
    """

    __tablename__ = "ai_teams"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Associated project ID (logical reference to API service)",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Team name",
    )

    model: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        comment='LLM model used by the team in format "provider:model_name"',
    )

    instruction: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Team system prompt/instructions",
    )

    expected_output: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Expected output format description",
    )

    session_id: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        comment="Team session identifier",
    )
    llm_provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_llm_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated LLM provider (credentials) ID",
    )


    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default team for the project",
    )

    config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Team configuration (respond_directly, num_history_runs, etc.)",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        primaryjoin="foreign(Team.project_id) == Project.id",
        back_populates="teams",
        lazy="selectin",
    )

    agents: Mapped[List["Agent"]] = relationship(
        "Agent",
        back_populates="team",
        lazy="selectin",
    )

    llm_provider: Mapped[Optional["LLMProvider"]] = relationship(
        "LLMProvider",
        lazy="selectin",
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "is_default",
            name="uq_ai_teams_default_per_project",
        ),
    )

    def __repr__(self) -> str:
        """String representation of the team."""
        return f"<Team(id={self.id}, name='{self.name}', project_id={self.project_id})>"

    @property
    def provider(self) -> str:
        """Extract provider from model string."""
        if ":" in self.model:
            return self.model.split(":", 1)[0]
        return "unknown"

    @property
    def model_name(self) -> str:
        """Extract model name from model string."""
        if ":" in self.model:
            return self.model.split(":", 1)[1]
        return self.model
