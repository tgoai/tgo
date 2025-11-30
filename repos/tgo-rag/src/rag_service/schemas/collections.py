"""
Collection-related Pydantic schemas.
"""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionTypeEnum(str, enum.Enum):
    """
    Enum representing the type/source of a collection.

    - file: Collection created from file uploads
    - website: Collection created from website crawling
    - qa: Collection created from question-answer pairs
    """
    file = "file"
    website = "website"
    qa = "qa"


class CollectionCreateRequest(BaseModel):
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
        default=CollectionTypeEnum.file,
        description="Type of collection: file, website, or qa",
        examples=["file"]
    )
    crawl_config: Optional[Dict[str, Any]] = Field(
        None,
        description="""Crawl configuration for website collections (only used when collection_type is 'website').

Available configuration options:
- **start_url** (str, required): Starting URL for crawling
- **max_pages** (int): Maximum number of pages to crawl (default: 100)
- **max_depth** (int): Maximum crawl depth from start URL (default: 3)
- **include_patterns** (list[str]): URL glob patterns to include (e.g., '*/docs/*')
- **exclude_patterns** (list[str]): URL glob patterns to exclude (e.g., '*/admin/*')
- **wait_for_selector** (str): CSS selector to wait for before extracting content
- **timeout** (int): Page load timeout in seconds (default: 30)
- **delay_between_requests** (float): Delay between requests in seconds (default: 1.0)
- **respect_robots_txt** (bool): Whether to respect robots.txt (default: true)
- **user_agent** (str): Custom user agent string
- **headers** (dict): Custom HTTP headers
- **js_rendering** (bool): Whether to render JavaScript (default: true)
- **extract_images** (bool): Whether to extract image URLs (default: false)
- **extract_links** (bool): Whether to extract external links (default: true)
""",
        examples=[
            {
                "start_url": "https://docs.example.com",
                "max_pages": 100,
                "max_depth": 3,
                "include_patterns": ["*/docs/*", "*/guide/*"],
                "exclude_patterns": ["*/admin/*", "*/login/*"],
                "wait_for_selector": ".main-content",
                "timeout": 30,
                "delay_between_requests": 1.0,
                "respect_robots_txt": True,
                "js_rendering": True,
                "extract_links": True
            }
        ]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata (embedding model, chunk size, etc.)",
        examples=[
            {
                "embedding_model": "text-embedding-ada-002",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "language": "en"
            }
        ]
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Collection tags for categorization and filtering",
        examples=[["documentation", "product", "v2.1"]]
    )


class CollectionUpdateRequest(BaseModel):
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
    crawl_config: Optional[Dict[str, Any]] = Field(
        None,
        description="""Crawl configuration for website collections. See CollectionCreateRequest for full option list.

Common options to update:
- **max_pages**: Maximum number of pages to crawl
- **max_depth**: Maximum crawl depth from start URL
- **include_patterns** / **exclude_patterns**: URL filtering patterns
- **timeout**: Page load timeout in seconds
- **delay_between_requests**: Delay between requests
""",
        examples=[
            {
                "max_pages": 200,
                "max_depth": 5,
                "include_patterns": ["*/docs/*", "*/api/*"],
                "exclude_patterns": ["*/admin/*", "*/login/*"],
                "delay_between_requests": 2.0
            }
        ]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata (embedding model, chunk size, etc.)",
        examples=[
            {
                "embedding_model": "text-embedding-ada-002",
                "chunk_size": 1200,
                "chunk_overlap": 250,
                "language": "en"
            }
        ]
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Collection tags for categorization and filtering",
        examples=[["documentation", "product", "v2.2", "updated"]]
    )


class CollectionResponse(BaseModel):
    """Schema for collection API responses."""

    id: UUID = Field(
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
        description="""Crawl configuration for website collections. Only present when collection_type is 'website'.

Contains settings such as:
- start_url, max_pages, max_depth
- include_patterns, exclude_patterns
- timeout, delay_between_requests
- js_rendering, extract_images, extract_links
""",
        examples=[
            {
                "start_url": "https://docs.example.com",
                "max_pages": 100,
                "max_depth": 3,
                "include_patterns": ["*/docs/*"],
                "exclude_patterns": ["*/admin/*"],
                "js_rendering": True
            }
        ]
    )
    collection_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Collection metadata",
        examples=[
            {
                "embedding_model": "text-embedding-ada-002",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "language": "en"
            }
        ]
    )
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
    file_count: int = Field(
        ...,
        ge=0,
        description="Total number of files associated with this collection",
        examples=[15]
    )

    class Config:
        from_attributes = True


class CollectionStats(BaseModel):
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


class CollectionSearchRequest(BaseModel):
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
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score threshold (0-1)"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional filters to apply to search results",
        examples=[
            {
                "content_type": ["paragraph", "heading"],
                "language": "en",
                "min_confidence": 0.8,
                "tags": {"section": "installation"}
            }
        ]
    )


class CollectionListResponse(BaseModel):
    """Schema for paginated collection list responses."""

    data: List[CollectionResponse] = Field(
        ...,
        description="List of collections"
    )
    pagination: "PaginationMetadata" = Field(
        ...,
        description="Pagination metadata"
    )


class CollectionBatchRequest(BaseModel):
    """Schema for batch collection retrieval requests."""

    collection_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of collection UUIDs to retrieve (maximum 50 collections per request)",
        examples=[
            [
                "coll_123e4567-e89b-12d3-a456-426614174000",
                "coll_987fcdeb-51a2-43d7-8f9e-123456789abc",
                "coll_456789ab-cdef-1234-5678-9abcdef01234"
            ]
        ]
    )


class CollectionBatchResponse(BaseModel):
    """Schema for batch collection retrieval responses."""

    collections: List[CollectionResponse] = Field(
        ...,
        description="List of successfully retrieved collections with full details"
    )
    not_found: List[UUID] = Field(
        ...,
        description="List of collection IDs that were not found or not accessible"
    )
    total_requested: int = Field(
        ...,
        ge=1,
        description="Total number of collection IDs requested",
        examples=[3]
    )
    total_found: int = Field(
        ...,
        ge=0,
        description="Total number of collections successfully retrieved",
        examples=[2]
    )


# Import here to avoid circular imports
from .common import PaginationMetadata
CollectionListResponse.model_rebuild()
