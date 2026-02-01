"""Agent-related Pydantic schemas."""

import enum
import uuid
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic import ConfigDict

from app.schemas.base import BaseSchema, IDMixin, PaginatedResponse, TimestampMixin
from app.schemas.tool import AgentToolDetail
from pydantic import computed_field


class AgentCategory(str, enum.Enum):
    """Agent category enumeration."""
    NORMAL = "normal"
    COMPUTER_USE = "computer_use"


class AgentToolBase(BaseSchema):
    """Base agent tool schema."""

    tool_id: uuid.UUID = Field(
        description="Tool ID (UUID) to bind to the agent",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    enabled: bool = Field(
        default=True,
        description="Whether tool is enabled for this agent",
    )
    permissions: Optional[List[str]] = Field(
        default=None,
        description="Tool permissions array",
        examples=[["read", "write"]],
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Tool-specific configuration",
        examples=[{"api_endpoint": "https://api.search.com", "timeout": 30}],
    )



class AgentToolCreate(AgentToolBase):
    """Schema for creating agent tool bindings."""

    pass


class AgentToolResponse(AgentToolBase, IDMixin, TimestampMixin):
    """Schema for agent tool API responses."""

    agent_id: uuid.UUID = Field(description="Associated agent ID")


class AgentBase(BaseSchema):
    """Base agent schema with common fields."""

    name: str = Field(
        max_length=255,
        description="Agent name",
        examples=["Customer Support Agent"],
    )
    instruction: Optional[str] = Field(
        default=None,
        description="Agent system instruction",
        examples=["You are a helpful customer support agent..."],
    )
    model: str = Field(
        max_length=150,
        description="LLM model with provider",
        examples=["claude-3-sonnet-20240229"],
    )
    is_default: bool = Field(
        default=False,
        description="Whether this should be the default agent (only one per project)",
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Agent configuration (temperature, max_tokens, etc.)",
        examples=[{"temperature": 0.7, "max_tokens": 2000}],
    )
    is_remote_store_agent: bool = Field(
        default=False,
        description="Whether this is a remote agent from store",
    )
    remote_agent_url: Optional[str] = Field(
        default=None,
        description="URL of the remote AgentOS server",
    )
    store_agent_id: Optional[str] = Field(
        default=None,
        description="Agent ID in the remote store",
    )
    agent_category: AgentCategory = Field(
        default=AgentCategory.NORMAL,
        description="Agent category: normal or computer_use",
    )


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""

    team_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Team ID to associate the agent with (optional)",
    )
    llm_provider_id: Optional[uuid.UUID] = Field(
        default=None,
        description="LLM provider (credentials) ID to use for this agent; overrides team-level provider if set",
    )
    tools: Optional[List[AgentToolCreate]] = Field(
        default_factory=list,
        description="Tools to bind to the agent",
    )
    collections: Optional[List[str]] = Field(
        default_factory=list,
        description="Collection IDs to associate with the agent (UUID strings)",
        examples=[["123e4567-e89b-12d3-a456-426614174000", "987fcdeb-51a2-43d1-9f6e-123456789abc"]],
    )
    workflows: Optional[List[str]] = Field(
        default_factory=list,
        description="Workflow IDs to associate with the agent (UUID strings)",
        examples=[["123e4567-e89b-12d3-a456-426614174000", "987fcdeb-51a2-43d1-9f6e-123456789abc"]],
    )
    bound_device_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Device ID to bind (only for computer_use category)",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )

    @field_validator("collections", "workflows")
    @classmethod
    def validate_ids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate that all IDs are valid UUIDs."""
        if v is not None:
            for item_id in v:
                try:
                    uuid.UUID(item_id)
                except ValueError:
                    raise ValueError(f"Invalid UUID format: {item_id}")
        return v


class AgentUpdate(BaseSchema):
    """Schema for updating an existing agent."""

    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Updated agent name",
    )
    team_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Updated team ID (set to null to remove from team)",
    )
    llm_provider_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Updated LLM provider (credentials) ID (set to null to inherit from team)",
    )
    instruction: Optional[str] = Field(
        default=None,
        description="Updated system instruction",
    )
    model: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Updated LLM model",
    )
    is_default: Optional[bool] = Field(
        default=None,
        description="Updated default status",
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated agent configuration",
    )
    is_remote_store_agent: Optional[bool] = Field(
        default=None,
        description="Update remote status",
    )
    remote_agent_url: Optional[str] = Field(
        default=None,
        description="Update remote URL",
    )
    store_agent_id: Optional[str] = Field(
        default=None,
        description="Update remote agent ID",
    )
    agent_category: Optional[AgentCategory] = Field(
        default=None,
        description="Updated agent category: normal or computer_use",
    )
    tools: Optional[List[AgentToolCreate]] = Field(
        default=None,
        description="Updated tools to bind to the agent",
    )
    collections: Optional[List[str]] = Field(
        default=None,
        description="Updated collection IDs to associate with the agent (UUID strings). Replaces existing associations.",
        examples=[["123e4567-e89b-12d3-a456-426614174000", "987fcdeb-51a2-43d1-9f6e-123456789abc"]],
    )
    workflows: Optional[List[str]] = Field(
        default=None,
        description="Updated workflow IDs to associate with the agent (UUID strings). Replaces existing associations.",
        examples=[["123e4567-e89b-12d3-a456-426614174000", "987fcdeb-51a2-43d1-9f6e-123456789abc"]],
    )
    bound_device_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Updated device ID to bind (only for computer_use category). Replaces existing binding.",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )

    @field_validator("collections", "workflows")
    @classmethod
    def validate_ids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate that all IDs are valid UUIDs."""
        if v is not None:
            for item_id in v:
                try:
                    uuid.UUID(item_id)
                except ValueError:
                    raise ValueError(f"Invalid UUID format: {item_id}")
        return v



class AgentResponse(AgentBase, IDMixin, TimestampMixin):
    """Schema for agent API responses."""

    team_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Associated team ID",
    )
    llm_provider_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Associated LLM provider (credentials) ID",
    )



class AgentWithDetails(AgentResponse):
    """Schema for agent response with additional details.

    - tools: full Tool objects from local database (ai_tools table)
    - collections: RAG collections as before
    """

    # Allow unknown/extra fields to be ignored when validating from ORM/dicts
    model_config = ConfigDict(extra="ignore")

    # Expose resolved Tool details under `tools`, reading from `_tools_data`
    tools: List[AgentToolDetail] = Field(
        default_factory=list,
        description="Detailed tool information for bound tools (from ai_tools table)",
        validation_alias="_tools_data",
        serialization_alias="tools",
    )

    collections: List["CollectionResponse"] = Field(
        default_factory=list,
        description="Collections accessible to this agent",
        alias="_collection_data",
        serialization_alias="collections",
    )

    workflows: List["WorkflowResponse"] = Field(
        default_factory=list,
        description="Workflows accessible to this agent",
        alias="_workflow_data",
        serialization_alias="workflows",
    )


# Forward reference resolution
from app.schemas.collection import CollectionResponse  # noqa: E402
from app.schemas.workflow import WorkflowResponse  # noqa: E402

AgentWithDetails.model_rebuild()


class AgentListResponse(PaginatedResponse[AgentWithDetails]):
    """Paginated response model for agent list endpoint with detailed agent information."""

    pass


class ToggleEnabledRequest(BaseSchema):
    """Generic request to toggle enabled state for a binding."""

    enabled: bool = Field(description="Whether the binding should be enabled")
