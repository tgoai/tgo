"""Installed Plugin model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class InstalledPlugin(Base):
    """Model for plugins installed by users."""

    __tablename__ = "pg_installed_plugins"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Basic fields
    plugin_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    author: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Installation configuration
    install_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    source_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    build_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    runtime_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Runtime status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    install_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    pid: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    installed_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )

