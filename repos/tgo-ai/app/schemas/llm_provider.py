"""Pydantic schemas for LLMProvider API."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from uuid import UUID

from app.schemas.llm_model import LLMModelUpsert, LLMModelResponse


def mask_api_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


class LLMProviderBase(BaseModel):
    provider_kind: str = Field(..., description="openai | anthropic | google | openai_compatible")
    vendor: Optional[str] = Field(None, description="Vendor label, e.g. deepseek")
    api_base_url: Optional[str] = Field(None, description="Custom API base URL for compatible vendors")
    default_model: Optional[str] = Field(None, description="Default model identifier (e.g., gpt-4o, qwen-plus)")
    organization: Optional[str] = Field(None, description="Organization/Tenant identifier")
    timeout: Optional[float] = Field(None, description="Request timeout seconds")
    is_active: bool = Field(default=True, description="Whether provider is active")


class LLMProviderUpsert(LLMProviderBase):
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "project_id": "00000000-0000-0000-0000-000000000000",
                "alias": "openai-prod",
                "provider_kind": "openai",
                "vendor": "openai",
                "api_key": "sk_...",
                "timeout": 30,
                "is_active": True,
            }
        ]
    })
    project_id: UUID = Field(..., description="Project ID owning this provider")
    id: UUID = Field(..., description="Primary key UUID provided by tgo-api")

    alias: str = Field(..., min_length=1, max_length=80)
    api_key: Optional[str] = Field(None, description="API key (write-only)")
    models: Optional[List[LLMModelUpsert]] = Field(default=None, description="Associated models to sync")


class LLMProviderResponse(LLMProviderBase):
    id: str
    alias: str
    api_key_masked: Optional[str] = Field(None, description="Masked API key")
    models: List[LLMModelResponse] = Field(default_factory=list)
    synced_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_model(cls, m) -> "LLMProviderResponse":
        return cls(
            id=str(m.id),
            alias=m.alias,
            provider_kind=m.provider_kind,
            vendor=m.vendor,
            api_base_url=m.api_base_url,
            default_model=m.default_model,
            organization=m.organization,
            timeout=m.timeout,
            is_active=m.is_active,
            api_key_masked=mask_api_key(m.api_key),
            models=[LLMModelResponse.from_orm_model(mod) for mod in m.models] if "models" in m.__dict__ and m.models else [],
            synced_at=m.synced_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class LLMProviderListResponse(BaseModel):
    data: List[LLMProviderResponse]


class LLMProviderSyncRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "examples": [
            {
                "providers": [
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "project_id": "00000000-0000-0000-0000-000000000000",
                        "alias": "openai-prod",
                        "provider_kind": "openai",
                        "vendor": "openai",
                        "api_key": "sk_..."
                    },
                    {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "project_id": "00000000-0000-0000-0000-000000000000",
                        "alias": "deepseek",
                        "provider_kind": "openai_compatible",
                        "vendor": "deepseek",
                        "api_base_url": "https://api.deepseek.com/v1",
                        "api_key": "ds_..."
                    }
                ]
            }
        ]
    })
    providers: List[LLMProviderUpsert]


class LLMProviderSyncResponse(BaseModel):
    data: List[LLMProviderResponse]

