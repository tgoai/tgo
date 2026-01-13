"""Tool model for storing project-level tool configurations.

Follows existing conventions: BaseModel (id, timestamps, soft delete),
no foreign key constraint on project_id, and explicit indexes.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import String, Text, Index, JSON as SAJSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from sqlalchemy import Enum as SAEnum

from app.models.base import BaseModel


if TYPE_CHECKING:
    from app.models.agent import Agent


class ToolType(str, Enum):
    """Tool type enumeration."""
    MCP = "MCP"
    FUNCTION = "FUNCTION"
    ALL = "ALL"


class ToolSourceType(str, Enum):
    """Tool source type enumeration."""
    LOCAL = "LOCAL"           # 本地配置的工具
    STORE = "STORE"           # 从商店安装的工具


class Tool(BaseModel):
    """Project-level tool configuration."""

    __tablename__ = "ai_tools"

    # Project scope (no foreign key constraint by design)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Associated project ID",
    )

    # Human-readable name and description
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Tool name",
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Display title for the tool (Legacy/Fallback)",
    )

    title_zh: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Display title for the tool (Chinese)",
    )

    title_en: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Display title for the tool (English)",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Optional tool description",
    )

    # Classification and connectivity
    tool_type: Mapped[ToolType] = mapped_column(
        SAEnum(ToolType, name="tool_type_enum"),
        nullable=False,
        comment="Tool type (MCP or FUNCTION)",
    )

    transport_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Transport type (e.g., http, stdio, sse)",
    )

    endpoint: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
        comment="Endpoint URL or path",
    )

    # Tool Store integration
    tool_source_type: Mapped[ToolSourceType] = mapped_column(
        SAEnum(ToolSourceType, name="tool_source_type_enum"),
        nullable=False,
        default=ToolSourceType.LOCAL,
        comment="Tool source (LOCAL or STORE)",
    )

    store_resource_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Associated Store resource ID",
    )

    # JSONB configuration (provider- or tool-specific settings)
    # Use JSONB on Postgres, fallback to JSON on SQLite for tests
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB().with_variant(SAJSON(), "sqlite"),
        nullable=True,
        comment="Tool configuration as JSON object",
    )

    # Many-to-many relationship to agents via association table
    agents: Mapped[List["Agent"]] = relationship(
        "Agent",
        secondary="ai_agent_tool_associations",
        primaryjoin="Tool.id == foreign(AgentToolAssociation.tool_id)",
        secondaryjoin="Agent.id == foreign(AgentToolAssociation.agent_id)",
        back_populates="tools",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_tools_project_id", "project_id"),
        Index("idx_tools_name", "name"),
        Index("idx_tools_store_resource_id", "store_resource_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - convenience
        return f"<Tool(id={self.id}, project_id={self.project_id}, name='{self.name}', type={self.tool_type})>"

