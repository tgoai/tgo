"""Pydantic schemas for LLMModel API."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class LLMModelBase(BaseModel):
    model_id: str = Field(..., description="Model identifier (e.g., gpt-4)")
    model_name: str = Field(..., description="Display name for the model")
    model_type: str = Field(default="chat", description="chat | embedding")
    description: Optional[str] = None
    capabilities: Optional[dict] = None
    context_window: Optional[int] = None
    max_tokens: Optional[int] = None
    is_active: bool = True
    store_resource_id: Optional[str] = Field(None, description="Store resource ID for models installed from store")


class LLMModelUpsert(LLMModelBase):
    id: UUID = Field(..., description="Primary key UUID provided by tgo-api")
    provider_id: UUID = Field(..., description="Associated provider ID")


class LLMModelResponse(LLMModelBase):
    id: UUID
    provider_id: UUID
    synced_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_model(cls, m) -> "LLMModelResponse":
        return cls(
            id=m.id,
            provider_id=m.provider_id,
            model_id=m.model_id,
            model_name=m.model_name,
            model_type=m.model_type,
            description=m.description,
            capabilities=m.capabilities,
            context_window=m.context_window,
            max_tokens=m.max_tokens,
            is_active=m.is_active,
            store_resource_id=m.store_resource_id,
            synced_at=m.synced_at,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


class LLMModelSyncRequest(BaseModel):
    models: List[LLMModelUpsert]


class LLMModelSyncResponse(BaseModel):
    data: List[LLMModelResponse]
