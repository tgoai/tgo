"""AI Model catalog (global) model."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AIModel(Base):
    """Concrete AI models supported by each provider (global, not project-scoped)."""

    __tablename__ = "api_ai_models"

    # PK
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    provider_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_ai_providers.id", ondelete="CASCADE"),
        nullable=True,
        comment="Associated provider ID"
    )

    # Basic fields
    provider: Mapped[str] = mapped_column(String(50), nullable=False, comment="Provider key (openai, anthropic, dashscope, azure_openai)")
    model_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="Model identifier (e.g., gpt-4, claude-3-opus, qwen-max)")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Display name for the model")
    # chat | embedding
    model_type: Mapped[str] = mapped_column(String(20), nullable=False, default="chat", index=True, comment="Model type: chat or embedding")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Optional description of the model")

    capabilities: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, comment="Model capabilities JSON, e.g., {vision: true, function_calling: true}")
    context_window: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Context window size (tokens)")
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Maximum output tokens")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="Whether this model is enabled")

    # Relationships
    ai_provider: Mapped[Optional["AIProvider"]] = relationship("AIProvider", back_populates="models")

    # Timestamps (soft delete)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), comment="Creation timestamp")
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, comment="Soft deletion timestamp")

    def __repr__(self) -> str:  # pragma: no cover - debug repr
        return f"<AIModel(id={self.id}, provider={self.provider}, model_id={self.model_id})>"

