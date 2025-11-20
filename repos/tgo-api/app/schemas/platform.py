"""Platform schemas."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, computed_field

from app.models.platform import PlatformType
from app.schemas.base import BaseSchema, PaginatedResponse, SoftDeleteMixin, TimestampMixin
from app.core.config import settings


class PlatformBase(BaseSchema):
    """Base platform schema."""

    name: Optional[str] = Field(
        None,
        description="Platform name (e.g., WeChat, WhatsApp)"
    )
    type: PlatformType = Field(
        ...,
        description="Platform type from predefined enum"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Platform-specific configuration"
    )
    is_active: bool = Field(
        default=True,
        description="Whether the platform is active"
    )


class PlatformCreate(PlatformBase):
    """Schema for creating a platform."""
    pass


class PlatformUpdate(BaseSchema):
    """Schema for updating a platform."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Updated platform name"
    )
    type: Optional[PlatformType] = Field(
        None,
        description="Updated platform type"
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated platform configuration"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Updated platform active status"
    )
    ai_disabled: Optional[bool] = Field(
        None,
        description="Whether AI responses are disabled for this platform"
    )


class PlatformInDB(PlatformBase, TimestampMixin, SoftDeleteMixin):
    """Schema for platform in database."""

    id: UUID = Field(..., description="Platform ID")
    project_id: UUID = Field(..., description="Associated project ID")
    api_key: Optional[str] = Field(None, description="Platform-specific API key for integrations")

    logo_path: Optional[str] = Field(
        None,
        exclude=True,
        description="Internal relative path to logo file under PLATFORM_LOGO_UPLOAD_DIR",
    )


class PlatformListItemResponse(BaseSchema, TimestampMixin, SoftDeleteMixin):
    """Schema for platform list item response (without sensitive fields)."""

    id: UUID = Field(..., description="Platform ID")
    project_id: UUID = Field(..., description="Associated project ID")
    name: Optional[str] = Field(None, description="Platform name (may be null)")
    display_name: str = Field("", description="Display name with fallback to platform type name")
    type: PlatformType = Field(..., description="Platform type")
    is_active: bool = Field(..., description="Whether the platform is active")
    icon: Optional[str] = Field(None, description="SVG icon markup for the platform type")
    ai_disabled: Optional[bool] = Field(None, description="Whether AI responses are disabled for this platform")
    is_supported: Optional[bool] = Field(None, description="Whether this platform type is currently supported")
    name_en: Optional[str] = Field(None, description="English name of the platform type")

    @computed_field  # type: ignore[misc]
    @property
    def logo_url(self) -> Optional[str]:
        """Public URL to retrieve the platform logo via API.

        Constructed as: {API_BASE_URL}/v1/platforms/{platform_id}/logo
        Returns None if no logo is set.
        """
        path = getattr(self, "logo_path", None)
        if not path:
            return None
        base = settings.API_BASE_URL.rstrip("/")
        v1 = settings.API_V1_STR.rstrip("/")
        return f"{base}{v1}/platforms/{self.id}/logo"

    @computed_field  # type: ignore[misc]
    @property
    def chat_url(self) -> Optional[str]:
        """Chat completion URL for custom platforms.

        Constructed as: {API_BASE_URL}/v1/chat/completions
        Only returned for platforms with type='custom'.
        """
        if self.type == PlatformType.CUSTOM:
            base = settings.API_BASE_URL.rstrip("/")
            return f"{base}/v1/chat/completions"
        return None


class PlatformResponse(PlatformInDB):
    """Schema for platform detail response (with all fields including sensitive data)."""
    icon: Optional[str] = Field(None, description="SVG icon markup for the platform type")
    ai_disabled: Optional[bool] = Field(None, description="Whether AI responses are disabled for this platform")
    is_supported: Optional[bool] = Field(None, description="Whether this platform type is currently supported")
    name_en: Optional[str] = Field(None, description="English name of the platform type")
    display_name: str = Field("", description="Display name with fallback to platform type name")


    @computed_field  # type: ignore[misc]
    @property
    def logo_url(self) -> Optional[str]:
        """Public URL to retrieve the platform logo via API.

        Constructed as: {API_BASE_URL}/v1/platforms/{platform_id}/logo
        Returns None if no logo is set.
        """
        path = getattr(self, "logo_path", None)
        if not path:
            return None
        base = settings.API_BASE_URL.rstrip("/")
        v1 = settings.API_V1_STR.rstrip("/")
        return f"{base}{v1}/platforms/{self.id}/logo"

    @computed_field  # type: ignore[misc]
    @property
    def chat_url(self) -> Optional[str]:
        """Chat completion URL for custom platforms.

        Constructed as: {API_BASE_URL}/v1/chat/completions
        Only returned for platforms with type='custom'.
        """
        if self.type == PlatformType.CUSTOM:
            base = settings.API_BASE_URL.rstrip("/")
            return f"{base}/v1/chat/completions"
        return None
    
    @computed_field  # type: ignore[misc]
    @property
    def callback_url(self) -> str:
        """Webhook callback URL for this platform.

        Constructed as: {API_BASE_URL}/v1/platforms/callback/{platform_api_key}
        """
        base = settings.API_BASE_URL.rstrip("/")
        v1 = settings.API_V1_STR.rstrip("/")
        key = self.api_key or ""
        return f"{base}{v1}/platforms/callback/{key}"


class PlatformListParams(BaseSchema):
    """Parameters for listing platforms."""

    type: Optional[PlatformType] = Field(
        None,
        description="Filter platforms by type"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Filter platforms by active status"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of platforms to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of platforms to skip"
    )


class PlatformListResponse(PaginatedResponse):
    """Schema for platform list response."""

    data: list[PlatformListItemResponse] = Field(..., description="List of platforms")


class PlatformTypeDefinitionResponse(BaseSchema, TimestampMixin):
    """Schema describing platform type metadata."""

    id: UUID = Field(..., description="Platform type definition ID")
    type: str = Field(..., description="Stable identifier (e.g., wechat, website, email)")
    name: str = Field(..., description="Human-readable platform name (Chinese)")
    name_en: Optional[str] = Field(None, description="English name of the platform type")
    is_supported: bool = Field(..., description="Whether this platform type is currently supported")
    icon: Optional[str] = Field(None, description="SVG icon markup for display")
    display_name: str = Field("", description="Localized display name based on request language")


class PlatformAPIKeyResponse(BaseSchema):
    """Schema for API key regeneration responses."""

    id: UUID = Field(..., description="Platform ID")
    api_key: str = Field(..., description="Newly generated API key")
