"""
Document model for processed document chunks.
"""

from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Import pgvector with fallback for development
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback for development without pgvector installed
    from sqlalchemy import ARRAY, Float
    Vector = lambda dim: ARRAY(Float)

from .base import Base, TimestampMixin, UUIDMixin


class FileDocument(Base, UUIDMixin, TimestampMixin):
    """
    Document model representing processed document chunks for RAG operations.
    
    This model stores individual document chunks extracted from files,
    along with their vector embeddings and metadata for semantic search.
    """
    
    staticmethod
    table_name = "rag_file_documents"

    __tablename__ = table_name

    # Foreign keys
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        doc="Associated project ID for multi-tenant isolation",
    )

    file_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_files.id", ondelete="SET NULL"),
        nullable=True,
        doc="Associated file ID (nullable for QA pairs)",
    )

    collection_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_collections.id", ondelete="SET NULL"),
        nullable=True,
        doc="Associated collection ID",
    )



    # Document content
    document_title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Document title or heading",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Document content text for RAG processing",
    )

    content_tsv: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        nullable=True,
        doc="PostgreSQL full-text search vector for hybrid search capabilities",
    )

    content_length: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        default=0,
        doc="Length of content in characters",
    )

    token_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Number of tokens in the content",
    )

    # Document structure
    chunk_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Index of this chunk within the document",
    )

    section_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Section or chapter title",
    )

    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Page number in original document",
    )

    # Content classification
    content_type: Mapped[str] = mapped_column(
        String(50),
        nullable=True, 
        default="paragraph",
        doc="Type of content (paragraph, heading, table, list, code, image, metadata)",
    )

    language: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        doc="Document language (ISO 639-1 code)",
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        doc="Confidence score for content extraction (0.0-1.0)",
    )

    # Metadata and tags
    tags: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Document tags and metadata for RAG categorization",
    )

    # Vector embedding information
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Model used to generate embeddings",
    )

    embedding_dimensions: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Dimensions of the embedding vector",
    )

    # Vector embedding (stored in PostgreSQL with pgvector)
    embedding: Mapped[Optional[list]] = mapped_column(
        Vector(1536),  # Default OpenAI embedding dimensions
        nullable=True,
        doc="Vector embedding for semantic search",
    )

    # Relationships
    file: Mapped[Optional["File"]] = relationship(
        "File",
        back_populates="documents",
        doc="Associated file (optional for QA pairs)",
    )

    collection: Mapped[Optional["Collection"]] = relationship(
        "Collection",
        back_populates="documents",
        doc="Associated collection",
    )

    # Indexes
    __table_args__ = (
        Index("idx_rag_file_documents_file_id", "file_id"),
        Index("idx_rag_file_documents_collection_id", "collection_id"),
        Index("idx_rag_file_documents_content_type", "content_type"),
        Index("idx_rag_file_documents_language", "language"),
        Index("idx_rag_file_documents_chunk_index", "chunk_index"),
        Index("idx_rag_file_documents_page_number", "page_number"),
        Index("idx_rag_file_documents_token_count", "token_count"),
        Index("idx_rag_file_documents_confidence_score", "confidence_score"),
        Index("idx_rag_file_documents_embedding_model", "embedding_model"),
        Index("idx_rag_file_documents_created_at", "created_at"),
        Index("idx_rag_file_documents_content_tsv", "content_tsv", postgresql_using="gin"),
        Index("idx_rag_file_documents_file_chunk", "file_id", "chunk_index"),
    )

    def __repr__(self) -> str:
        """String representation of the document."""
        return f"<FileDocument(id={self.id}, content_type='{self.content_type}', file_id={self.file_id})>"

    @property
    def has_embedding(self) -> bool:
        """Check if the document has an embedding vector."""
        return self.embedding is not None

    @property
    def content_preview(self, length: int = 100) -> str:
        """
        Get a preview of the document content.
        
        Args:
            length: Maximum length of the preview
            
        Returns:
            Truncated content preview
        """
        if len(self.content) <= length:
            return self.content
        return self.content[:length] + "..."

    def get_tag_value(self, key: str, default=None):
        """
        Get a specific tag value.
        
        Args:
            key: Tag key to retrieve
            default: Default value if key not found
            
        Returns:
            Tag value or default
        """
        if not self.tags:
            return default
        return self.tags.get(key, default)

    def set_tag_value(self, key: str, value) -> None:
        """
        Set a specific tag value.
        
        Args:
            key: Tag key to set
            value: Value to set
        """
        if self.tags is None:
            self.tags = {}
        self.tags[key] = value

    def update_embedding_info(self, model: str, dimensions: int) -> None:
        """
        Update embedding-related information.

        Args:
            model: Embedding model name
            dimensions: Vector dimensions
        """
        self.embedding_model = model
        self.embedding_dimensions = dimensions
