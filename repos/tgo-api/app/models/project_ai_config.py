"""Project AI default models configuration (per project)."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProjectAIConfig(Base):
    """Default AI models for a given project (one-to-one with Project).

    Stores default chat and embedding provider/model selections.
    """

    __tablename__ = "api_project_ai_configs"

    # PK
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # One-to-one with Project
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="Associated project ID (unique)",
    )

    # Default chat model selection
    default_chat_provider_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_ai_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="AIProvider ID for default chat model",
    )
    default_chat_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Default chat model identifier"
    )

    # Default embedding model selection
    default_embedding_provider_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_ai_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="AIProvider ID for default embedding model",
    )
    default_embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Default embedding model identifier"
    )

    # Device control model selection
    device_control_provider_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_ai_providers.id", ondelete="SET NULL"),
        nullable=True,
        comment="AIProvider ID for device control model",
    )
    device_control_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Device control model identifier"
    )

    # Timestamps (soft delete)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Sync tracking fields (to AI service)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    sync_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="ai_config", lazy="select")
    chat_provider: Mapped[Optional["AIProvider"]] = relationship(
        "AIProvider", foreign_keys=[default_chat_provider_id], lazy="select"
    )
    embedding_provider: Mapped[Optional["AIProvider"]] = relationship(
        "AIProvider", foreign_keys=[default_embedding_provider_id], lazy="select"
    )
    device_control_provider: Mapped[Optional["AIProvider"]] = relationship(
        "AIProvider", foreign_keys=[device_control_provider_id], lazy="select"
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_ai_config_project_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<ProjectAIConfig(project_id={self.project_id})>"

