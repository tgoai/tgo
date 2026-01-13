"""AI Model schemas (global catalog)."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, PaginatedResponse, SoftDeleteMixin, TimestampMixin


class AIModelBase(BaseSchema):
    provider: str = Field(..., min_length=1, max_length=50, description="Provider key (openai, anthropic, dashscope, azure_openai)")
    model_id: str = Field(..., min_length=1, max_length=100, description="Model identifier (e.g., gpt-4, claude-3-opus)")
    model_name: str = Field(..., min_length=1, max_length=100, description="Display name for the model")
    model_type: str = Field(
        default="chat",
        pattern="^(chat|embedding)$",
        description="Model type: chat or embedding",
    )

    description: Optional[str] = Field(None, max_length=255, description="Model description")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Capabilities JSON (e.g., {vision: true})")
    context_window: Optional[int] = Field(None, ge=1, description="Context window size in tokens")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum output tokens")
    is_active: bool = Field(default=True, description="Whether this model is enabled")


class AIModelCreate(AIModelBase):
    """Create a new AI model entry."""
    pass


class AIModelUpdate(BaseSchema):
    provider: Optional[str] = Field(None, min_length=1, max_length=50)
    model_id: Optional[str] = Field(None, min_length=1, max_length=100)
    model_name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_type: Optional[str] = Field(None, pattern="^(chat|embedding)$")
    description: Optional[str] = Field(None, max_length=255)
    capabilities: Optional[Dict[str, Any]] = Field(None)
    context_window: Optional[int] = Field(None, ge=1)
    max_tokens: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = Field(None)


class AIModelResponse(AIModelBase, TimestampMixin, SoftDeleteMixin):
    id: UUID = Field(..., description="AI Model ID")


class AIModelListParams(BaseSchema):
    provider: Optional[str] = Field(None, description="Filter by provider")
    model_type: Optional[str] = Field(None, pattern="^(chat|embedding)$", description="Filter by model type")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    search: Optional[str] = Field(None, description="Search model_id or model_name")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class AIModelListResponse(PaginatedResponse):
    data: list[AIModelResponse] = Field(..., description="List of AI models")


class AIModelWithProvider(BaseSchema):
    id: UUID
    model_id: str
    model_name: str
    model_type: str
    provider_id: UUID
    provider_name: str
    provider_kind: str
    description: Optional[str] = None
    context_window: Optional[int] = None
    is_active: bool


class AIModelWithProviderListResponse(PaginatedResponse):
    data: list[AIModelWithProvider] = Field(..., description="List of AI models with provider info")

