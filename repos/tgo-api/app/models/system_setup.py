"""System setup/installation status model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SystemSetup(Base):
    """Singleton-style table storing system installation status and options.

    There should be at most one row in this table. Application logic ensures
    singleton semantics by always reading/updating the first row.
    """

    __tablename__ = "api_system_setup"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # High-level installation flags
    is_installed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    admin_created: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    llm_configured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    skip_llm_config: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Metadata about the setup process
    setup_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    setup_version: Mapped[Optional[str]] = mapped_column(
        String(length=50),
        nullable=True,
        default="v1",
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return (
            "SystemSetup(is_installed="
            f"{self.is_installed}, admin_created={self.admin_created}, "
            f"llm_configured={self.llm_configured}, "
            f"skip_llm_config={self.skip_llm_config})"
        )
