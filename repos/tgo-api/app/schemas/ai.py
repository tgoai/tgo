"""AI service schemas for proxy endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal, TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import BaseSchema, PaginationMetadata

if TYPE_CHECKING:
    from app.schemas.ai_workflows import WorkflowSummary


# Agent Category Enum
class AgentCategory(str, Enum):
    """Agent category enumeration."""
    NORMAL = "normal"
    COMPUTER_USE = "computer_use"


# Model-related Enums and Schemas
class ModelType(str, Enum):
    """Enumeration of supported model types."""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    IMAGE = "image"
    AUDIO = "audio"


class ModelStatus(str, Enum):
    """Enumeration of model status values."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"
    BETA = "beta"


class PricingTier(str, Enum):
    """Enumeration of pricing tiers."""
    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PREMIUM = "premium"


class ModelCapabilities(BaseSchema):
    """Schema for model capabilities and features."""

    context_length: int = Field(
        ...,
        ge=1,
        description="Maximum context length in tokens",
        examples=[4096, 8192, 32768, 128000]
    )
    supports_functions: bool = Field(
        default=False,
        description="Whether the model supports function calling"
    )
    supports_vision: bool = Field(
        default=False,
        description="Whether the model supports image/vision inputs"
    )
    supports_streaming: bool = Field(
        default=True,
        description="Whether the model supports streaming responses"
    )
    supports_system_messages: bool = Field(
        default=True,
        description="Whether the model supports system messages"
    )
    max_output_tokens: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum output tokens per response",
        examples=[1024, 2048, 4096]
    )
    input_modalities: List[str] = Field(
        default_factory=lambda: ["text"],
        description="Supported input modalities",
        examples=[["text"], ["text", "image"], ["text", "audio"]]
    )
    output_modalities: List[str] = Field(
        default_factory=lambda: ["text"],
        description="Supported output modalities",
        examples=[["text"], ["text", "image"], ["text", "audio"]]
    )


class ModelInfo(BaseSchema):
    """Schema for model information."""

    id: str = Field(
        ...,
        description="Unique model identifier with provider prefix",
        examples=["openai:gpt-4", "anthropic:claude-3-sonnet-20240229", "openai:text-embedding-ada-002"]
    )
    display_name: str = Field(
        ...,
        description="Human-readable model name",
        examples=["GPT-4", "Claude 3 Sonnet", "Text Embedding Ada 002"]
    )
    provider: str = Field(
        ...,
        description="Model provider name",
        examples=["OpenAI", "Anthropic", "Google", "Meta"]
    )
    model_type: ModelType = Field(
        ...,
        description="Type of model (chat, completion, embedding, etc.)"
    )
    status: ModelStatus = Field(
        ...,
        description="Current model status"
    )
    capabilities: ModelCapabilities = Field(
        ...,
        description="Model capabilities and features"
    )
    pricing_tier: PricingTier = Field(
        ...,
        description="Pricing tier for the model"
    )
    description: Optional[str] = Field(
        None,
        description="Detailed model description",
        examples=["Advanced reasoning model with improved performance on complex tasks"]
    )
    version: Optional[str] = Field(
        None,
        description="Model version or release date",
        examples=["2024-02-29", "v1.0", "turbo-2024-04-09"]
    )
    release_date: Optional[datetime] = Field(
        None,
        description="Model release date"
    )
    deprecation_date: Optional[datetime] = Field(
        None,
        description="Model deprecation date (if applicable)"
    )
    documentation_url: Optional[str] = Field(
        None,
        description="URL to model documentation",
        examples=["https://platform.openai.com/docs/models/gpt-4"]
    )


class ModelListResponse(BaseSchema):
    """Schema for paginated model list responses."""

    data: List[ModelInfo] = Field(
        ...,
        description="List of supported models"
    )
    pagination: PaginationMetadata = Field(
        ...,
        description="Pagination metadata"
    )


# Team Schemas
class TeamCreateRequest(BaseSchema):
    """Schema for creating a new team."""

    name: str = Field(
        ...,
        max_length=255,
        description="Team name",
        examples=["Customer Support Team"]
    )
    model: str = Field(
        ...,
        max_length=150,
        description="LLM model name (no provider prefix)",
        examples=["gpt-4", "claude-3-sonnet-20240229"]
    )
    instruction: Optional[str] = Field(
        None,
        description="Team system prompt/instructions",
        examples=["You are a customer support team focused on resolving user issues efficiently..."]
    )
    expected_output: Optional[str] = Field(
        None,
        description="Expected output format description",
        examples=["Provide clear, actionable solutions with step-by-step instructions"]
    )
    session_id: Optional[str] = Field(
        None,
        max_length=150,
        description="Team session identifier",
        examples=["cs-team-session-2024"]
    )
    ai_provider_id: Optional[UUID] = Field(
        None,
        description="AIProvider ID (credentials) to use for this team"
    )

    is_default: bool = Field(
        default=False,
        description="Whether this should be the default team (only one per project)"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Team configuration (respond_directly, num_history_runs, etc.)",
        examples=[{
            "respond_directly": False,
            "num_history_runs": 5,
            "markdown": True
        }]
    )


class TeamUpdateRequest(BaseSchema):
    """Schema for updating an existing team."""

    name: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated team name"
    )
    ai_provider_id: Optional[UUID] = Field(
        None,
        description="AIProvider ID (credentials) to use or update for this team"
    )

    model: Optional[str] = Field(
        None,
        max_length=150,
        description="Updated LLM model name (no provider prefix)"
    )
    instruction: Optional[str] = Field(
        None,
        description="Updated team instructions"
    )
    expected_output: Optional[str] = Field(
        None,
        description="Updated expected output format"
    )
    session_id: Optional[str] = Field(
        None,
        max_length=150,
        description="Updated session identifier"
    )
    is_default: Optional[bool] = Field(
        None,
        description="Updated default status"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated team configuration"
    )


class TeamResponse(BaseSchema):
    """Schema for team API responses."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(
        ...,
        max_length=255,
        description="Team name",
        examples=["Customer Support Team"]
    )
    model: Optional[str] = Field(
        None,
        max_length=150,
        description="LLM model name (no provider prefix)",
        examples=["gpt-4", "claude-3-sonnet-20240229"]
    )
    instruction: Optional[str] = Field(
        None,
        description="Team system prompt/instructions",
        examples=["You are a customer support team focused on resolving user issues efficiently..."]
    )
    expected_output: Optional[str] = Field(
        None,
        description="Expected output format description",
        examples=["Provide clear, actionable solutions with step-by-step instructions"]
    )
    session_id: Optional[str] = Field(
        None,
        max_length=150,
        description="Team session identifier",
        examples=["cs-team-session-2024"]
    )
    is_default: bool = Field(
        default=False,
        description="Whether this should be the default team (only one per project)"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Team configuration"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")


class TeamListResponse(BaseSchema):
    """Schema for paginated team list responses."""

    data: List[TeamResponse] = Field(..., description="List of teams")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


# Agent Tool Schemas
class ToggleEnabledRequest(BaseSchema):
    """Generic request to toggle enabled state for a binding."""

    enabled: bool = Field(
        ...,
        description="Whether the binding should be enabled"
    )


class AgentToolCreateRequest(BaseSchema):
    """Schema for creating agent tool bindings."""

    tool_id: UUID = Field(
        ...,
        description="Tool ID (UUID) to bind to the agent",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    enabled: bool = Field(
        default=True,
        description="Whether tool is enabled for this agent"
    )
    permissions: Optional[List[str]] = Field(
        None,
        description="Tool permissions array",
        examples=[["read", "write"]]
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Tool-specific configuration",
        examples=[{
            "api_endpoint": "https://api.search.com",
            "timeout": 30
        }]
    )


class AgentToolResponse(BaseSchema):
    """Schema for agent tool API responses (AgentToolDetail from AI service)."""

    # Base fields
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")
    id: UUID = Field(..., description="Unique identifier")
    project_id: UUID = Field(..., description="Project ID that owns the tool")

    # Tool information
    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Optional tool description")
    tool_type: str = Field(..., description="Tool type (MCP | FUNCTION)")
    transport_type: Optional[str] = Field(None, description="Transport type (e.g., http, stdio, sse)")
    endpoint: Optional[str] = Field(None, description="Endpoint URL or path")
    config: Optional[Dict[str, Any]] = Field(None, description="Tool configuration JSON object")

    # Agent-specific settings
    enabled: bool = Field(default=True, description="Whether tool is enabled for this agent")
    permissions: Optional[List[str]] = Field(None, description="Tool permissions array for this agent")
    agent_tool_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Agent-specific tool configuration (overrides tool's default config)"
    )


# Agent Schemas
class AgentCreateRequest(BaseSchema):
    """Schema for creating a new agent."""

    name: str = Field(
        ...,
        max_length=255,
        description="Agent name",
        examples=["Customer Support Agent"]
    )
    instruction: Optional[str] = Field(
        None,
        description="Agent system instruction",
        examples=["You are a helpful customer support agent..."]
    )
    model: str = Field(
        ...,
        max_length=150,
        description="LLM model name (no provider prefix), e.g., 'gpt-4', 'claude-3-sonnet-20240229'",
        examples=["gpt-4", "claude-3-sonnet-20240229"]
    )
    is_default: bool = Field(
        default=False,
        description="Whether this should be the default agent (only one per project)"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Agent configuration (temperature, max_tokens, markdown, add_datetime_to_context, etc.)",
        examples=[{
            "max_tokens": 2000,
            "temperature": 0.7,
            "markdown": True
        }]
    )
    is_remote_store_agent: bool = Field(
        default=False,
        description="Whether this is a remote agent from store"
    )
    remote_agent_url: Optional[str] = Field(
        None,
        description="URL of the remote AgentOS server"
    )
    store_agent_id: Optional[str] = Field(
        None,
        description="Agent ID in the remote store"
    )
    agent_category: AgentCategory = Field(
        default=AgentCategory.NORMAL,
        description="Agent category: normal or computer_use"
    )
    team_id: Optional[UUID] = Field(
        None,
        description="Team ID to associate the agent with (optional)"
    )
    ai_provider_id: Optional[UUID] = Field(
        None,
        description="AIProvider ID (credentials) to use for this agent"
    )

    tools: Optional[List[AgentToolCreateRequest]] = Field(
        None,
        description="Tools to bind to the agent"
    )
    collections: Optional[List[str]] = Field(
        None,
        description="Collection IDs to associate with the agent (UUID strings)",
        examples=[
            [
                "123e4567-e89b-12d3-a456-426614174000",
                "987fcdeb-51a2-43d1-9f6e-123456789abc"
            ]
        ]
    )
    workflows: Optional[List[str]] = Field(
        None,
        description="Workflow IDs to associate with the agent (UUID strings)",
        examples=[
            [
                "123e4567-e89b-12d3-a456-426614174000",
                "987fcdeb-51a2-43d1-9f6e-123456789abc"
            ]
        ]
    )
    bound_device_id: Optional[str] = Field(
        None,
        description="Device ID to bind for device control MCP connection",
        examples=["device-uuid-1"]
    )


class AgentUpdateRequest(BaseSchema):
    """Schema for updating an existing agent."""

    name: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated agent name"
    )
    team_id: Optional[UUID] = Field(
        None,
        description="Updated team ID (set to null to remove from team)"
    )
    ai_provider_id: Optional[UUID] = Field(
        None,
        description="AIProvider ID (credentials) to use or update for this agent"
    )
    instruction: Optional[str] = Field(
        None,
        description="Updated system instruction"
    )
    model: Optional[str] = Field(
        None,
        max_length=150,
        description="Updated LLM model name (no provider prefix)"
    )
    is_default: Optional[bool] = Field(
        None,
        description="Updated default status"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated agent configuration (temperature, max_tokens, markdown, add_datetime_to_context, etc.)"
    )
    is_remote_store_agent: Optional[bool] = Field(
        None,
        description="Update remote status"
    )
    remote_agent_url: Optional[str] = Field(
        None,
        description="Update remote URL"
    )
    store_agent_id: Optional[str] = Field(
        None,
        description="Update remote agent ID"
    )
    agent_category: Optional[AgentCategory] = Field(
        None,
        description="Updated agent category: normal or computer_use"
    )
    tools: Optional[List[AgentToolCreateRequest]] = Field(
        None,
        description="Updated tools to bind to the agent"
    )
    collections: Optional[List[str]] = Field(
        None,
        description="Updated collection IDs to associate with the agent (UUID strings). Replaces existing associations.",
        examples=[
            [
                "123e4567-e89b-12d3-a456-426614174000",
                "987fcdeb-51a2-43d1-9f6e-123456789abc"
            ]
        ]
    )
    workflows: Optional[List[str]] = Field(
        None,
        description="Updated workflow IDs to associate with the agent (UUID strings). Replaces existing associations.",
        examples=[
            [
                "123e4567-e89b-12d3-a456-426614174000",
                "987fcdeb-51a2-43d1-9f6e-123456789abc"
            ]
        ]
    )
    bound_device_id: Optional[str] = Field(
        None,
        description="Updated device ID to bind for device control. Set to empty string to unbind.",
        examples=["device-uuid-1"]
    )


class AgentResponse(BaseSchema):
    """Schema for agent API responses."""

    id: UUID = Field(..., description="Unique identifier")
    name: str = Field(
        ...,
        max_length=255,
        description="Agent name",
        examples=["Customer Support Agent"]
    )
    instruction: Optional[str] = Field(
        None,
        description="Agent system instruction",
        examples=["You are a helpful customer support agent..."]
    )
    model: Optional[str] = Field(
        None,
        max_length=150,
        description="LLM model name (no provider prefix)",
        examples=["gpt-4", "claude-3-sonnet-20240229"]
    )
    is_default: bool = Field(
        default=False,
        description="Whether this should be the default agent (only one per project)"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Agent configuration (temperature, max_tokens, markdown, add_datetime_to_context, etc.)",
        examples=[{
            "max_tokens": 2000,
            "temperature": 0.7,
            "markdown": True
        }]
    )
    is_remote_store_agent: bool = Field(
        default=False,
        description="Whether this is a remote agent from store"
    )
    remote_agent_url: Optional[str] = Field(
        None,
        description="URL of the remote AgentOS server"
    )
    store_agent_id: Optional[str] = Field(
        None,
        description="Agent ID in the remote store"
    )
    agent_category: AgentCategory = Field(
        default=AgentCategory.NORMAL,
        description="Agent category: normal or computer_use"
    )
    team_id: Optional[UUID] = Field(None, description="Associated team ID")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")


class AgentListResponse(BaseSchema):
    """Paginated response model for agent list endpoint with detailed agent information."""

    data: List["AgentWithDetailsResponse"] = Field(..., description="List of items")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


# Collection Response Schema (referenced by AgentWithDetails)
class AICollectionResponse(BaseSchema):
    """Schema for collection API responses in AI service context."""

    id: UUID = Field(..., description="Unique identifier")
    display_name: str = Field(
        ...,
        max_length=255,
        description="Human-readable collection name",
        examples=["Product Documentation"]
    )
    description: Optional[str] = Field(
        None,
        description="Collection description",
        examples=["Documentation for all product features and APIs"]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata (embedding model, chunk size, etc.)",
        examples=[{
            "chunk_size": 1000,
            "embedding_model": "text-embedding-ada-002"
        }]
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")


class AIWorkflowResponse(BaseSchema):
    """Schema for workflow information in agent responses."""

    id: str = Field(..., description="Workflow ID")
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    tags: List[str] = Field(default_factory=list, description="Workflow tags")
    status: str = Field(..., description="Current status")
    version: int = Field(..., description="Version number")
    updated_at: datetime = Field(..., description="Last update time")
    enabled: bool = Field(
        default=True,
        description="Whether this workflow is enabled for the current agent binding"
    )


# Detailed Response Schemas
class AgentWithDetailsResponse(AgentResponse):
    """Schema for agent response with additional details."""

    tools: List[AgentToolResponse] = Field(
        default_factory=list,
        description="Tools bound to this agent"
    )
    collections: List[AICollectionResponse] = Field(
        default_factory=list,
        description="Collections accessible to this agent"
    )
    workflows: List[AIWorkflowResponse] = Field(
        default_factory=list,
        description="Workflows accessible to this agent"
    )


class TeamWithDetailsResponse(TeamResponse):
    """Schema for team response with additional details."""

    agents: List[AgentWithDetailsResponse] = Field(
        default_factory=list,
        description="Agents belonging to this team with their tools and collections"
    )


class ManualServiceRequestEvent(BaseSchema):
    """Payload schema for manual service escalation events from AI service."""

    reason: str = Field(..., description="Reason for requesting manual assistance")
    urgency: Literal["low", "normal", "high", "urgent"] = Field(
        default="normal",
        description="Urgency level for the manual assistance request",
    )
    channel: Optional[str] = Field(
        None,
        description="Preferred manual service channel (e.g., phone/wechat/email/ticket)",
    )
    notification_type: Optional[str] = Field(
        None,
        description="Notification modality used to alert staff (e.g., sms, email, slack)",
    )
    session_id: Optional[str] = Field(
        None,
        description="Combined session identifier in the format {channel_id}@{channel_type}",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata for the request",
    )


class VisitorInfoUpdateEvent(BaseSchema):
    """Payload schema for visitor info update events."""

    session_id: Optional[str] = Field(
        None,
        description="Combined session identifier in the format {channel_id}@{channel_type}",
    )
    visitor: Dict[str, Any] = Field(
        default_factory=dict,
        description="Visitor profile attributes to update. Supports an optional 'extra_info' object for additional fields.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata for the update",
    )


class VisitorSentimentUpdateEvent(BaseSchema):
    """Payload schema for visitor sentiment update events."""

    session_id: Optional[str] = Field(
        None,
        description="Combined session identifier in the format {channel_id}@{channel_type}",
    )
    sentiment: Dict[str, Any] = Field(
        default_factory=dict,
        description="Sentiment scores including satisfaction, emotion, and optional intent",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata for the sentiment update",
    )


class VisitorTagItem(BaseSchema):
    """Schema for a single tag item with multilingual support."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Tag name (English or primary name, used for ID generation)",
    )
    name_zh: Optional[str] = Field(
        None,
        max_length=50,
        description="Tag name in Chinese",
    )


class VisitorTagEvent(BaseSchema):
    """Payload schema for visitor tagging events."""

    session_id: Optional[str] = Field(
        None,
        description="Combined session identifier in the format {channel_id}@{channel_type}",
    )
    tags: List[VisitorTagItem] = Field(
        default_factory=list,
        description="List of tags to add to the visitor, each with name and optional name_zh",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual metadata for the tagging operation",
    )


# Backward compatibility aliases
CustomerInfoUpdateEvent = VisitorInfoUpdateEvent
CustomerSentimentUpdateEvent = VisitorSentimentUpdateEvent


class AIServiceEvent(BaseSchema):
    """Envelope for generic AI service events."""

    event_type: str = Field(..., description="Event type identifier (e.g., manual_service.request)")
    user_id: Optional[str] = Field(
        None,
        description="User identifier (visitor or staff) related to the event",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event payload data",
    )


# Update forward references
AgentListResponse.model_rebuild()
