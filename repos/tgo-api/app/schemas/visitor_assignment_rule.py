"""Visitor Assignment Rule schemas."""

import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.base import BaseSchema


def validate_weekdays(v: Optional[List[int]]) -> Optional[List[int]]:
    """Validate weekdays list."""
    if v is None:
        return None
    for day in v:
        if day < 1 or day > 7:
            raise ValueError("Weekday must be between 1 (Monday) and 7 (Sunday)")
    return sorted(set(v))


def validate_time_format(v: Optional[str]) -> Optional[str]:
    """Validate time format HH:MM."""
    if v is None:
        return None
    if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", v):
        raise ValueError("Time must be in HH:MM format (e.g., 09:00, 18:30)")
    return v


class VisitorAssignmentRuleBase(BaseSchema):
    """Base schema for visitor assignment rule."""
    
    ai_provider_id: Optional[UUID] = Field(
        None,
        description="AI provider ID for assignment analysis"
    )
    model: Optional[str] = Field(
        None,
        max_length=100,
        description="Specific model to use (e.g., gpt-4, qwen-turbo). If null, uses provider's default"
    )
    prompt: Optional[str] = Field(
        None,
        max_length=1000,
        description="Custom prompt for assignment analysis (max 1000 chars). If null, uses system default"
    )
    llm_assignment_enabled: bool = Field(
        default=True,
        description="Whether to use LLM for automatic visitor assignment"
    )
    # Service time fields
    timezone: Optional[str] = Field(
        default="Asia/Shanghai",
        max_length=50,
        description="Timezone for service hours (e.g., Asia/Shanghai, America/New_York, Europe/London)"
    )
    service_weekdays: Optional[List[int]] = Field(
        None,
        description="Service weekdays (1=Monday, 7=Sunday), e.g., [1,2,3,4,5]"
    )
    service_start_time: Optional[str] = Field(
        None,
        max_length=5,
        description="Service start time in HH:MM format, e.g., 09:00"
    )
    service_end_time: Optional[str] = Field(
        None,
        max_length=5,
        description="Service end time in HH:MM format, e.g., 18:00"
    )
    max_concurrent_chats: Optional[int] = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent chats per staff member (1-100)"
    )
    auto_close_hours: Optional[int] = Field(
        default=48,
        ge=1,
        le=720,
        description="Auto close chat after N hours of inactivity (1-720, default 48)"
    )

    @field_validator("service_weekdays")
    @classmethod
    def check_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        return validate_weekdays(v)

    @field_validator("service_start_time", "service_end_time")
    @classmethod
    def check_time_format(cls, v: Optional[str]) -> Optional[str]:
        return validate_time_format(v)


class VisitorAssignmentRuleCreate(VisitorAssignmentRuleBase):
    """Schema for creating a visitor assignment rule."""
    pass


class VisitorAssignmentRuleUpdate(BaseSchema):
    """Schema for updating a visitor assignment rule."""
    
    ai_provider_id: Optional[UUID] = Field(
        None,
        description="Updated AI provider ID"
    )
    model: Optional[str] = Field(
        None,
        max_length=100,
        description="Updated model name"
    )
    prompt: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated prompt for assignment analysis (max 1000 chars)"
    )
    llm_assignment_enabled: Optional[bool] = Field(
        None,
        description="Whether to use LLM for automatic visitor assignment"
    )
    timezone: Optional[str] = Field(
        None,
        max_length=50,
        description="Updated timezone for service hours (e.g., Asia/Shanghai, America/New_York)"
    )
    service_weekdays: Optional[List[int]] = Field(
        None,
        description="Updated service weekdays (1=Monday, 7=Sunday)"
    )
    service_start_time: Optional[str] = Field(
        None,
        max_length=5,
        description="Updated service start time in HH:MM format"
    )
    service_end_time: Optional[str] = Field(
        None,
        max_length=5,
        description="Updated service end time in HH:MM format"
    )
    max_concurrent_chats: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Updated maximum concurrent chats per staff (1-100)"
    )
    auto_close_hours: Optional[int] = Field(
        None,
        ge=1,
        le=720,
        description="Updated auto close hours (1-720)"
    )

    @field_validator("service_weekdays")
    @classmethod
    def check_weekdays(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        return validate_weekdays(v)

    @field_validator("service_start_time", "service_end_time")
    @classmethod
    def check_time_format(cls, v: Optional[str]) -> Optional[str]:
        return validate_time_format(v)


class VisitorAssignmentRuleResponse(BaseSchema):
    """Schema for visitor assignment rule response."""
    
    id: UUID = Field(..., description="Rule ID")
    project_id: UUID = Field(..., description="Associated project ID")
    ai_provider_id: Optional[UUID] = Field(None, description="AI provider ID")
    model: Optional[str] = Field(None, description="Model name")
    prompt: Optional[str] = Field(None, description="Custom prompt")
    effective_prompt: str = Field(..., description="Effective prompt (custom or default)")
    llm_assignment_enabled: bool = Field(..., description="Whether to use LLM for automatic visitor assignment")
    timezone: Optional[str] = Field(None, description="Timezone for service hours")
    service_weekdays: Optional[List[int]] = Field(None, description="Service weekdays (1=Monday, 7=Sunday)")
    service_start_time: Optional[str] = Field(None, description="Service start time in HH:MM format")
    service_end_time: Optional[str] = Field(None, description="Service end time in HH:MM format")
    max_concurrent_chats: Optional[int] = Field(None, description="Maximum concurrent chats per staff")
    auto_close_hours: Optional[int] = Field(None, description="Auto close chat after N hours")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
