"""Service for managing LLM Model metadata (synced from tgo-api)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel


class LLMModelService:
    """Application service for LLMModel CRUD and sync operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_models(
        self,
        provider_id: Optional[uuid.UUID] = None,
        model_type: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[LLMModel]:
        stmt = select(LLMModel)
        if provider_id:
            stmt = stmt.where(LLMModel.provider_id == provider_id)
        if model_type:
            stmt = stmt.where(LLMModel.model_type == model_type)
        if not include_inactive:
            stmt = stmt.where(LLMModel.is_active.is_(True))
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_model_by_id(
        self,
        model_id: uuid.UUID | str,
    ) -> Optional[LLMModel]:
        """Get model by primary key ID."""
        if isinstance(model_id, str):
            model_id = uuid.UUID(model_id)
        stmt = select(LLMModel).where(LLMModel.id == model_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_model(
        self,
        *,
        id: uuid.UUID | str,
        provider_id: uuid.UUID | str,
        model_id: str,
        model_name: str,
        model_type: str = "chat",
        description: Optional[str] = None,
        capabilities: Optional[dict] = None,
        context_window: Optional[int] = None,
        max_tokens: Optional[int] = None,
        is_active: bool = True,
        store_resource_id: Optional[str] = None,
    ) -> LLMModel:
        """Create or update a model by ID (primary key)."""
        if isinstance(id, str):
            id = uuid.UUID(id)
        if isinstance(provider_id, str):
            provider_id = uuid.UUID(provider_id)
            
        now = datetime.now(timezone.utc)

        # 1. Try to find by primary key ID first
        existing = await self.get_model_by_id(id)
        
        # 2. If not found by ID, try to find by (provider_id, model_id) to avoid unique constraint violation
        if not existing:
            stmt = select(LLMModel).where(
                LLMModel.provider_id == provider_id,
                LLMModel.model_id == model_id,
                LLMModel.deleted_at.is_(None)
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

        if existing:
            # Update in place
            # If we found it by (provider_id, model_id) but the ID is different, 
            # we should keep the existing ID to avoid conflicts
            existing.provider_id = provider_id
            existing.model_id = model_id
            existing.model_name = model_name
            existing.model_type = model_type
            existing.description = description
            existing.capabilities = capabilities
            existing.context_window = context_window
            existing.max_tokens = max_tokens
            existing.is_active = is_active
            existing.store_resource_id = store_resource_id
            existing.synced_at = now
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new
        model = LLMModel(
            id=id,
            provider_id=provider_id,
            model_id=model_id,
            model_name=model_name,
            model_type=model_type,
            description=description,
            capabilities=capabilities,
            context_window=context_window,
            max_tokens=max_tokens,
            is_active=is_active,
            store_resource_id=store_resource_id,
            synced_at=now,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model

    async def sync_models(
        self,
        models: Iterable[dict],
        commit: bool = True,
    ) -> List[LLMModel]:
        """Bulk upsert models.
        
        Uses model ID as the primary key for upsert logic.
        """
        synced: list[LLMModel] = []
        for payload in models:
            model = await self.upsert_model(
                id=payload["id"],
                provider_id=payload["provider_id"],
                model_id=payload["model_id"],
                model_name=payload["model_name"],
                model_type=payload.get("model_type", "chat"),
                description=payload.get("description"),
                capabilities=payload.get("capabilities"),
                context_window=payload.get("context_window"),
                max_tokens=payload.get("max_tokens"),
                is_active=payload.get("is_active", True),
                store_resource_id=payload.get("store_resource_id"),
            )
            synced.append(model)
        if commit:
            await self.db.commit()
        return synced

    async def deactivate_model(
        self,
        model_pk: uuid.UUID,
    ) -> None:
        """Deactivate a model by ID."""
        model = await self.get_model_by_id(model_pk)
        if model:
            model.is_active = False
            model.synced_at = datetime.now(timezone.utc)
            await self.db.flush()
