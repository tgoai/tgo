"""Project model - synchronized from API service."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.collection import Collection


class Project(BaseModel):
    """
    Project model - synchronized copy from API service.
    
    This table is maintained by synchronization with the main API service
    and provides project information for multi-tenant isolation.
    """

    __tablename__ = "ai_projects"

    # Override id to not use default UUID generation since it's synced
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        comment="Project UUID synchronized from API service",
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Project name",
    )

    api_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="API key for authentication",
    )

    # Synchronization timestamp
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this record was last synchronized",
    )

    # Relationships
    agents: Mapped[List["Agent"]] = relationship(
        "Agent",
        primaryjoin="Project.id == foreign(Agent.project_id)",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    collections: Mapped[List["Collection"]] = relationship(
        "Collection",
        primaryjoin="Project.id == foreign(Collection.project_id)",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


    def __repr__(self) -> str:
        """String representation of the project."""
        return f"<Project(id={self.id}, name='{self.name}')>"
