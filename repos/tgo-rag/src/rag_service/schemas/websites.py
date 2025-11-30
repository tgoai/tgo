"""
Website crawling Pydantic schemas.

This module provides request/response schemas for website crawling APIs.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class CrawlOptionsSchema(BaseModel):
    """Schema for crawl configuration options."""
    
    render_js: bool = Field(
        default=False,
        description="Whether to render JavaScript (uses headless browser)",
    )
    respect_robots_txt: bool = Field(
        default=True,
        description="Whether to respect robots.txt rules",
    )
    delay_seconds: float = Field(
        default=1.0,
        ge=0,
        le=60,
        description="Delay between requests in seconds",
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="Custom user agent string",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds",
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom HTTP headers",
    )


class WebsiteCrawlRequest(BaseModel):
    """Schema for creating a new website crawl job."""
    
    start_url: HttpUrl = Field(
        ...,
        description="Starting URL for the crawl",
        examples=["https://docs.python.org/3/"],
    )
    max_pages: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of pages to crawl",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum crawl depth from start URL",
    )
    include_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to include (glob patterns)",
        examples=[["*/docs/*", "*/api/*"]],
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to exclude (glob patterns)",
        examples=[["*/login", "*/admin/*"]],
    )
    options: Optional[CrawlOptionsSchema] = Field(
        default=None,
        description="Additional crawl options",
    )


class CrawlProgressSchema(BaseModel):
    """Schema for crawl job progress information."""
    
    pages_discovered: int = Field(
        ...,
        ge=0,
        description="Number of pages discovered",
    )
    pages_crawled: int = Field(
        ...,
        ge=0,
        description="Number of pages successfully crawled",
    )
    pages_processed: int = Field(
        ...,
        ge=0,
        description="Number of pages processed into documents",
    )
    pages_failed: int = Field(
        ...,
        ge=0,
        description="Number of pages that failed to process",
    )
    progress_percent: float = Field(
        ...,
        ge=0,
        le=100,
        description="Overall progress percentage",
    )


class WebsiteCrawlJobResponse(BaseModel):
    """Schema for website crawl job API responses."""
    
    id: UUID = Field(
        ...,
        description="Crawl job unique identifier",
    )
    collection_id: UUID = Field(
        ...,
        description="Target collection ID",
    )
    start_url: str = Field(
        ...,
        description="Starting URL for the crawl",
    )
    max_pages: int = Field(
        ...,
        description="Maximum number of pages to crawl",
    )
    max_depth: int = Field(
        ...,
        description="Maximum crawl depth",
    )
    include_patterns: Optional[List[str]] = Field(
        None,
        description="URL patterns to include",
    )
    exclude_patterns: Optional[List[str]] = Field(
        None,
        description="URL patterns to exclude",
    )
    status: str = Field(
        ...,
        description="Job status: pending, crawling, processing, completed, failed, cancelled",
    )
    progress: CrawlProgressSchema = Field(
        ...,
        description="Crawl progress information",
    )
    crawl_options: Optional[Dict[str, Any]] = Field(
        None,
        description="Crawl configuration options",
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if job failed",
    )
    created_at: datetime = Field(
        ...,
        description="Job creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Job last update timestamp",
    )

    class Config:
        from_attributes = True


class WebsiteCrawlCreateResponse(BaseModel):
    """Schema for crawl job creation response."""

    job_id: UUID = Field(
        ...,
        description="Created crawl job ID",
    )
    status: str = Field(
        ...,
        description="Initial job status",
    )
    start_url: str = Field(
        ...,
        description="Starting URL for the crawl",
    )
    collection_id: UUID = Field(
        ...,
        description="Target collection ID",
    )
    created_at: datetime = Field(
        ...,
        description="Job creation timestamp",
    )
    message: str = Field(
        ...,
        description="Status message",
    )


class WebsitePageResponse(BaseModel):
    """Schema for website page API responses."""

    id: UUID = Field(
        ...,
        description="Page unique identifier",
    )
    crawl_job_id: UUID = Field(
        ...,
        description="Associated crawl job ID",
    )
    collection_id: UUID = Field(
        ...,
        description="Associated collection ID",
    )
    url: str = Field(
        ...,
        description="Page URL",
    )
    title: Optional[str] = Field(
        None,
        description="Page title",
    )
    depth: int = Field(
        ...,
        description="Crawl depth from start URL",
    )
    content_length: int = Field(
        ...,
        description="Content length in characters",
    )
    meta_description: Optional[str] = Field(
        None,
        description="Page meta description",
    )
    status: str = Field(
        ...,
        description="Page status: pending, fetched, extracted, processed, failed",
    )
    http_status_code: Optional[int] = Field(
        None,
        description="HTTP response status code",
    )
    file_id: Optional[UUID] = Field(
        None,
        description="Associated file ID (after processing)",
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if processing failed",
    )
    created_at: datetime = Field(
        ...,
        description="Page creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Page last update timestamp",
    )

    class Config:
        from_attributes = True


class WebsitePageListResponse(BaseModel):
    """Schema for paginated page list responses."""

    data: List[WebsitePageResponse] = Field(
        ...,
        description="List of pages",
    )
    pagination: "PaginationMetadata" = Field(
        ...,
        description="Pagination metadata",
    )


class WebsiteCrawlJobListResponse(BaseModel):
    """Schema for paginated crawl job list responses."""

    data: List[WebsiteCrawlJobResponse] = Field(
        ...,
        description="List of crawl jobs",
    )
    pagination: "PaginationMetadata" = Field(
        ...,
        description="Pagination metadata",
    )


# ============================================================================
# Add Page Request/Response Schemas
# ============================================================================

class AddPageRequest(BaseModel):
    """Schema for adding a single page to crawl queue."""

    url: HttpUrl = Field(
        ...,
        description="URL of the page to add",
    )


class AddPageResponse(BaseModel):
    """Schema for add page response."""

    success: bool = Field(
        ...,
        description="Whether the page was added successfully",
    )
    page_id: Optional[UUID] = Field(
        None,
        description="ID of the newly created page (if added)",
    )
    message: str = Field(
        ...,
        description="Status message",
    )
    status: str = Field(
        ...,
        description="Result status: 'added', 'exists', 'crawling'",
    )


class CrawlDeeperRequest(BaseModel):
    """Schema for deep crawl request from an existing page."""

    max_depth: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Maximum crawl depth from this page",
    )
    include_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to include (fnmatch style)",
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="URL patterns to exclude (fnmatch style)",
    )


class CrawlDeeperResponse(BaseModel):
    """Schema for deep crawl response."""

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )
    source_page_id: UUID = Field(
        ...,
        description="ID of the source page",
    )
    pages_added: int = Field(
        ...,
        description="Number of new pages added to crawl queue",
    )
    pages_skipped: int = Field(
        ...,
        description="Number of pages skipped (already exists or crawling)",
    )
    links_found: int = Field(
        ...,
        description="Total number of links found in the page",
    )
    message: str = Field(
        ...,
        description="Status message",
    )
    added_urls: List[str] = Field(
        default_factory=list,
        description="URLs that were added to crawl queue",
    )


# Import for pagination - avoid circular imports
from .common import PaginationMetadata
WebsitePageListResponse.model_rebuild()
WebsiteCrawlJobListResponse.model_rebuild()

