"""Setup schemas for system initialization."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


class SetupStatusResponse(BaseSchema):
    """Response schema for setup status check."""

    is_installed: bool = Field(
        ...,
        description="Whether the system has completed initial installation"
    )
    has_admin: bool = Field(
        ...,
        description="Whether at least one admin account exists"
    )
    has_user_staff: bool = Field(
        ...,
        description="Whether at least one non-admin staff (user role) exists"
    )
    has_llm_config: bool = Field(
        ...,
        description="Whether at least one LLM provider is configured and enabled"
    )
    skip_llm_config: bool = Field(
        ...,
        description="Whether LLM configuration step was explicitly skipped"
    )
    setup_completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when setup was completed (if applicable)"
    )


class CreateAdminRequest(BaseSchema):
    """Request schema for creating the first admin account."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Admin password (will be hashed, minimum 8 characters)"
    )
    nickname: Optional[str] = Field(
        None,
        max_length=100,
        description="Admin display name (optional)"
    )
    project_name: str = Field(
        default="Default Project",
        min_length=1,
        max_length=255,
        description="Name for the default project"
    )
    skip_llm_config: bool = Field(
        default=False,
        description="Whether to skip LLM configuration during setup (can be configured later)"
    )


class CreateAdminResponse(BaseSchema):
    """Response schema for admin creation."""

    id: UUID = Field(..., description="Created admin staff ID")
    username: str = Field(..., description="Admin username")
    nickname: Optional[str] = Field(None, description="Admin display name")
    project_id: UUID = Field(..., description="Associated project ID")
    project_name: str = Field(..., description="Project name")
    created_at: datetime = Field(..., description="Creation timestamp")


class ConfigureLLMRequest(BaseSchema):
    """Request schema for configuring LLM provider."""

    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Provider name (e.g., 'openai', 'anthropic', 'azure_openai', 'dashscope')"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name for this provider configuration"
    )
    api_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="API key for the provider (will be encrypted)"
    )
    api_base_url: Optional[str] = Field(
        None,
        max_length=255,
        description="Custom API base URL (optional, for proxies or custom endpoints)"
    )
    available_models: List[str] = Field(
        default_factory=list,
        description="List of available model identifiers"
    )
    default_model: Optional[str] = Field(
        None,
        max_length=100,
        description="Default model to use"
    )
    is_active: bool = Field(
        default=True,
        description="Whether this provider configuration is enabled"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional provider-specific configuration (e.g., temperature, max_tokens)"
    )

    @field_validator('available_models')
    @classmethod
    def validate_available_models(cls, v: List[str]) -> List[str]:
        """Validate available_models list."""
        if len(v) > 50:
            raise ValueError("Maximum 50 models allowed")
        return v


class ConfigureLLMResponse(BaseSchema):
    """Response schema for LLM configuration."""

    id: UUID = Field(..., description="AI Provider configuration ID")
    provider: str = Field(..., description="Provider name")
    name: str = Field(..., description="Display name")
    default_model: Optional[str] = Field(None, description="Default model")
    is_active: bool = Field(..., description="Whether this configuration is enabled")
    project_id: UUID = Field(..., description="Associated project ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class SetupCheckResult(BaseSchema):
    """Individual check result for setup verification."""

    passed: bool = Field(..., description="Whether the check passed")
    message: str = Field(..., description="Check result message")


class VerifySetupResponse(BaseSchema):
    """Response schema for setup verification."""

    is_valid: bool = Field(
        ...,
        description="Whether the installation is valid and complete"
    )
    checks: Dict[str, SetupCheckResult] = Field(
        ...,
        description="Individual check results"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors found"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings"
    )




class SkipLLMConfigResponse(BaseSchema):
    """Response schema for skipping LLM configuration during setup."""

    message: str = Field(..., description="Success message for skip LLM operation")
    is_installed: bool = Field(
        ...,
        description="Updated installation status after skipping LLM configuration",
    )
    setup_completed_at: datetime = Field(
        ...,
        description="Timestamp when setup was marked as completed",
    )


class StaffCreateItem(BaseSchema):
    """Single staff item for batch creation."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Staff username for login (unique)"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Staff password (will be hashed)"
    )
    name: Optional[str] = Field(
        None,
        max_length=100,
        description="Staff real name"
    )
    nickname: Optional[str] = Field(
        None,
        max_length=100,
        description="Staff display name"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Staff description for LLM assignment"
    )


class BatchCreateStaffRequest(BaseSchema):
    """Request schema for batch creating staff members during setup."""

    staff_list: List[StaffCreateItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of staff members to create (max 100)"
    )


class StaffCreatedItem(BaseSchema):
    """Created staff item response."""

    id: UUID = Field(..., description="Staff ID")
    username: str = Field(..., description="Staff username")
    name: Optional[str] = Field(None, description="Staff real name")
    nickname: Optional[str] = Field(None, description="Staff display name")
    created_at: datetime = Field(..., description="Creation timestamp")


class BatchCreateStaffResponse(BaseSchema):
    """Response schema for batch staff creation."""

    created_count: int = Field(..., description="Number of staff members created")
    staff_list: List[StaffCreatedItem] = Field(..., description="List of created staff members")
    skipped_usernames: List[str] = Field(
        default_factory=list,
        description="Usernames that were skipped (already exist)"
    )
