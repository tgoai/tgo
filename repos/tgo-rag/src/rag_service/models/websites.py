"""
Website crawling models for RAG processing.

This module provides database models for managing website crawl jobs
and individual web pages for RAG document generation.
"""

from typing import List, Optional
from uuid import UUID as PyUUID

from sqlalchemy import ARRAY, BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class WebsiteCrawlJob(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    Website crawl job model for tracking website crawling tasks.
    
    This model manages the configuration and status of website crawling
    operations, tracking progress and storing crawl parameters.
    """

    __tablename__ = "rag_website_crawl_jobs"

    # Foreign keys
    project_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        doc="Associated project ID",
    )

    collection_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_collections.id", ondelete="CASCADE"),
        nullable=False,
        doc="Target collection ID for storing crawled content",
    )

    # Crawl configuration
    start_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        doc="Starting URL for the crawl",
    )

    max_pages: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        doc="Maximum number of pages to crawl",
    )

    max_depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        doc="Maximum crawl depth from start URL",
    )

    # URL patterns
    include_patterns: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="URL patterns to include (glob patterns)",
    )

    exclude_patterns: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="URL patterns to exclude (glob patterns)",
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="pending",
        doc="Job status: pending, crawling, processing, completed, failed, cancelled",
    )

    # Progress metrics
    pages_discovered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of pages discovered",
    )

    pages_crawled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of pages successfully crawled",
    )

    pages_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of pages processed into documents",
    )

    pages_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of pages that failed to process",
    )

    # Crawl options (JSONB for flexibility)
    crawl_options: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional crawl options (js_render, delay, user_agent, etc.)",
    )

    # Error information
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Error message if job failed",
    )

    # Celery task tracking
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Celery task ID for tracking",
    )

    # Relationships
    collection: Mapped["Collection"] = relationship(
        "Collection",
        doc="Target collection",
    )

    pages: Mapped[List["WebsitePage"]] = relationship(
        "WebsitePage",
        back_populates="crawl_job",
        cascade="all, delete-orphan",
        doc="Crawled pages",
    )

    # Indexes
    __table_args__ = (
        Index("idx_website_crawl_jobs_project_id", "project_id"),
        Index("idx_website_crawl_jobs_collection_id", "collection_id"),
        Index("idx_website_crawl_jobs_status", "status"),
        Index("idx_website_crawl_jobs_created_at", "created_at"),
        Index("idx_website_crawl_jobs_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return f"<WebsiteCrawlJob(id={self.id}, url='{self.start_url}', status='{self.status}')>"


class WebsitePage(Base, UUIDMixin, TimestampMixin):
    """
    Website page model for storing crawled page content.

    This model stores individual web pages crawled from a website,
    including their content and metadata for RAG processing.
    """

    __tablename__ = "rag_website_pages"

    # Foreign keys
    crawl_job_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_website_crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
        doc="Associated crawl job ID",
    )

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

    file_id: Mapped[Optional[PyUUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rag_files.id", ondelete="SET NULL"),
        nullable=True,
        doc="Associated file ID (created after processing)",
    )

    # Page information
    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        doc="Page URL",
    )

    url_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 hash of URL for deduplication",
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Page title",
    )

    depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Crawl depth from start URL",
    )

    # Content
    content_markdown: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Extracted content in Markdown format",
    )

    content_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Content length in characters",
    )

    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="SHA-256 hash of content for deduplication",
    )

    # Metadata
    meta_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Page meta description",
    )

    page_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional page metadata (headers, links, images, etc.)",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="pending",
        doc="Page status: pending, fetched, extracted, processed, failed",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Error message if processing failed",
    )

    # HTTP response info
    http_status_code: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="HTTP response status code",
    )

    # Relationships
    crawl_job: Mapped["WebsiteCrawlJob"] = relationship(
        "WebsiteCrawlJob",
        back_populates="pages",
        doc="Parent crawl job",
    )

    collection: Mapped["Collection"] = relationship(
        "Collection",
        doc="Associated collection",
    )

    file: Mapped[Optional["File"]] = relationship(
        "File",
        doc="Associated file record",
    )

    # Indexes
    __table_args__ = (
        Index("idx_website_pages_crawl_job_id", "crawl_job_id"),
        Index("idx_website_pages_collection_id", "collection_id"),
        Index("idx_website_pages_project_id", "project_id"),
        Index("idx_website_pages_file_id", "file_id"),
        Index("idx_website_pages_url_hash", "url_hash"),
        Index("idx_website_pages_status", "status"),
        Index("idx_website_pages_depth", "depth"),
        Index("idx_website_pages_created_at", "created_at"),
        # Unique constraint on URL within a crawl job
        Index("idx_website_pages_job_url", "crawl_job_id", "url_hash", unique=True),
    )

    def __repr__(self) -> str:
        return f"<WebsitePage(id={self.id}, url='{self.url[:50]}...', status='{self.status}')>"

