"""Service for managing LLM Provider credentials (synced from tgo-api)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_provider import LLMProvider


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
        provider_id: uuid.UUID,
    ) -> Optional[LLMProvider]:
        """Get provider by primary key ID."""
        stmt = select(LLMProvider).where(LLMProvider.id == provider_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_providers_by_alias(
        self,
        project_id: uuid.UUID,
        alias: str,
    ) -> List[LLMProvider]:
        """Get providers by project_id and alias (may return multiple)."""
        stmt = select(LLMProvider).where(
            LLMProvider.project_id == project_id,
            LLMProvider.alias == alias,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_provider(
        self,
        project_id: uuid.UUID,
        *,
        provider_id: uuid.UUID,
        alias: str,
        provider_kind: str,
        vendor: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        timeout: Optional[float] = None,
        is_active: bool = True,
    ) -> LLMProvider:
        """Create or update a provider by ID (primary key)."""
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
                organization=payload.get("organization"),
                timeout=payload.get("timeout"),
                is_active=payload.get("is_active", True),
            )
            synced.append(provider)
        await self.db.commit()
        return synced

