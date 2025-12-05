"""LLM Provider credentials synchronized from tgo-api.

This table stores per-project Large Language Model provider credentials and
configuration (api_base_url, api_key, etc.). Agents and Teams can reference a
provider record via llm_provider_id.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class LLMProvider(BaseModel):
    """LLM provider configuration for a project.

    Fields:
      - project_id: owning project
      - alias: human friendly unique key within a project (e.g. "openai-prod")
      - provider_kind: canonical kind: openai | anthropic | google | openai_compatible
      - vendor: optional vendor label (e.g. deepseek, openrouter)
      - api_base_url: optional custom base URL (for compatible vendors)
      - api_key: API key secret (plain stored; do NOT log it)
      - organization: optional org/tenant id for some providers (OpenAI)
      - timeout: optional request timeout seconds
      - is_active: whether usable
      - synced_at: last sync timestamp from tgo-api
    """

    __tablename__ = "ai_llm_providers"
    # Override BaseModel.id to require externally-provided IDs (no default)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Primary key UUID (externally provided)",
    )


    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Associated project ID",
    )

    alias: Mapped[str] = mapped_column(String(80), nullable=False, comment="Unique alias within project")
    provider_kind: Mapped[str] = mapped_column(String(40), nullable=False, comment="Provider kind: openai/anthropic/google/openai_compatible")
    vendor: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, comment="Vendor label (e.g. deepseek)")

    api_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Custom API base URL")
    api_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="API key (do NOT log)")
    organization: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Organization/tenant id")
    timeout: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Request timeout seconds")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="Whether this provider is active")

    # Synchronization timestamp
    synced_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this record was last synchronized",
    )

    # Note: No FK relationship to ai_projects by design; project_id may refer to external projects not yet synced.
    # Note: (project_id, alias) is NOT unique - multiple providers can share the same alias within a project.

    def __repr__(self) -> str:
        return f"<LLMProvider(id={self.id}, project_id={self.project_id}, alias='{self.alias}', kind='{self.provider_kind}', vendor='{self.vendor}')>"

