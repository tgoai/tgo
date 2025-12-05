"""RAG service schemas for proxy endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import BaseSchema, PaginationMetadata


class CollectionTypeEnum(str, Enum):
    """Enum representing the type/source of a collection.

    - FILE: Collection created from file uploads
    - WEBSITE: Collection created from website crawling
    - QA: Collection created from question-answer pairs
    """

    FILE = "file"
    WEBSITE = "website"
    QA = "qa"


class CrawlConfig(BaseSchema):
    """Crawl configuration for website collections.

    Only used when collection_type is 'website'. Contains all settings for
    controlling how the website crawler behaves.
    """

    start_url: Optional[str] = Field(
        None,
        description="Starting URL for crawling (required for website collections)",
        examples=["https://docs.example.com"]
    )
    max_pages: Optional[int] = Field(
        100,
        ge=1,
        le=10000,
        description="Maximum number of pages to crawl (default: 100)"
    )
    max_depth: Optional[int] = Field(
        3,
        ge=1,
        le=10,
        description="Maximum crawl depth from start URL (default: 3)"
    )
    include_patterns: Optional[List[str]] = Field(
        None,
        description="URL glob patterns to include (e.g., '*/docs/*', '*/guide/*')",
        examples=[["*/docs/*", "*/guide/*"]]
    )
    exclude_patterns: Optional[List[str]] = Field(
        None,
        description="URL glob patterns to exclude (e.g., '*/admin/*', '*/login/*')",
        examples=[["*/admin/*", "*/login/*"]]
    )
    wait_for_selector: Optional[str] = Field(
        None,
        description="CSS selector to wait for before extracting content",
        examples=[".main-content"]
    )
    timeout: Optional[int] = Field(
        30,
        ge=1,
        le=120,
        description="Page load timeout in seconds (default: 30)"
    )
    delay_between_requests: Optional[float] = Field(
        1.0,
        ge=0,
        le=60,
        description="Delay between requests in seconds (default: 1.0)"
    )
    respect_robots_txt: Optional[bool] = Field(
        True,
        description="Whether to respect robots.txt rules (default: true)"
    )
    user_agent: Optional[str] = Field(
        None,
        description="Custom user agent string for HTTP requests"
    )
    headers: Optional[Dict[str, str]] = Field(
        None,
        description="Custom HTTP headers to include in requests"
    )
    js_rendering: Optional[bool] = Field(
        True,
        description="Whether to render JavaScript using headless browser (default: true)"
    )
    extract_images: Optional[bool] = Field(
        False,
        description="Whether to extract image URLs from pages (default: false)"
    )
    extract_links: Optional[bool] = Field(
        True,
        description="Whether to extract external links from pages (default: true)"
    )



# Collection Schemas
class CollectionCreateRequest(BaseSchema):
    """Schema for creating a new collection."""

    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable collection name",
        examples=["Product Documentation v2.1"]
    )
    description: Optional[str] = Field(
        None,
        description="Optional collection description",
        examples=["Updated product documentation for RAG knowledge base"]
    )
    collection_type: CollectionTypeEnum = Field(
        CollectionTypeEnum.FILE,
        description="Type of collection: file, website, or qa",
        examples=["file"]
    )
    crawl_config: Optional[CrawlConfig] = Field(
        None,
        description=(
            "Crawl configuration for website collections "
            "(only used when collection_type is 'website').\n\n"
            "Available configuration options:\n"
            "- **start_url** (str, required): Starting URL for crawling\n"
            "- **max_pages** (int): Maximum number of pages to crawl (default: 100)\n"
            "- **max_depth** (int): Maximum crawl depth from start URL (default: 3)\n"
            "- **include_patterns** (list[str]): URL glob patterns to include\n"
            "- **exclude_patterns** (list[str]): URL glob patterns to exclude\n"
            "- **wait_for_selector** (str): CSS selector to wait for before extracting\n"
            "- **timeout** (int): Page load timeout in seconds (default: 30)\n"
            "- **delay_between_requests** (float): Delay between requests (default: 1.0)\n"
            "- **respect_robots_txt** (bool): Whether to respect robots.txt (default: true)\n"
            "- **user_agent** (str): Custom user agent string\n"
            "- **headers** (dict): Custom HTTP headers\n"
            "- **js_rendering** (bool): Whether to render JavaScript (default: true)\n"
            "- **extract_images** (bool): Whether to extract image URLs (default: false)\n"
            "- **extract_links** (bool): Whether to extract external links (default: true)"
        ),
        examples=[{
            "start_url": "https://docs.example.com",
            "max_pages": 100,
            "max_depth": 3,
            "include_patterns": ["*/docs/*", "*/guide/*"],
            "exclude_patterns": ["*/admin/*", "*/login/*"],
            "js_rendering": True,
            "respect_robots_txt": True
        }]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata (embedding model, chunk size, etc.)",
        examples=[{
            "embedding_model": "text-embedding-ada-002",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "language": "en"
        }]
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Collection tags for categorization and filtering",
        examples=[["documentation", "product", "v2.1"]]
    )



class CollectionUpdateRequest(BaseSchema):
    """Schema for updating an existing collection."""

    display_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Human-readable collection name",
        examples=["Product Documentation v2.2"]
    )
    description: Optional[str] = Field(
        None,
        description="Collection description",
        examples=["Updated product documentation for RAG knowledge base with new features"]
    )
    collection_type: Optional[CollectionTypeEnum] = Field(
        None,
        description="Type of collection: file, website, or qa",
        examples=["file"]
    )
    crawl_config: Optional[CrawlConfig] = Field(
        None,
        description=(
            "Crawl configuration for website collections. "
            "Only applicable when collection_type is 'website'.\n\n"
            "Contains settings such as:\n"
            "- start_url, max_pages, max_depth\n"
            "- include_patterns, exclude_patterns\n"
            "- timeout, delay_between_requests\n"
            "- js_rendering, extract_images, extract_links"
        ),
        examples=[{
            "max_pages": 200,
            "exclude_patterns": ["*/admin/*"]
        }]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata (embedding model, chunk size, etc.)",
        examples=[{
            "embedding_model": "text-embedding-ada-002",
            "chunk_size": 1200,
            "chunk_overlap": 250,
            "language": "en"
        }]
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Collection tags for categorization and filtering",
        examples=[["documentation", "product", "v2.2", "updated"]]
    )



class CollectionResponse(BaseSchema):
    """Schema for collection API responses."""

    id: str = Field(
        ...,
        description="Collection unique identifier",
        examples=["coll_123e4567-e89b-12d3-a456-426614174000"]
    )
    display_name: str = Field(
        ...,
        description="Human-readable collection name",
        examples=["Product Documentation v2.1"]
    )
    description: Optional[str] = Field(
        None,
        description="Collection description",
        examples=["Updated product documentation for RAG knowledge base"]
    )
    collection_type: CollectionTypeEnum = Field(
        ...,
        description="Type of collection: file, website, or qa",
        examples=["file"]
    )
    crawl_config: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Crawl configuration for website collections. "
            "Only present when collection_type is 'website'.\n\n"
            "Contains settings such as:\n"
            "- start_url, max_pages, max_depth\n"
            "- include_patterns, exclude_patterns\n"
            "- timeout, delay_between_requests\n"
            "- js_rendering, extract_images, extract_links"
        ),
        examples=[{
            "start_url": "https://docs.example.com",
            "max_pages": 100,
            "max_depth": 3,
            "exclude_patterns": ["*/admin/*"]
        }]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata",
        examples=[{
            "embedding_model": "text-embedding-ada-002",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "language": "en"
        }]
    )
    file_count: Optional[int] = Field(default=0, description="Number of files in collection")
    tags: Optional[List[str]] = Field(
        None,
        description="Collection tags for categorization and filtering",
        examples=[["documentation", "product", "v2.1"]]
    )
    created_at: datetime = Field(
        ...,
        description="Collection creation timestamp",
        examples=["2024-01-15T10:30:00Z"]
    )
    updated_at: datetime = Field(
        ...,
        description="Collection last update timestamp",
        examples=["2024-01-15T10:30:00Z"]
    )
    deleted_at: Optional[datetime] = Field(
        None,
        description="Collection deletion timestamp (if soft deleted)"
    )



class CollectionStats(BaseSchema):
    """Schema for collection statistics."""
    
    document_count: int = Field(
        ...,
        ge=0,
        description="Total number of documents in collection",
        examples=[150]
    )
    file_count: int = Field(
        ...,
        ge=0,
        description="Total number of files in collection",
        examples=[25]
    )
    total_tokens: int = Field(
        ...,
        ge=0,
        description="Total tokens across all documents",
        examples=[45000]
    )
    last_updated: Optional[datetime] = Field(
        None,
        description="Last time a document was added/updated",
        examples=["2024-01-15T14:30:00Z"]
    )


class CollectionDetailResponse(CollectionResponse):
    """Schema for detailed collection response with optional statistics."""
    
    stats: Optional[CollectionStats] = Field(
        None,
        description="Collection statistics (when include_stats=true)"
    )


class CollectionListResponse(BaseSchema):
    """Schema for paginated collection list responses."""
    
    data: List[CollectionResponse] = Field(
        ...,
        description="List of collections"
    )
    pagination: PaginationMetadata = Field(
        ...,
        description="Pagination metadata"
    )


# Search Schemas
class CollectionSearchRequest(BaseSchema):
    """Schema for collection-scoped search requests."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
        examples=["How to configure database settings"]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip for pagination"
    )
    min_score: float = Field(
        default=0,
        ge=0,
        le=1,
        description="Minimum relevance score threshold (0-1)"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional filters to apply to search results",
        examples=[{
            "content_type": ["paragraph", "heading"],
            "language": "en",
            "min_confidence": 0.8,
            "tags": {"section": "installation"}
        }]
    )


class SearchResult(BaseSchema):
    """Schema for individual search results."""

    document_id: UUID = Field(..., description="Document unique identifier")
    file_id: Optional[UUID] = Field(None, description="Associated file ID")
    collection_id: Optional[UUID] = Field(None, description="Associated collection ID")
    relevance_score: float = Field(
        ..., ge=0, le=1, description="Relevance score (0-1, higher is more relevant)"
    )
    content_preview: str = Field(..., description="Preview of the document content")
    document_title: Optional[str] = Field(None, description="Document title or heading")
    content_type: str = Field(
        ...,
        description="Type of content",
        examples=["paragraph", "heading", "table", "list", "code", "image", "metadata"]
    )
    chunk_index: Optional[int] = Field(None, description="Index of this chunk within the document")
    page_number: Optional[int] = Field(None, description="Page number in original document")
    section_title: Optional[str] = Field(None, description="Section or chapter title")
    tags: Optional[Dict[str, Any]] = Field(None, description="Document tags and metadata")
    created_at: datetime = Field(..., description="Document creation timestamp")


class SearchMetadata(BaseSchema):
    """Schema for search metadata."""

    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., ge=0, description="Total number of results found")
    returned_results: int = Field(..., ge=0, description="Number of results returned in this response")
    search_time_ms: int = Field(..., ge=0, description="Search execution time in milliseconds")
    filters_applied: Optional[Dict[str, Any]] = Field(
        None, description="Filters that were applied to the search"
    )
    search_type: str = Field(
        default="semantic",
        description="Type of search performed",
        examples=["semantic", "keyword", "hybrid"]
    )


class SearchResponse(BaseSchema):
    """Schema for search responses."""

    results: List[SearchResult] = Field(..., description="List of search results")
    search_metadata: SearchMetadata = Field(..., description="Search execution metadata")


# File Schemas  
class FileResponse(BaseSchema):
    """Schema for file API responses."""
    
    id: str = Field(..., description="File unique identifier")
    collection_id: Optional[str] = Field(
        None,
        description="Associated collection ID",
        examples=["coll_123e4567-e89b-12d3-a456-426614174000"]
    )
    original_filename: str = Field(
        ...,
        description="Original filename when uploaded",
        examples=["product_manual.pdf"]
    )
    file_size: int = Field(
        ...,
        description="File size in bytes",
        examples=[2048576]
    )
    content_type: str = Field(
        ...,
        description="MIME type of the file",
        examples=["application/pdf"]
    )
    status: str = Field(
        ...,
        description="Processing status",
        examples=["pending", "processing", "completed", "failed", "archived"]
    )
    document_count: int = Field(
        ...,
        description="Number of document chunks generated",
        examples=[25]
    )
    total_tokens: int = Field(
        ...,
        description="Total tokens across all document chunks",
        examples=[5000]
    )
    language: Optional[str] = Field(
        None,
        description="Detected or specified language",
        examples=["en", "es", "fr"]
    )
    description: Optional[str] = Field(
        None,
        description="Optional file description"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="File tags for categorization and filtering",
        examples=[["document", "manual", "pdf"]]
    )
    uploaded_by: Optional[str] = Field(
        None,
        description="User who uploaded the file"
    )
    created_at: datetime = Field(..., description="File upload timestamp")
    updated_at: datetime = Field(..., description="File last update timestamp")


class FileListResponse(BaseSchema):
    """Schema for paginated file list responses."""
    
    data: List[FileResponse] = Field(..., description="List of files")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class FileUploadResponse(BaseSchema):
    """Schema for file upload responses."""
    
    id: str = Field(..., description="File unique identifier")
    original_filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    status: str = Field(..., description="Processing status")
    message: str = Field(..., description="Upload status message")


# Batch Upload Schemas
class FileUploadError(BaseSchema):
    """Schema for individual file upload errors."""
    
    filename: str = Field(..., description="Name of the file that failed")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")


class BatchUploadSummary(BaseSchema):
    """Schema for batch upload summary statistics."""
    
    total_files: int = Field(..., description="Total number of files in the batch")
    successful_uploads: int = Field(..., description="Number of successfully uploaded files")
    failed_uploads: int = Field(..., description="Number of failed uploads")
    total_size: int = Field(..., description="Total size of all files in bytes")


class BatchFileUploadResponse(BaseSchema):
    """Schema for batch file upload responses."""
    
    summary: BatchUploadSummary = Field(..., description="Batch upload summary statistics")
    successful_uploads: List[FileUploadResponse] = Field(
        ...,
        description="List of successfully uploaded files"
    )
    failed_uploads: List[FileUploadError] = Field(
        ...,
        description="List of failed uploads with error details"
    )
    message: str = Field(
        ...,
        description="Overall batch status message",
        examples=["Batch upload completed: 4 successful, 1 failed"]
    )


# Website Crawl Schemas
class CrawlOptionsSchema(BaseSchema):
    """Schema for crawl configuration options."""

    render_js: Optional[bool] = Field(
        None, description="Whether to render JavaScript (uses headless browser)"
    )
    wait_time: Optional[int] = Field(
        None, description="Wait time in seconds after page load"
    )
    follow_external_links: Optional[bool] = Field(
        None, description="Whether to follow external links"
    )
    respect_robots_txt: Optional[bool] = Field(
        None, description="Whether to respect robots.txt rules"
    )
    user_agent: Optional[str] = Field(
        None, description="Custom User-Agent header"
    )
    headers: Optional[Dict[str, str]] = Field(
        None, description="Custom HTTP headers"
    )


# =============================================================================
# Website Pages Schemas (New API)
# =============================================================================

class WebsitePageResponse(BaseSchema):
    """Schema for website page API responses."""

    id: UUID = Field(..., description="Page unique identifier")
    collection_id: UUID = Field(..., description="Associated collection ID")
    parent_page_id: Optional[UUID] = Field(
        None, description="Parent page ID (for hierarchical structure)"
    )
    url: str = Field(..., description="Page URL")
    title: Optional[str] = Field(None, description="Page title")
    depth: int = Field(..., description="Crawl depth from root page")
    content_length: int = Field(..., description="Content length in characters")
    meta_description: Optional[str] = Field(None, description="Page meta description")
    status: str = Field(
        ...,
        description="Page status: pending, crawling, fetched, extracted, processing, processed, failed, skipped"
    )
    crawl_source: Optional[str] = Field(
        None, description="How this page was added: initial, discovered, manual, deep_crawl"
    )
    http_status_code: Optional[int] = Field(None, description="HTTP response status code")
    file_id: Optional[UUID] = Field(None, description="Associated file ID (after processing)")
    discovered_links: Optional[List[Dict[str, Any]]] = Field(
        None, description="Links discovered on this page"
    )
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    tree_completed: bool = Field(
        False, description="Whether this page and all its descendant pages have been processed or skipped"
    )
    has_children: bool = Field(
        False, description="Whether this page has any child pages"
    )
    children: Optional[List["WebsitePageResponse"]] = Field(
        None, description="Child pages (populated when tree_depth > 0)"
    )
    created_at: datetime = Field(..., description="Page creation timestamp")
    updated_at: datetime = Field(..., description="Page last update timestamp")


class WebsitePageListResponse(BaseSchema):
    """Schema for paginated page list responses."""

    data: List[WebsitePageResponse] = Field(..., description="List of pages")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class AddPageRequest(BaseSchema):
    """Schema for adding a page to crawl."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2083,
        description="URL of the page to add",
        examples=["https://docs.python.org/3/"]
    )
    parent_page_id: Optional[UUID] = Field(
        None,
        description="Parent page ID. If provided, the new page will be a child of this page with depth = parent.depth + 1"
    )
    max_depth: int = Field(
        0,
        ge=0,
        le=10,
        description="Maximum crawl depth from this page (0 = only this page)"
    )
    include_patterns: Optional[List[str]] = Field(
        None, description="URL patterns to include (glob patterns)"
    )
    exclude_patterns: Optional[List[str]] = Field(
        None, description="URL patterns to exclude (glob patterns)"
    )
    options: Optional[CrawlOptionsSchema] = Field(
        None, description="Crawl options (overrides collection defaults)"
    )


class AddPageResponse(BaseSchema):
    """Schema for add page response."""

    success: bool = Field(..., description="Whether the page was added successfully")
    page_id: Optional[UUID] = Field(
        None, description="ID of the newly created page (if added)"
    )
    message: str = Field(..., description="Status message")
    status: str = Field(
        ..., description="Result status: 'added', 'exists', 'crawling'"
    )


class CrawlDeeperRequest(BaseSchema):
    """Schema for deep crawl request from an existing page."""

    max_depth: int = Field(
        1,
        ge=1,
        le=10,
        description="Maximum crawl depth from this page"
    )
    include_patterns: Optional[List[str]] = Field(
        None, description="URL patterns to include (fnmatch style)"
    )
    exclude_patterns: Optional[List[str]] = Field(
        None, description="URL patterns to exclude (fnmatch style)"
    )


class CrawlDeeperResponse(BaseSchema):
    """Schema for deep crawl response."""

    success: bool = Field(..., description="Whether the operation was successful")
    source_page_id: UUID = Field(..., description="ID of the source page")
    pages_added: int = Field(..., description="Number of new pages added to crawl queue")
    pages_skipped: int = Field(
        ..., description="Number of pages skipped (already exists or crawling)"
    )
    links_found: int = Field(..., description="Total number of links found in the page")
    message: str = Field(..., description="Status message")
    added_urls: Optional[List[str]] = Field(
        None, description="URLs that were added to crawl queue"
    )


class CrawlProgressSchema(BaseSchema):
    """Schema for collection crawl progress (computed from pages)."""

    total_pages: int = Field(..., ge=0, description="Total number of pages in collection")
    pages_pending: int = Field(..., ge=0, description="Number of pages pending crawl")
    pages_crawled: int = Field(..., ge=0, description="Number of pages successfully crawled")
    pages_processing: int = Field(..., ge=0, description="Number of pages being processed")
    pages_processed: int = Field(..., ge=0, description="Number of pages processed into documents")
    pages_failed: int = Field(..., ge=0, description="Number of pages that failed to process")
    progress_percent: float = Field(
        ..., ge=0, le=100, description="Overall progress percentage"
    )


# =============================================================================
# QA Pairs Schemas
# =============================================================================

class QAPairCreateRequest(BaseSchema):
    """Schema for creating a single QA pair."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The question text",
        examples=["如何重置密码？"]
    )
    answer: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="The answer text",
        examples=["您可以通过以下步骤重置密码：1. 点击登录页面的'忘记密码'..."]
    )
    category: Optional[str] = Field(
        None,
        max_length=255,
        description="Category for organizing QA pairs",
        examples=["账户管理"]
    )
    subcategory: Optional[str] = Field(
        None,
        max_length=255,
        description="Subcategory for finer organization",
        examples=["密码相关"]
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Tags for filtering and search",
        examples=[["密码", "重置", "账户"]]
    )
    qa_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata",
        examples=[{"source": "user_manual", "version": "2.0"}]
    )
    priority: int = Field(
        0,
        ge=0,
        le=100,
        description="Priority for ordering (0-100, higher = more important)"
    )


class QAPairUpdateRequest(BaseSchema):
    """Schema for updating a QA pair."""

    question: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10000,
        description="Updated question text"
    )
    answer: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50000,
        description="Updated answer text"
    )
    category: Optional[str] = Field(None, max_length=255)
    subcategory: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = None
    qa_metadata: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=0, le=100)


class QAPairResponse(BaseSchema):
    """Schema for QA pair API responses."""

    id: UUID = Field(..., description="QA pair unique identifier")
    collection_id: UUID = Field(..., description="Associated collection ID")
    question: str = Field(..., description="The question text")
    answer: str = Field(..., description="The answer text")
    question_hash: str = Field(..., description="Question hash for deduplication")
    category: Optional[str] = Field(None, description="Category")
    subcategory: Optional[str] = Field(None, description="Subcategory")
    tags: Optional[List[str]] = Field(None, description="Tags")
    qa_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    source_type: str = Field(..., description="Source type: manual, import, ai_generated")
    status: str = Field(..., description="Processing status")
    priority: int = Field(..., description="Priority")
    document_id: Optional[UUID] = Field(None, description="Associated document ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class QAPairListResponse(BaseSchema):
    """Schema for paginated QA pair list responses."""

    data: List[QAPairResponse] = Field(..., description="List of QA pairs")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class QAPairBatchCreateRequest(BaseSchema):
    """Schema for batch creating QA pairs."""

    qa_pairs: List[QAPairCreateRequest] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of QA pairs to create (max 1000)"
    )


class QAPairBatchCreateResponse(BaseSchema):
    """Schema for batch create response."""

    success: bool = Field(..., description="Whether operation succeeded")
    created_count: int = Field(..., description="Number of QA pairs created")
    skipped_count: int = Field(..., description="Number skipped (duplicates)")
    failed_count: int = Field(..., description="Number failed")
    created_ids: Optional[List[UUID]] = Field(None, description="Created QA pair IDs")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Error details")
    message: str = Field(..., description="Summary message")


class QAPairImportFormatEnum(str, Enum):
    """Import format enum."""
    JSON = "json"
    CSV = "csv"


class QAPairImportRequest(BaseSchema):
    """Schema for importing QA pairs from JSON/CSV."""

    format: QAPairImportFormatEnum = Field(
        QAPairImportFormatEnum.JSON,
        description="Import format: json or csv"
    )
    data: str = Field(..., description="JSON array string or CSV content")
    category: Optional[str] = Field(None, description="Default category for all imported pairs")
    tags: Optional[List[str]] = Field(None, description="Default tags for all imported pairs")


class QACategoryListResponse(BaseSchema):
    """Schema for QA category list response."""

    categories: List[str] = Field(..., description="List of unique categories")
    total: int = Field(..., description="Total count of categories")