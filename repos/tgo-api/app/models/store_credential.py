from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StoreCredential(Base):
    """Store credentials for a project."""

    __tablename__ = "api_store_credentials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("api_projects.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False,
        comment="Associated project ID"
    )
    
    store_user_id: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        comment="User ID in the Store"
    )
    store_email: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        comment="Email associated with the Store account"
    )
    
    # Encrypted fields
    api_key_encrypted: Mapped[str] = mapped_column(
        String(1024), 
        nullable=False,
        comment="Encrypted API Key"
    )
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(
        String(1024), 
        nullable=True,
        comment="Encrypted Refresh Token"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now()
    )
