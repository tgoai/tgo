"""RAG Collections proxy endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES, UPDATE_RESPONSES
from app.core.logging import get_logger
from app.core.security import get_authenticated_project
from app.schemas.rag import (
    CollectionCreateRequest,
    CollectionDetailResponse,
    CollectionListResponse,
    CollectionResponse,
    CollectionSearchRequest,
    CollectionTypeEnum,
    CollectionUpdateRequest,
    SearchResponse,
    WebsiteCrawlJobListResponse,
    WebsitePageListResponse,
)
from app.services.rag_client import rag_client

logger = get_logger("endpoints.rag_collections")
router = APIRouter()


@router.get(
    "",
    response_model=CollectionListResponse,
    responses=LIST_RESPONSES,
    summary="List Collections",
    description="""
    Retrieve all collections for the authenticated project with filtering and pagination.

    Collections are used to organize documents and files for RAG operations.
    All results are automatically scoped to the authenticated project.
    Supports filtering by collection_type (file, website, qa).
    """,
)
async def list_collections(
    display_name: Optional[str] = Query(
        None, description="Filter by collection display name (partial match)"
    ),
    collection_type: Optional[CollectionTypeEnum] = Query(
        None, description="Filter by collection type: file, website, or qa"
    ),
    tags: Optional[str] = Query(
        None, description="Filter by tags (comma-separated list)"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Number of collections to return"
    ),
    offset: int = Query(
        0, ge=0, description="Number of collections to skip"
    ),
    project_and_key = Depends(get_authenticated_project),
) -> CollectionListResponse:
    """List collections from RAG service."""
    logger.info(
        "Listing RAG collections",
        extra={
            "display_name": display_name,
            "collection_type": collection_type.value if collection_type else None,
            "tags": tags,
            "limit": limit,
            "offset": offset,
        }
    )
    project, _api_key = project_and_key
    project_id = str(project.id)

    result = await rag_client.list_collections(
        project_id=project_id,
        display_name=display_name,
        collection_type=collection_type.value if collection_type else None,
        tags=tags,
        limit=limit,
        offset=offset,
    )
    return CollectionListResponse.model_validate(result)


@router.post(
    "",
    response_model=CollectionResponse,
    responses=CREATE_RESPONSES,
    status_code=201,
    summary="Create Collection",
    description="""
    Create a new collection within the authenticated project for organizing documents and files.

    Collections help organize RAG content and can contain metadata about embedding models,
    chunk sizes, and other processing parameters. Collection is automatically scoped to the authenticated project.
    """,
)
async def create_collection(
    collection_data: CollectionCreateRequest,
    project_and_key = Depends(get_authenticated_project),
) -> CollectionResponse:
    """Create collection in RAG service."""
    logger.info(
        "Creating RAG collection",
        extra={
            "display_name": collection_data.display_name,
            "tags": collection_data.tags,
        }
    )
    project, _api_key = project_and_key
    project_id = str(project.id)

    result = await rag_client.create_collection(
        project_id=project_id,
        collection_data=collection_data.model_dump(exclude_none=True),
    )

    return CollectionResponse.model_validate(result)


@router.get(
    "/{collection_id}",
    response_model=CollectionDetailResponse,
    responses=CRUD_RESPONSES,
    summary="Get Collection",
    description="""
    Retrieve detailed information about a specific collection including metadata
    and optional statistics about contained documents and files. Collection must belong to the authenticated project.
    """,
)
async def get_collection(
    collection_id: UUID,
    include_stats: bool = Query(
        False, description="Include document and file count statistics"
    ),
    project_and_key = Depends(get_authenticated_project),
) -> CollectionDetailResponse:
    """Get collection from RAG service."""
    logger.info(
        "Getting RAG collection",
        extra={
            "collection_id": str(collection_id),
            "include_stats": include_stats,
        }
    )

    project, _api_key = project_and_key
    project_id = str(project.id)

    result = await rag_client.get_collection(
        project_id=project_id,
        collection_id=str(collection_id),
        include_stats=include_stats,
    )

    return CollectionDetailResponse.model_validate(result)


@router.patch(
    "/{collection_id}",
    response_model=CollectionResponse,
    responses=UPDATE_RESPONSES,
    summary="Update Collection",
    description="""
    Update an existing collection's properties including display name, description,
    tags, and metadata. Only provided fields will be updated. Collection must belong
    to the authenticated project and cannot be soft-deleted.

    This endpoint allows partial updates - you only need to provide the fields you want to change.
    All other fields will remain unchanged.
    """,
)
async def update_collection(
    collection_id: UUID,
    collection_data: CollectionUpdateRequest,
    project_and_key = Depends(get_authenticated_project),
) -> CollectionResponse:
    """Update collection in RAG service."""
    logger.info(
        "Updating RAG collection",
        extra={
            "collection_id": str(collection_id),
            "display_name": collection_data.display_name,
            "tags": collection_data.tags,
        }
    )
    project, _api_key = project_and_key
    project_id = str(project.id)


    result = await rag_client.update_collection(
        project_id=project_id,
        collection_id=str(collection_id),
        collection_data=collection_data.model_dump(exclude_none=True),
    )

    return CollectionResponse.model_validate(result)


@router.delete(
    "/{collection_id}",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Delete Collection",
    description="""
    Delete a specific collection by its UUID. This will set collection_id to NULL
    for associated files and documents but will not delete them. Collection must belong to the authenticated project.
    """,
)
async def delete_collection(
    collection_id: UUID,
    project_and_key = Depends(get_authenticated_project),
) -> None:
    """Delete collection from RAG service."""
    logger.info(
        "Deleting RAG collection",
        extra={"collection_id": str(collection_id)}
    )
    project, _api_key = project_and_key
    project_id = str(project.id)


    await rag_client.delete_collection(
        project_id=project_id,
        collection_id=str(collection_id),
    )


@router.post(
    "/{collection_id}/documents/search",
    response_model=SearchResponse,
    responses=CRUD_RESPONSES,
    summary="Search Collection Documents",
    description="""
    Perform semantic search for documents within a specific collection.

    This endpoint provides collection-scoped search capabilities for RAG operations.
    All results are automatically scoped to the authenticated project.
    """,
)
async def search_collection_documents(
    collection_id: UUID,
    search_request: CollectionSearchRequest,
    project_and_key = Depends(get_authenticated_project),
) -> SearchResponse:
    """Search documents in collection."""
    logger.info(
        "Searching RAG collection documents",
        extra={
            "collection_id": str(collection_id),
            "query": search_request.query,
            "limit": search_request.limit,
        }
    )
    project, _api_key = project_and_key
    project_id = str(project.id)

    result = await rag_client.search_collection_documents(
        project_id=project_id,
        collection_id=str(collection_id),
        search_data=search_request.model_dump(exclude_none=True),
    )

    return SearchResponse.model_validate(result)


@router.get(
    "/{collection_id}/crawl-jobs",
    response_model=WebsiteCrawlJobListResponse,
    responses=LIST_RESPONSES,
    summary="List Collection Crawl Jobs",
    description="""
    Retrieve all crawl jobs for a specific website collection.

    This endpoint returns the list of website crawl jobs associated with the collection.
    Only works for collections with collection_type='website'.
    Results are ordered by creation time (newest first).
    """,
)
async def list_collection_crawl_jobs(
    collection_id: UUID,
    status: Optional[str] = Query(
        None, description="Filter by job status (pending, crawling, completed, failed, cancelled)"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Number of crawl jobs to return"
    ),
    offset: int = Query(
        0, ge=0, description="Number of crawl jobs to skip"
    ),
    project_and_key=Depends(get_authenticated_project),
) -> WebsiteCrawlJobListResponse:
    """List crawl jobs for a website collection."""
    logger.info(
        "Listing collection crawl jobs",
        extra={
            "collection_id": str(collection_id),
            "status": status,
            "limit": limit,
            "offset": offset,
        }
    )
    project, _api_key = project_and_key
    project_id = str(project.id)

    result = await rag_client.list_collection_crawl_jobs(
        project_id=project_id,
        collection_id=str(collection_id),
        status=status,
        limit=limit,
        offset=offset,
    )
    return WebsiteCrawlJobListResponse.model_validate(result)


@router.get(
    "/{collection_id}/pages",
    response_model=WebsitePageListResponse,
    responses=LIST_RESPONSES,
    summary="List Collection Pages",
    description="""
    Retrieve all crawled pages for a specific website collection.

    This endpoint returns the list of website pages that have been crawled
    and associated with the collection. Only works for collections with
    collection_type='website'. Results are ordered by creation time (newest first).
    """,
)
async def list_collection_pages(
    collection_id: UUID,
    status: Optional[str] = Query(
        None, description="Filter by page status (pending, processing, completed, failed)"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Number of pages to return"
    ),
    offset: int = Query(
        0, ge=0, description="Number of pages to skip"
    ),
    project_and_key=Depends(get_authenticated_project),
) -> WebsitePageListResponse:
    """List crawled pages for a website collection."""
    logger.info(
        "Listing collection pages",
        extra={
            "collection_id": str(collection_id),
            "status": status,
            "limit": limit,
            "offset": offset,
        }
    )
    project, _api_key = project_and_key
    project_id = str(project.id)

    result = await rag_client.list_collection_pages(
        project_id=project_id,
        collection_id=str(collection_id),
        status=status,
        limit=limit,
        offset=offset,
    )
    return WebsitePageListResponse.model_validate(result)
