"""AI Provider (LLM Provider) schemas."""

from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema, PaginatedResponse, SoftDeleteMixin, TimestampMixin


class AIProviderConfigBase(BaseSchema):
    """Base config fields shared by create/update/response (excludes secret)."""

    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Provider key (e.g., openai, anthropic, dashscope, azure_openai)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name / alias shown in UI",
    )
    api_base_url: Optional[str] = Field(
        None,
        max_length=255,
        description="Base URL for the provider API (if applicable)",
    )
    available_models: Optional[list[str]] = Field(
        default_factory=list,
        description="List of available model identifiers for this provider (max 50)",
    )
    default_model: Optional[str] = Field(
        None,
        max_length=100,
        description="Default model identifier to use",
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional provider-specific configuration",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this provider configuration is enabled",
    )


class AIProviderCreate(AIProviderConfigBase):
    """Schema for creating an AI provider."""

    api_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="API key/credential used to call the provider",
    )


class AIProviderUpdate(BaseSchema):
    """Schema for updating an AI provider."""

    provider: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = Field(None, min_length=1, max_length=255)
    api_base_url: Optional[str] = Field(None, max_length=255)
    available_models: Optional[list[str]] = Field(None)
    default_model: Optional[str] = Field(None, max_length=100)
    config: Optional[Dict[str, Any]] = Field(None)
    is_active: Optional[bool] = Field(None)


class AIProviderResponse(AIProviderConfigBase, TimestampMixin, SoftDeleteMixin):
    """Public response model for AI provider (secrets masked)."""

    id: UUID = Field(..., description="AI Provider ID")
    project_id: UUID = Field(..., description="Associated project ID")
    has_api_key: bool = Field(..., description="Whether secret is set")
    api_key_masked: Optional[str] = Field(None, description="Masked API key, only last 4 visible")

    # Store metadata
    store_resource_id: Optional[str] = Field(None, description="Store resource ID if provider is from store")
    is_from_store: bool = Field(False, description="Whether this provider was created from store")

    # Sync metadata (read-only)
    last_synced_at: Optional[datetime] = Field(None, description="Last time synced to tgo-ai")
    sync_status: Optional[str] = Field(None, description="Sync status: pending|synced|failed")
    sync_error: Optional[str] = Field(None, description="Last sync error message")


class AIProviderListParams(BaseSchema):
    """Query parameters for listing AI providers."""

    provider: Optional[str] = Field(None, description="Filter by provider key")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    search: Optional[str] = Field(
        None,
        description="Search in name or default_model",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class AIProviderListResponse(PaginatedResponse):
    """Paginated list response for AI providers."""

    data: list[AIProviderResponse] = Field(..., description="List of AI providers")

