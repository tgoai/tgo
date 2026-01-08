"""Agent models for AI agent management."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.collection import AgentCollection
    from app.models.workflow import AgentWorkflow
    from app.models.project import Project
    from app.models.team import Team
    from app.models.llm_provider import LLMProvider
    from app.models.tool import Tool


class Agent(BaseModel):
    """
    Agent model for AI agent definitions.

    Agents represent individual AI assistants with their own configuration,
    instructions, and tool bindings.
    """

    __tablename__ = "ai_agents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Associated project ID (logical reference to API service)",
    )

    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_teams.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated team ID for team-based organization",
    )

    llm_provider_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_llm_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="Associated LLM provider (credentials) ID",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Agent name",
    )

    instruction: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Agent system instruction",
    )

    model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment='LLM model with provider prefix (format: "provider:model_name")',
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is the default agent for the project",
    )

    config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Agent configuration (temperature, max_tokens, markdown, add_datetime_to_context, etc.)",
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        primaryjoin="foreign(Agent.project_id) == Project.id",
        back_populates="agents",
        lazy="selectin",
    )

    team: Mapped[Optional["Team"]] = relationship(
        "Team",
        back_populates="agents",
        lazy="selectin",
    )

    llm_provider: Mapped[Optional["LLMProvider"]] = relationship(
        "LLMProvider",
        lazy="selectin",
    )

    tools: Mapped[List["Tool"]] = relationship(
        "Tool",
        secondary="ai_agent_tool_associations",
        primaryjoin="Agent.id == foreign(AgentToolAssociation.agent_id)",
        secondaryjoin="Tool.id == foreign(AgentToolAssociation.tool_id)",
        back_populates="agents",
        lazy="selectin",
    )

    collections: Mapped[List["AgentCollection"]] = relationship(
        "AgentCollection",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    workflows: Mapped[List["AgentWorkflow"]] = relationship(
        "AgentWorkflow",
        back_populates="agent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"<Agent(id={self.id}, name='{self.name}', project_id={self.project_id})>"

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

    @property
    def collection_ids(self) -> List[str]:
        """Get the collection IDs from agent collections."""
        return [agent_collection.collection_id for agent_collection in self.collections]

    @property
    def workflow_ids(self) -> List[str]:
        """Get the workflow IDs from agent workflows."""
        return [agent_workflow.workflow_id for agent_workflow in self.workflows]


class AgentToolAssociation(BaseModel):
    """
    Association entity between agents and tools with per-agent settings.

    Stores per-agent enablement, permissions, and configuration overrides
    for a given Tool.
    """

    __tablename__ = "ai_agent_tool_associations"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Associated agent ID",
    )

    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Associated tool ID",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether tool is enabled for this agent",
    )

    permissions: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Tool permissions array",
    )

    config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Agent-specific tool configuration overrides",
    )


    __table_args__ = (
        Index("idx_agent_tool_assoc_agent_id", "agent_id"),
        Index("idx_agent_tool_assoc_tool_id", "tool_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - convenience
        return f"<AgentToolAssociation(agent_id={self.agent_id}, tool_id={self.tool_id})>"


