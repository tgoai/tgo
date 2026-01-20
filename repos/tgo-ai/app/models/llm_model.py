"""LLM Model metadata synchronized from tgo-api.

Each LLMProvider can have multiple LLMModels.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.llm_provider import LLMProvider


class LLMModel(BaseModel):
    """Specific AI model supported by an LLMProvider.
    
    Examples: gpt-4, claude-3-opus, qwen-max.
    """

    __tablename__ = "ai_llm_models"

    # Override BaseModel.id to require externally-provided IDs (no default)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Primary key UUID (externally provided)",
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_llm_providers.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated provider ID",
    )

    model_id: Mapped[str] = mapped_column(
        String(100), 
        nullable=False, 
        comment="Model identifier (e.g., gpt-4, claude-3-opus, qwen-max)"
    )
    
    model_name: Mapped[str] = mapped_column(
        String(100), 
        nullable=False, 
        comment="Display name for the model"
    )
    
    # chat | embedding
    model_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="chat", 
        comment="Model type: chat or embedding"
    )
    
    description: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True, 
        comment="Optional description of the model"
    )

    capabilities: Mapped[Optional[dict]] = mapped_column(
        JSONB, 
        nullable=True, 
        comment="Model capabilities JSON, e.g., {vision: true, function_calling: true}"
    )
    
    context_window: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True, 
        comment="Context window size (tokens)"
    )
    
    max_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True, 
        comment="Maximum output tokens"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True, 
        comment="Whether this model is enabled"
    )
    
    store_resource_id: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True, 
        comment="Store resource ID for models installed from store"
    )

    # Synchronization timestamp
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this record was last synchronized",
    )

    # Relationships
    llm_provider: Mapped["LLMProvider"] = relationship("LLMProvider", back_populates="models")

    def __repr__(self) -> str:
        return f"<LLMModel(id={self.id}, model_id='{self.model_id}', type='{self.model_type}')>"
