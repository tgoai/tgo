"""Service for managing LLM Provider credentials (synced from tgo-api)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_provider import LLMProvider
from app.models.llm_model import LLMModel


class LLMProviderService:
    """Application service for LLMProvider CRUD and sync operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_providers(
        self,
        project_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> List[LLMProvider]:
        stmt = select(LLMProvider).where(LLMProvider.project_id == project_id)
        if not include_inactive:
            stmt = stmt.where(LLMProvider.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_provider_by_id(
        self,
        provider_id: uuid.UUID | str,
    ) -> Optional[LLMProvider]:
        """Get provider by primary key ID."""
        if isinstance(provider_id, str):
            provider_id = uuid.UUID(provider_id)
        stmt = select(LLMProvider).where(LLMProvider.id == provider_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_providers_by_alias(
        self,
        project_id: uuid.UUID | str,
        alias: str,
    ) -> List[LLMProvider]:
        """Get providers by project_id and alias (may return multiple)."""
        if isinstance(project_id, str):
            project_id = uuid.UUID(project_id)
        stmt = select(LLMProvider).where(
            LLMProvider.project_id == project_id,
            LLMProvider.alias == alias,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_provider(
        self,
        project_id: uuid.UUID | str,
        *,
        provider_id: uuid.UUID | str,
        alias: str,
        provider_kind: str,
        vendor: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        organization: Optional[str] = None,
        timeout: Optional[float] = None,
        is_active: bool = True,
    ) -> LLMProvider:
        """Create or update a provider by ID (primary key)."""
        if isinstance(project_id, str):
            project_id = uuid.UUID(project_id)
        if isinstance(provider_id, str):
            provider_id = uuid.UUID(provider_id)
            
        existing = await self.get_provider_by_id(provider_id)
        now = datetime.now(timezone.utc)

        if existing:
            # Update in place
            existing.project_id = project_id
            existing.alias = alias
            existing.provider_kind = provider_kind
            existing.vendor = vendor
            existing.api_base_url = api_base_url
            # Only overwrite api_key if provided (allows partial updates without clearing)
            if api_key is not None:
                existing.api_key = api_key
            existing.default_model = default_model
            existing.organization = organization
            existing.timeout = timeout
            existing.is_active = is_active
            existing.synced_at = now
            await self.db.flush()
            await self.db.refresh(existing)
            return existing

        # Create new
        provider = LLMProvider(
            id=provider_id,
            project_id=project_id,
            alias=alias,
            provider_kind=provider_kind,
            vendor=vendor,
            api_base_url=api_base_url,
            api_key=api_key,
            default_model=default_model,
            organization=organization,
            timeout=timeout,
            is_active=is_active,
            synced_at=now,
        )
        self.db.add(provider)
        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def deactivate_provider(
        self,
        provider_id: uuid.UUID,
    ) -> None:
        """Deactivate a provider by ID."""
        provider = await self.get_provider_by_id(provider_id)
        if provider:
            provider.is_active = False
            provider.synced_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def sync_providers(
        self,
        providers: Iterable[dict],
    ) -> List[LLMProvider]:
        """Bulk upsert providers.

        For each incoming item (must include id, project_id and alias), update if exists else create.
        Uses provider ID as the primary key for upsert logic.
        """
        synced: list[LLMProvider] = []
        for payload in providers:
            project_id = payload["project_id"]
            alias = payload["alias"].strip()
            provider = await self.upsert_provider(
                project_id,
                provider_id=payload["id"],
                alias=alias,
                provider_kind=payload["provider_kind"],
                vendor=payload.get("vendor"),
                api_base_url=payload.get("api_base_url"),
                api_key=payload.get("api_key"),
                default_model=payload.get("default_model"),
                organization=payload.get("organization"),
                timeout=payload.get("timeout"),
                is_active=payload.get("is_active", True),
            )
            # Handle nested models sync
            if payload.get("models") is not None:
                from app.services.llm_model_service import LLMModelService
                model_service = LLMModelService(self.db)
                # Ensure each model has the correct provider_id and type conversion
                models_to_sync = []
                for m_payload in payload["models"]:
                    # m_payload might be a dict or a Pydantic object depending on how it's called
                    m_dict = m_payload if isinstance(m_payload, dict) else m_payload.model_dump()
                    m_dict["provider_id"] = provider.id
                    models_to_sync.append(m_dict)
                
                await model_service.sync_models(models_to_sync)
                
                # Optional: Deactivate models that are NOT in the sync payload for this provider
                synced_model_ids = [m["id"] for m in models_to_sync]
                await self.db.execute(
                    update(LLMModel)
                    .where(LLMModel.provider_id == provider.id)
                    .where(LLMModel.id.notin_(synced_model_ids))
                    .values(is_active=False, synced_at=datetime.now(timezone.utc))
                )

            synced.append(provider)
        await self.db.commit()
        return synced

