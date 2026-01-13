"""LLM Provider (AIProvider) model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIProvider(Base):
    """Configuration for a Large Language Model provider per project.

    Examples of provider: "openai", "anthropic", "dashscope", "azure_openai".
    """

    __tablename__ = "api_ai_providers"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated project ID for multi-tenant isolation",
    )

    # Basic fields
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Provider key (e.g., openai, anthropic, dashscope, azure_openai)",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name / alias shown in UI",
    )
    api_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="API key/credential used to call the provider",
    )
    api_base_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Base URL for the provider API (if applicable)",
    )

    default_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Default model identifier to use",
    )

    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional provider-specific configuration",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this provider configuration is enabled",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        comment="Creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Soft deletion timestamp",
    )

    # Sync metadata
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Last synced to AI service timestamp",
    )
    sync_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Sync status: pending|synced|failed",
    )
    sync_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last sync error message",
    )


    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="ai_providers", lazy="select")
    models: Mapped[List["AIModel"]] = relationship("AIModel", back_populates="ai_provider", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AIProvider(id={self.id}, provider='{self.provider}', name='{self.name}')>"

