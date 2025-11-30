"""
QA (Question-Answer) pair models for RAG processing.

This module provides database models for managing QA knowledge bases,
storing question-answer pairs for direct embedding and retrieval.
"""

from typing import List, Optional
from uuid import UUID as PyUUID

from sqlalchemy import ARRAY, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class QAPair(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    QA pair model for storing question-answer knowledge.

    This model stores individual question-answer pairs that are directly
    embedded without chunking, providing precise answers for FAQ-style
    knowledge bases.
    """

    __tablename__ = "rag_qa_pairs"

    # Foreign keys
    collection_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        doc="Associated collection ID",
    )

    project_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        doc="Associated project ID",
    )

    # QA content
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The question text",
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The answer text",
    )

    question_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 hash of question for deduplication",
    )

    # Classification
    category: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Category for organizing QA pairs",
    )

    subcategory: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Subcategory for finer organization",
    )

    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="Tags for filtering and search",
    )

    # Metadata
    qa_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional metadata (source, author, etc.)",
    )

    # Source tracking
    source_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="manual",
        doc="Source type: manual, import, ai_generated",
    )

    source_reference: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Reference to the source (file path, URL, etc.)",
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="pending",
        doc="Processing status: pending, processed, failed",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Error message if processing failed",
    )

    # Link to generated FileDocument
    document_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_file_documents.id", ondelete="SET NULL"),
        nullable=True,
        doc="Associated FileDocument ID after processing",
    )

    # Priority/ordering
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Priority for ordering (higher = more important)",
    )

    # Relationships
    collection: Mapped["Collection"] = relationship(
        "Collection",
        back_populates="qa_pairs",
        doc="Parent collection",
    )

    document: Mapped[Optional["FileDocument"]] = relationship(
        "FileDocument",
        doc="Associated document with embedding",
    )

    # Indexes
    __table_args__ = (
        Index("idx_qa_pairs_collection_id", "collection_id"),
        Index("idx_qa_pairs_project_id", "project_id"),
        Index("idx_qa_pairs_question_hash", "question_hash"),
        Index("idx_qa_pairs_category", "category"),
        Index("idx_qa_pairs_status", "status"),
        Index("idx_qa_pairs_source_type", "source_type"),
        Index("idx_qa_pairs_created_at", "created_at"),
        Index("idx_qa_pairs_deleted_at", "deleted_at"),
        Index("idx_qa_pairs_tags", "tags", postgresql_using="gin"),
        # Unique constraint on question within a collection
        Index("idx_qa_pairs_collection_question", "collection_id", "question_hash", unique=True),
    )

    def __repr__(self) -> str:
        return f"<QAPair(id={self.id}, question='{self.question[:50]}...', status='{self.status}')>"

