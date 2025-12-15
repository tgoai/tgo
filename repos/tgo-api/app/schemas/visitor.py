"""Visitor schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.core.config import settings
from app.models.platform import PlatformType
from app.schemas.base import BaseSchema, PaginatedResponse, SoftDeleteMixin, TimestampMixin
from app.schemas.tag import TagResponse


def _resolve_avatar_url(avatar_url: Optional[str]) -> Optional[str]:
    """
    Resolve avatar URL to full URL.
    
    - If None or empty, return None
    - If already a full URL (http:// or https://), return as-is
    - If relative path (starts with /), prepend API_BASE_URL
    """
    if not avatar_url:
        return None
    if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
        return avatar_url
    # Relative path: prepend API_BASE_URL
    base_url = settings.API_BASE_URL.rstrip("/")
    return f"{base_url}{avatar_url}"



class VisitorAIProfileResponse(BaseSchema):
    """AI persona representation for a visitor."""

    persona_tags: List[str] = Field(default_factory=list, description="AI generated persona tags")
    summary: Optional[dict] = Field(None, description="Structured persona details")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class VisitorAIInsightResponse(BaseSchema):
    """AI derived insight scores for a visitor."""

    satisfaction_score: Optional[int] = Field(None, description="Satisfaction score on a 0-5 scale (0=unknown)")
    emotion_score: Optional[int] = Field(None, description="Emotion score on a 0-5 scale (0=unknown)")
    intent: Optional[str] = Field(None, description="Intent classification (e.g., purchase, inquiry, complaint, support)")
    insight_summary: Optional[str] = Field(None, description="Short insight summary")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional insight metadata",
        alias="insight_metadata",
    )
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class VisitorSystemInfoResponse(BaseSchema):
    """System metadata associated with a visitor."""

    platform: Optional[str] = Field(None, description="Acquisition platform/channel")
    source_detail: Optional[str] = Field(None, description="Additional source detail")
    browser: Optional[str] = Field(None, description="Browser information")
    operating_system: Optional[str] = Field(None, description="Operating system information")
    first_seen_at: Optional[datetime] = Field(None, description="First recorded session timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class VisitorSystemInfoRequest(BaseSchema):
    """Incoming payload carrying visitor system metadata."""

    source_detail: Optional[str] = Field(None, max_length=255, description="Additional source context")
    browser: Optional[str] = Field(None, max_length=100, description="Visitor browser name/version")
    operating_system: Optional[str] = Field(None, max_length=100, description="Visitor operating system")


class VisitorActivityResponse(BaseSchema):
    """Recent activity entry for a visitor."""

    id: UUID = Field(..., description="Activity ID")
    activity_type: str = Field(..., description="Categorised activity type")
    title: str = Field(..., description="Activity title")
    description: Optional[str] = Field(None, description="Activity description")
    occurred_at: datetime = Field(..., description="Time when the activity occurred")
    duration_seconds: Optional[int] = Field(None, description="Activity duration in seconds, when applicable")
    context: Optional[dict] = Field(None, description="Optional context for the activity")




class VisitorBase(BaseSchema):
    """Base visitor schema."""

    platform_open_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Visitor unique identifier on this platform"
    )
    name: Optional[str] = Field(
        None,
        max_length=100,
        description="Visitor real name"
    )
    nickname: Optional[str] = Field(
        None,
        max_length=100,
        description="Visitor nickname on this platform (English)"
    )
    nickname_zh: Optional[str] = Field(
        None,
        max_length=100,
        description="Visitor nickname in Chinese"
    )
    avatar_url: Optional[str] = Field(
        None,
        max_length=255,
        description="Visitor avatar URL on this platform"
    )
    phone_number: Optional[str] = Field(
        None,
        max_length=30,
        description="Visitor phone number on this platform"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Visitor email on this platform"
    )
    company: Optional[str] = Field(
        None,
        max_length=255,
        description="Visitor company or organization"
    )
    job_title: Optional[str] = Field(
        None,
        max_length=255,
        description="Visitor job title or position"
    )
    source: Optional[str] = Field(
        None,
        max_length=255,
        description="Acquisition source describing how the visitor found us"
    )
    note: Optional[str] = Field(
        None,
        description="Additional notes about the visitor"
    )
    custom_attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom attribute key/value pairs (supports nested structures)"
    )
    timezone: Optional[str] = Field(
        None,
        max_length=50,
        description="Visitor timezone (e.g., 'Asia/Shanghai', 'America/New_York')"
    )
    language: Optional[str] = Field(
        None,
        max_length=10,
        description="Visitor preferred language code (e.g., 'en', 'zh-CN')"
    )


class VisitorCreate(VisitorBase):
    """Schema for creating a visitor."""

    # Platform selection - either platform_id or platform_type is required
    platform_id: Optional[UUID] = Field(
        None,
        description="Associated platform ID (required if platform_type not provided)"
    )
    platform_type: Optional[PlatformType] = Field(
        None,
        description="Platform type to use default platform (required if platform_id not provided)"
    )
    ip_address: Optional[str] = Field(
        None,
        max_length=45,
        description="Visitor IP address (if not provided, will be extracted from request headers)"
    )


class VisitorAttributesUpdate(BaseSchema):
    """Schema for updating visitor profile attributes."""

    name: Optional[str] = Field(
        None,
        max_length=100,
        description="Updated visitor real name"
    )
    nickname: Optional[str] = Field(
        None,
        max_length=100,
        description="Updated visitor nickname (English)"
    )
    nickname_zh: Optional[str] = Field(
        None,
        max_length=100,
        description="Updated visitor nickname in Chinese"
    )
    avatar_url: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated visitor avatar URL"
    )
    phone_number: Optional[str] = Field(
        None,
        max_length=30,
        description="Updated visitor phone number"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Updated visitor email"
    )
    company: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated visitor company or organization"
    )
    job_title: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated visitor job title or position"
    )
    source: Optional[str] = Field(
        None,
        max_length=255,
        description="Updated acquisition source"
    )
    note: Optional[str] = Field(
        None,
        description="Updated notes about the visitor"
    )
    custom_attributes: Optional[dict[str, Any]] = Field(
        None,
        description="Updated custom attribute key/value pairs"
    )
    timezone: Optional[str] = Field(
        None,
        max_length=50,
        description="Updated visitor timezone"
    )
    language: Optional[str] = Field(
        None,
        max_length=10,
        description="Updated visitor language code"
    )
    ip_address: Optional[str] = Field(
        None,
        max_length=45,
        description="Updated visitor IP address"
    )


class VisitorUpdate(VisitorAttributesUpdate):
    """Schema for updating a visitor."""

    is_online: Optional[bool] = Field(
        None,
        description="Updated visitor online status"
    )
    ai_disabled: Optional[bool] = Field(
        None,
        description="Whether AI responses are disabled for this visitor"
    )
    last_visit_time: Optional[datetime] = Field(
        None,
        description="Updated last visit time"
    )
    last_offline_time: Optional[datetime] = Field(
        None,
        description="Updated last offline time"
    )


class VisitorInDB(VisitorBase, TimestampMixin, SoftDeleteMixin):
    """Schema for visitor in database."""

    id: UUID = Field(..., description="Visitor ID")
    project_id: UUID = Field(..., description="Associated project ID")
    platform_id: UUID = Field(..., description="Associated platform ID")
    first_visit_time: datetime = Field(..., description="When the visitor first accessed the system")
    last_visit_time: datetime = Field(..., description="Visitor most recent activity/visit time")
    last_offline_time: Optional[datetime] = Field(None, description="Most recent time visitor went offline")
    is_online: bool = Field(..., description="Whether the visitor is currently online/active")
    service_status: str = Field(
        default="new",
        description="Visitor service status: new, queued, active, closed"
    )
    ip_address: Optional[str] = Field(
        None,
        description="Visitor IP address (supports both IPv4 and IPv6)"
    )
    geo_country: Optional[str] = Field(
        None,
        description="Country name derived from IP address"
    )
    geo_country_code: Optional[str] = Field(
        None,
        description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CN')"
    )
    geo_region: Optional[str] = Field(
        None,
        description="Region/state/province name"
    )
    geo_city: Optional[str] = Field(
        None,
        description="City name"
    )
    geo_isp: Optional[str] = Field(
        None,
        description="Internet Service Provider (available with ip2region)"
    )


class VisitorResponse(VisitorInDB):
    """Schema for visitor response with related entities."""

    platform_type: Optional[PlatformType] = Field(
        None,
        description="Associated platform type (e.g., website, wechat)"
    )
    ai_disabled: Optional[bool] = Field(
        None,
        description="Whether AI responses are disabled for this visitor"
    )
    display_nickname: Optional[str] = Field(
        None,
        description="Display nickname based on client language (nickname_zh for zh, nickname for others)"
    )
    assigned_staff_id: Optional[UUID] = Field(
        None,
        description="Currently assigned staff ID (from active session)"
    )
    tags: List[TagResponse] = Field(default_factory=list, description="Associated visitor tags")
    ai_profile: Optional[VisitorAIProfileResponse] = Field(None, description="AI persona data")
    ai_insights: Optional[VisitorAIInsightResponse] = Field(None, description="AI insight metrics")
    system_info: Optional[VisitorSystemInfoResponse] = Field(None, description="System metadata")
    recent_activities: List[VisitorActivityResponse] = Field(default_factory=list, description="Recent visitor activities")

    @field_validator("avatar_url", mode="after")
    @classmethod
    def resolve_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        """Resolve relative avatar URL to full URL."""
        return _resolve_avatar_url(v)


class VisitorBasicResponse(BaseSchema):
    """Lightweight visitor response with essential fields only."""

    id: UUID = Field(..., description="Visitor ID")
    name: Optional[str] = Field(None, description="Visitor real name")
    nickname: Optional[str] = Field(None, description="Visitor nickname on this platform (English)")
    nickname_zh: Optional[str] = Field(None, description="Visitor nickname in Chinese")
    display_nickname: Optional[str] = Field(
        None,
        description="Display nickname based on client language (nickname_zh for zh, nickname for others)"
    )
    avatar_url: Optional[str] = Field(None, description="Visitor avatar URL on this platform")
    platform_open_id: str = Field(..., description="Visitor unique identifier on this platform")
    platform_id: UUID = Field(..., description="Associated platform ID")
    platform_type: Optional[PlatformType] = Field(
        None, description="Associated platform type (e.g., website, wechat)"
    )
    ai_disabled: Optional[bool] = Field(
        None, description="Whether AI responses are disabled for this visitor"
    )
    is_online: bool = Field(..., description="Whether the visitor is currently online/active")
    service_status: str = Field(
        default="new",
        description="Visitor service status: new, queued, active, closed"
    )
    timezone: Optional[str] = Field(
        None, description="Visitor timezone (e.g., 'Asia/Shanghai', 'America/New_York')"
    )
    language: Optional[str] = Field(
        None, description="Visitor preferred language code (e.g., 'en', 'zh-CN')"
    )
    ip_address: Optional[str] = Field(
        None, description="Visitor IP address (supports both IPv4 and IPv6)"
    )
    geo_country: Optional[str] = Field(
        None, description="Country name derived from IP address"
    )
    geo_country_code: Optional[str] = Field(
        None, description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CN')"
    )
    geo_region: Optional[str] = Field(
        None, description="Region/state/province name"
    )
    geo_city: Optional[str] = Field(
        None, description="City name"
    )
    geo_isp: Optional[str] = Field(
        None, description="Internet Service Provider (available with ip2region)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @field_validator("avatar_url", mode="after")
    @classmethod
    def resolve_avatar_url(cls, v: Optional[str]) -> Optional[str]:
        """Resolve relative avatar URL to full URL."""
        return _resolve_avatar_url(v)


class VisitorListParams(BaseSchema):
    """Parameters for listing visitors."""

    platform_id: Optional[UUID] = Field(
        None,
        description="Filter visitors by platform ID"
    )
    is_online: Optional[bool] = Field(
        None,
        description="Filter visitors by online status"
    )
    search: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Search visitors by name, nickname, or platform_open_id"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of visitors to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of visitors to skip"
    )


class VisitorListResponse(PaginatedResponse):
    """Schema for visitor list response."""

    data: list[VisitorResponse] = Field(..., description="List of visitors")


class VisitorAvatarUploadResponse(BaseSchema):
    """Response schema for visitor avatar upload."""

    visitor_id: UUID = Field(..., description="Visitor ID")
    avatar_url: str = Field(..., description="Avatar URL (relative path for local storage)")
    file_name: str = Field(..., description="Original file name")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type of the file")
    uploaded_at: datetime = Field(..., description="Upload timestamp")


# Helper functions for language-aware display

def resolve_display_nickname(
    nickname: Optional[str],
    nickname_zh: Optional[str],
    language: str = "en",
) -> Optional[str]:
    """
    Resolve display nickname based on user language.

    Args:
        nickname: English nickname
        nickname_zh: Chinese nickname
        language: User language code ('zh' or 'en')

    Returns:
        nickname_zh if language is 'zh', otherwise nickname
    """
    if language == "zh":
        return nickname_zh or nickname
    return nickname or nickname_zh


def resolve_visitor_display_name(
    name: Optional[str],
    nickname: Optional[str],
    nickname_zh: Optional[str],
    language: str = "en",
    fallback: str = "Unknown Visitor",
) -> str:
    """
    Resolve visitor display name based on user language.

    Priority:
    1. name (if exists)
    2. nickname_zh (if language is 'zh')
    3. nickname (default)
    4. fallback value

    Args:
        name: Visitor's real name
        nickname: English nickname
        nickname_zh: Chinese nickname
        language: User language code ('zh' or 'en')
        fallback: Fallback value if no name available

    Returns:
        The resolved display name
    """
    if name:
        return name
    if language == "zh":
        return nickname_zh or nickname or fallback
    return nickname or nickname_zh or fallback


def set_visitor_display_nickname(
    response: Union[VisitorResponse, VisitorBasicResponse],
    language: str = "en",
) -> Union[VisitorResponse, VisitorBasicResponse]:
    """
    Set display_nickname field on visitor response based on language.

    Args:
        response: Visitor response object
        language: User language code ('zh' or 'en')

    Returns:
        The same response object with display_nickname set
    """
    response.display_nickname = resolve_display_nickname(
        response.nickname,
        response.nickname_zh,
        language,
    )
    return response


def set_visitor_list_display_nickname(
    responses: List[Union[VisitorResponse, VisitorBasicResponse]],
    language: str = "en",
) -> List[Union[VisitorResponse, VisitorBasicResponse]]:
    """
    Set display_nickname field on a list of visitor responses.

    Args:
        responses: List of visitor response objects
        language: User language code ('zh' or 'en')

    Returns:
        The same list with display_nickname set on each item
    """
    for response in responses:
        set_visitor_display_nickname(response, language)
    return responses
