"""
Pydantic schemas for request/response validation.
"""

from .collections import (
    CollectionCreateRequest,
    CollectionDetailResponse,
    CollectionResponse,
    CollectionSearchRequest,
    CollectionTypeEnum,
)
from .common import ErrorResponse, PaginationMetadata, PaginationParams
from .documents import DocumentCreateRequest, DocumentResponse
from .files import FileResponse, FileUploadResponse
from .projects import ProjectResponse
from .search import SearchResponse, SearchResult, SearchMetadata
from .websites import (
    CrawlOptionsSchema,
    CrawlProgressSchema,
    WebsiteCrawlCreateResponse,
    WebsiteCrawlJobListResponse,
    WebsiteCrawlJobResponse,
    WebsiteCrawlRequest,
    WebsitePageListResponse,
    WebsitePageResponse,
)
from .qa import (
    QAPairCreateRequest,
    QAPairUpdateRequest,
    QAPairBatchCreateRequest,
    QAPairImportRequest,
    QAPairResponse,
    QAPairListResponse,
    QAPairBatchCreateResponse,
)

__all__ = [
    # Common schemas
    "ErrorResponse",
    "PaginationMetadata",
    "PaginationParams",
    # Project schemas
    "ProjectResponse",
    # Collection schemas
    "CollectionCreateRequest",
    "CollectionResponse",
    "CollectionDetailResponse",
    "CollectionSearchRequest",
    "CollectionTypeEnum",
    # File schemas
    "FileResponse",
    "FileUploadResponse",
    # Document schemas
    "DocumentCreateRequest",
    "DocumentResponse",
    # Search schemas
    "SearchResponse",
    "SearchResult",
    "SearchMetadata",
    # Website schemas
    "CrawlOptionsSchema",
    "CrawlProgressSchema",
    "WebsiteCrawlCreateResponse",
    "WebsiteCrawlJobListResponse",
    "WebsiteCrawlJobResponse",
    "WebsiteCrawlRequest",
    "WebsitePageListResponse",
    "WebsitePageResponse",
    # QA schemas
    "QAPairCreateRequest",
    "QAPairUpdateRequest",
    "QAPairBatchCreateRequest",
    "QAPairImportRequest",
    "QAPairResponse",
    "QAPairListResponse",
    "QAPairBatchCreateResponse",
]
