"""
Collection model for organizing documents.
"""

import enum
from typing import List, Optional

from sqlalchemy import ARRAY, Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class CollectionType(str, enum.Enum):
    """
    Enum representing the type/source of a collection.

    - file: Collection created from file uploads
    - website: Collection created from website crawling
    - qa: Collection created from question-answer pairs
    """
    file = "file"
    website = "website"
    qa = "qa"


class Collection(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Collection model for organizing documents and files within projects.
    
    Collections provide a way to group related documents and files for better
    organization and scoped search operations within RAG workflows.
    """

    __tablename__ = "rag_collections"

    # Foreign key to project
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        doc="Associated project ID (logical reference to API service)",
    )

    # Collection type
    collection_type: Mapped[CollectionType] = mapped_column(
        Enum(CollectionType, name="collection_type_enum", create_type=True),
        nullable=False,
        default=CollectionType.file,
        server_default="file",
        doc="Type of collection: file, website, or qa",
    )

    # Crawl configuration (only used when collection_type is WEBSITE)
    # Structure:
    # {
    #     "start_url": str,              # Starting URL for crawling (required)
    #     "max_pages": int,              # Maximum number of pages to crawl (default: 100)
    #     "max_depth": int,              # Maximum crawl depth from start URL (default: 3)
    #     "include_patterns": list[str], # URL patterns to include (glob patterns)
    #     "exclude_patterns": list[str], # URL patterns to exclude (glob patterns)
    #     "wait_for_selector": str,      # CSS selector to wait for before extracting content
    #     "timeout": int,                # Page load timeout in seconds (default: 30)
    #     "delay_between_requests": float, # Delay between requests in seconds (default: 1.0)
    #     "respect_robots_txt": bool,    # Whether to respect robots.txt (default: True)
    #     "user_agent": str,             # Custom user agent string
    #     "headers": dict[str, str],     # Custom HTTP headers
    #     "js_rendering": bool,          # Whether to render JavaScript (default: True)
    #     "extract_images": bool,        # Whether to extract image URLs (default: False)
    #     "extract_links": bool,         # Whether to extract external links (default: True)
    # }
    crawl_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Crawl configuration for website collections. Contains settings like start_url, "
            "max_pages, max_depth, include/exclude patterns, timeouts, and rendering options.",
    )

    # Collection information
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable collection name",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Collection description",
    )

    collection_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Collection metadata (embedding model, chunk size, etc.)",
    )

    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Collection tags for categorization and filtering",
    )

    # Relationships

    files: Mapped[List["File"]] = relationship(
        "File",
        back_populates="collection",
        cascade="all, delete-orphan",
        doc="Files in this collection",
    )

    documents: Mapped[List["FileDocument"]] = relationship(
        "FileDocument",
        back_populates="collection",
        cascade="all, delete-orphan",
        doc="Documents in this collection",
    )

    qa_pairs: Mapped[List["QAPair"]] = relationship(
        "QAPair",
        back_populates="collection",
        cascade="all, delete-orphan",
        doc="QA pairs in this collection (for qa type collections)",
    )

    # Indexes
    __table_args__ = (
        Index("idx_rag_collections_project_id", "project_id"),
        Index("idx_rag_collections_collection_type", "collection_type"),
        Index("idx_rag_collections_display_name", "display_name"),
        Index("idx_rag_collections_created_at", "created_at"),
        Index("idx_rag_collections_deleted_at", "deleted_at"),
        Index("idx_rag_collections_project_display_name", "project_id", "display_name"),
        Index("idx_rag_collections_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        """String representation of the collection."""
        return f"<Collection(id={self.id}, display_name='{self.display_name}', project_id={self.project_id})>"

    @property
    def document_count(self) -> int:
        """Get the number of documents in this collection."""
        return len(self.documents) if self.documents else 0

    def get_metadata_value(self, key: str, default=None):
        """
        Get a specific metadata value.

        Args:
            key: Metadata key to retrieve
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        if not self.collection_metadata:
            return default
        return self.collection_metadata.get(key, default)

    def set_metadata_value(self, key: str, value) -> None:
        """
        Set a specific metadata value.

        Args:
            key: Metadata key to set
            value: Value to set
        """
        if self.collection_metadata is None:
            self.collection_metadata = {}
        self.collection_metadata[key] = value

    def update_metadata(self, updates: dict) -> None:
        """
        Update multiple metadata values.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        if self.collection_metadata is None:
            self.collection_metadata = {}
        self.collection_metadata.update(updates)
