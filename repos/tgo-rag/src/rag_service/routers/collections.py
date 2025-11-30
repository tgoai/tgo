"""
Collections management endpoints.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session_dependency
from ..logging_config import get_logger
from ..models import Collection, CollectionType, FileDocument, File as FileModel
from ..models import WebsiteCrawlJob, WebsitePage
from ..schemas.collections import (
    CollectionBatchRequest,
    CollectionBatchResponse,
    CollectionCreateRequest,
    CollectionDetailResponse,
    CollectionListResponse,
    CollectionResponse,
    CollectionSearchRequest,
    CollectionStats,
    CollectionTypeEnum,
    CollectionUpdateRequest,
)
from ..schemas.common import ErrorResponse
from ..schemas.common import PaginationMetadata
from ..schemas.search import SearchResponse
from ..schemas.websites import (
    CrawlProgressSchema,
    WebsiteCrawlJobListResponse,
    WebsiteCrawlJobResponse,
    WebsitePageListResponse,
    WebsitePageResponse,
)
from ..services.search import get_search_service

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "",
    response_model=CollectionListResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error - invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_collections(
    display_name: Optional[str] = Query(None, description="Filter by collection display name (partial match)"),
    collection_type: Optional[CollectionTypeEnum] = Query(None, description="Filter by collection type: file, website, or qa"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated list)"),
    limit: int = Query(20, ge=1, le=100, description="Number of collections to return"),
    offset: int = Query(0, ge=0, description="Number of collections to skip"),
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve all collections for the specified project (via project_id) with filtering, pagination, and file counts.

    Collections are used to organize documents and files for RAG operations.
    All results are scoped to the specified project.
    Each collection includes a file_count field showing the total number of associated files.
    Supports filtering by collection_type (file, website, qa).
    """
    # Build base query with file count using LEFT JOIN and COUNT
    # This efficiently gets file counts in a single query to avoid N+1 problems
    file_count_subquery = (
        select(
            FileModel.collection_id,
            func.count(FileModel.id).label('file_count')
        )
        .where(
            and_(
                FileModel.project_id == project_id,
                FileModel.deleted_at.is_(None)
            )
        )
        .group_by(FileModel.collection_id)
        .subquery()
    )

    # Main query with LEFT JOIN to include file counts
    query = (
        select(
            Collection,
            func.coalesce(file_count_subquery.c.file_count, 0).label('file_count')
        )
        .outerjoin(
            file_count_subquery,
            Collection.id == file_count_subquery.c.collection_id
        )
        .where(
            and_(
                Collection.deleted_at.is_(None),
                Collection.project_id == project_id
            )
        )
    )

    # Apply display name filter if provided
    if display_name:
        query = query.where(Collection.display_name.ilike(f"%{display_name}%"))

    # Apply collection type filter if provided
    if collection_type:
        # Convert schema enum to model enum
        model_collection_type = CollectionType(collection_type.value)
        query = query.where(Collection.collection_type == model_collection_type)

    # Apply tags filter if provided
    if tags:
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if tag_list:
            # Use PostgreSQL array overlap operator to check if any of the provided tags exist
            from sqlalchemy import text
            query = query.where(text("tags && :tag_list")).params(tag_list=tag_list)

    # Get total count for pagination (need to count from the main query)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    query = query.offset(offset).limit(limit).order_by(Collection.created_at.desc())

    # Execute query
    result = await db.execute(query)
    rows = result.all()

    # Convert to response models with file counts
    collection_responses = []
    for row in rows:
        collection = row[0]  # Collection object
        file_count = row[1]  # file_count from the query

        # Create response object manually to include file_count
        collection_response = CollectionResponse(
            id=collection.id,
            display_name=collection.display_name,
            description=collection.description,
            collection_type=CollectionTypeEnum(collection.collection_type.value),
            crawl_config=collection.crawl_config,
            collection_metadata=collection.collection_metadata,
            tags=collection.tags,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            deleted_at=collection.deleted_at,
            file_count=file_count
        )
        collection_responses.append(collection_response)
    
    # Create pagination metadata
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )
    
    return CollectionListResponse(
        data=collection_responses,
        pagination=pagination
    )


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - invalid input data"},
        422: {"model": ErrorResponse, "description": "Validation error - request data validation failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def create_collection(
    collection_data: CollectionCreateRequest,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Create a new collection within the specified project for organizing documents and files.

    Collections help organize RAG content and can contain metadata about embedding models,
    chunk sizes, and other processing parameters. Collection is scoped to the specified project.
    Supports collection_type to specify the source: file, website, or qa.
    """
    # Convert schema enum to model enum
    model_collection_type = CollectionType(collection_data.collection_type.value)

    # Create new collection with specified project_id
    collection = Collection(
        project_id=project_id,
        display_name=collection_data.display_name,
        description=collection_data.description,
        collection_type=model_collection_type,
        crawl_config=collection_data.crawl_config,
        collection_metadata=collection_data.collection_metadata,
        tags=collection_data.tags,
    )

    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    # Create response manually with file_count = 0 (new collection has no files)
    return CollectionResponse(
        id=collection.id,
        display_name=collection.display_name,
        description=collection.description,
        collection_type=CollectionTypeEnum(collection.collection_type.value),
        crawl_config=collection.crawl_config,
        collection_metadata=collection.collection_metadata,
        tags=collection.tags,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        deleted_at=collection.deleted_at,
        file_count=0
    )


@router.post(
    "/batch",
    response_model=CollectionBatchResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - too many collection IDs or invalid request"},
        422: {"model": ErrorResponse, "description": "Validation error - invalid UUIDs or empty array"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_collections_batch(
    request: CollectionBatchRequest,
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve detailed information for multiple collections by their IDs in a single request.

    This endpoint allows efficient batch retrieval of collection details, reducing the number
    of HTTP requests needed. Only collections belonging to the specified project are returned.

    Features:
    - Batch retrieval of up to 50 collections per request
    - Includes file_count for each collection
    - Returns partial results if some collections are not found
    - Excludes soft-deleted collections from results
    - Proper filtering by project ownership

    The response includes both found collections and a list of collection IDs that were
    not found or not accessible, allowing clients to handle partial results appropriately.
    """
    collection_ids = request.collection_ids
    total_requested = len(collection_ids)

    # Validate request size
    if total_requested > 50:
        raise HTTPException(
            status_code=400,
            detail="Too many collection IDs requested. Maximum 50 collections per batch request."
        )

    # Query all requested collections in a single database query
    collections_query = select(Collection).where(
        and_(
            Collection.id.in_(collection_ids),
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )

    collections_result = await db.execute(collections_query)
    found_collections = collections_result.scalars().all()

    # Get file counts for all found collections in a single query
    file_counts_query = select(
        FileModel.collection_id,
        func.count(FileModel.id).label('file_count')
    ).where(
        and_(
            FileModel.collection_id.in_([c.id for c in found_collections]),
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    ).group_by(FileModel.collection_id)

    file_counts_result = await db.execute(file_counts_query)
    file_counts_dict = {row.collection_id: row.file_count for row in file_counts_result}

    # Build response collections with file counts
    response_collections = []
    found_collection_ids = set()

    for collection in found_collections:
        found_collection_ids.add(collection.id)
        file_count = file_counts_dict.get(collection.id, 0)

        response_collections.append(CollectionResponse(
            id=collection.id,
            display_name=collection.display_name,
            description=collection.description,
            collection_type=CollectionTypeEnum(collection.collection_type.value),
            crawl_config=collection.crawl_config,
            collection_metadata=collection.collection_metadata,
            tags=collection.tags,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
            deleted_at=collection.deleted_at,
            file_count=file_count
        ))

    # Determine which collection IDs were not found
    not_found_ids = [cid for cid in collection_ids if cid not in found_collection_ids]
    total_found = len(response_collections)

    return CollectionBatchResponse(
        collections=response_collections,
        not_found=not_found_ids,
        total_requested=total_requested,
        total_found=total_found
    )


@router.get(
    "/{collection_id}",
    response_model=CollectionDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_collection(
    collection_id: UUID,
    include_stats: bool = Query(False, description="Include document and file count statistics"),
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve detailed information about a specific collection including metadata
    and optional statistics about contained documents and files. Collection must belong to the specified project.
    """
    # Always get file count using a separate query to avoid async issues
    file_count_query = select(func.count(FileModel.id)).where(
        and_(
            FileModel.collection_id == collection_id,
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    )
    file_count_result = await db.execute(file_count_query)
    file_count = file_count_result.scalar() or 0

    # Query collection with relationships if stats are requested
    if include_stats:
        query = select(Collection).options(
            selectinload(Collection.files),
            selectinload(Collection.documents)
        ).where(
            and_(
                Collection.id == collection_id,
                Collection.project_id == project_id,
                Collection.deleted_at.is_(None)
            )
        )
    else:
        query = select(Collection).where(
            and_(
                Collection.id == collection_id,
                Collection.project_id == project_id,
                Collection.deleted_at.is_(None)
            )
        )

    result = await db.execute(query)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found or not accessible")

    # Create response manually to avoid accessing the file_count property
    collection_response = CollectionResponse(
        id=collection.id,
        display_name=collection.display_name,
        description=collection.description,
        collection_type=CollectionTypeEnum(collection.collection_type.value),
        crawl_config=collection.crawl_config,
        collection_metadata=collection.collection_metadata,
        tags=collection.tags,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        deleted_at=collection.deleted_at,
        file_count=file_count
    )

    response_data = collection_response.model_dump()

    # Add statistics if requested
    if include_stats:
        # Calculate statistics
        document_count = len(collection.documents) if collection.documents else 0
        # Use the file_count we already calculated

        # Calculate total tokens
        total_tokens = 0
        last_updated = None

        if collection.documents:
            for doc in collection.documents:
                if doc.token_count:
                    total_tokens += doc.token_count
                if not last_updated or (doc.updated_at and doc.updated_at > last_updated):
                    last_updated = doc.updated_at

        stats = CollectionStats(
            document_count=document_count,
            file_count=file_count,
            total_tokens=total_tokens,
            last_updated=last_updated,
        )

        response_data["stats"] = stats.model_dump()

    return CollectionDetailResponse(**response_data)


@router.put(
    "/{collection_id}",
    response_model=CollectionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - invalid input data"},
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        422: {"model": ErrorResponse, "description": "Validation error - request data validation failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def update_collection(
    collection_id: UUID,
    collection_data: CollectionUpdateRequest,
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Update an existing collection's properties including display name, description,
    tags, and metadata. Only provided fields will be updated. Collection must belong
    to the specified project and cannot be soft-deleted.

    Args:
        collection_id: UUID of the collection to update
        collection_data: Collection update data with optional fields
        project_id: Project ID
        db: Database session

    Returns:
        Updated collection data

    Raises:
        HTTPException: 404 if collection not found or not accessible
        HTTPException: 400 if invalid input data provided
        HTTPException: 422 if validation fails
        HTTPException: 500 if database operation fails
    """
    # Find the collection with project filtering and soft-delete check
    query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )

    result = await db.execute(query)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=404,
            detail="Collection not found or not accessible"
        )

    # Track if any changes were made for logging
    changes_made = []

    # Update only provided fields
    if collection_data.display_name is not None:
        if collection.display_name != collection_data.display_name:
            collection.display_name = collection_data.display_name
            changes_made.append("display_name")

    if collection_data.description is not None:
        if collection.description != collection_data.description:
            collection.description = collection_data.description
            changes_made.append("description")

    if collection_data.collection_metadata is not None:
        if collection.collection_metadata != collection_data.collection_metadata:
            collection.collection_metadata = collection_data.collection_metadata
            changes_made.append("collection_metadata")

    if collection_data.tags is not None:
        if collection.tags != collection_data.tags:
            collection.tags = collection_data.tags
            changes_made.append("tags")

    if collection_data.collection_type is not None:
        model_collection_type = CollectionType(collection_data.collection_type.value)
        if collection.collection_type != model_collection_type:
            collection.collection_type = model_collection_type
            changes_made.append("collection_type")

    if collection_data.crawl_config is not None:
        if collection.crawl_config != collection_data.crawl_config:
            collection.crawl_config = collection_data.crawl_config
            changes_made.append("crawl_config")

    # The updated_at timestamp will be automatically updated by SQLAlchemy
    # when any field is modified due to the onupdate=func.current_timestamp() setting
    if changes_made:

        # Log the update operation
        logger.info(
            f"Collection updated: {collection_id} (project: {project_id}) - changes: {', '.join(changes_made)}",
            extra={
                "collection_id": str(collection_id),
                "project_id": str(project_id),
                "changes": changes_made,
                "display_name": collection.display_name
            }
        )

    # Commit the changes
    try:
        await db.commit()
        await db.refresh(collection)
    except Exception as e:
        await db.rollback()
        logger.error(
            f"Failed to update collection {collection_id} (project: {project_id}): {str(e)}",
            extra={
                "collection_id": str(collection_id),
                "project_id": str(project_id),
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to update collection"
        )

    # Get current file count for the updated collection
    file_count_query = select(func.count(FileModel.id)).where(
        and_(
            FileModel.collection_id == collection_id,
            FileModel.project_id == project_id,
            FileModel.deleted_at.is_(None)
        )
    )
    file_count_result = await db.execute(file_count_query)
    file_count = file_count_result.scalar() or 0

    # Create response manually to include file_count
    return CollectionResponse(
        id=collection.id,
        display_name=collection.display_name,
        description=collection.description,
        collection_type=CollectionTypeEnum(collection.collection_type.value),
        crawl_config=collection.crawl_config,
        collection_metadata=collection.collection_metadata,
        tags=collection.tags,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        deleted_at=collection.deleted_at,
        file_count=file_count
    )


@router.delete(
    "/{collection_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def delete_collection(
    collection_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Delete a specific collection by its UUID. This will set collection_id to NULL
    for associated files and documents but will not delete them. Collection must belong to the specified project.
    """
    # Find the collection with project filtering
    query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )

    result = await db.execute(query)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found or not accessible")
    
    # Soft delete the collection
    collection.soft_delete()
    
    await db.commit()


@router.get(
    "/{collection_id}/documents",
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        422: {"model": ErrorResponse, "description": "Validation error - invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_collection_documents(
    collection_id: UUID,
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    min_confidence: Optional[float] = Query(None, ge=0, le=1, description="Minimum confidence score threshold"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    limit: int = Query(20, ge=1, le=100, description="Number of documents to return"),
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve all documents within a specific collection with filtering and pagination.

    This endpoint provides collection-scoped document access for RAG operations.
    All results are scoped to the specified project.
    """
    # Verify collection exists and belongs to the project
    collection_query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found or not accessible")

    # Build documents query with project filtering for multi-tenant isolation
    query = select(FileDocument).where(
        and_(
            FileDocument.collection_id == collection_id,
            FileDocument.project_id == project_id
        )
    )
    
    # Apply filters
    if content_type:
        query = query.where(FileDocument.content_type == content_type)
    if language:
        query = query.where(FileDocument.language == language)
    if min_confidence is not None:
        query = query.where(FileDocument.confidence_score >= min_confidence)
    
    # Apply sorting
    sort_column = getattr(FileDocument, sort_by, FileDocument.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    documents = result.scalars().all()
    
    # Convert to response models
    from ..schemas.documents import DocumentResponse, DocumentListResponse
    document_responses = [DocumentResponse.model_validate(doc) for doc in documents]
    
    # Create pagination metadata
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )
    
    return DocumentListResponse(
        data=document_responses,
        pagination=pagination
    )


@router.post(
    "/{collection_id}/documents/search",
    response_model=SearchResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        422: {"model": ErrorResponse, "description": "Validation error - invalid search request"},
        500: {"model": ErrorResponse, "description": "Internal server error - search service failed"}
    }
)
async def search_collection_documents(
    collection_id: UUID,
    search_request: CollectionSearchRequest,
    project_id: UUID = Query(..., description="Project ID", example="11111111-1111-1111-1111-111111111111"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Perform semantic search for documents within a specific collection.

    This endpoint provides collection-scoped search capabilities for RAG operations.
    All results are scoped to the specified project.
    """
    # Verify collection exists and belongs to the project
    collection_query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found or not accessible")
    
    # Perform semantic search using the search service
    search_service = get_search_service()

    # Use hybrid search by default for better results with project filtering
    search_response = await search_service.hybrid_search(
        query=search_request.query,
        project_id=project_id,
        collection_id=collection_id,
        limit=search_request.limit,
        min_score=search_request.min_score,
        filters=search_request.filters
    )

    return search_response


@router.get(
    "/{collection_id}/crawl-jobs",
    response_model=WebsiteCrawlJobListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        400: {"model": ErrorResponse, "description": "Collection is not of type 'website'"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_collection_crawl_jobs(
    collection_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Number of crawl jobs to return"),
    offset: int = Query(0, ge=0, description="Number of crawl jobs to skip"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve all crawl jobs for a specific website collection.

    This endpoint returns the list of website crawl jobs associated with the collection.
    Only works for collections with collection_type='website'.
    Results are ordered by creation time (newest first).
    """
    # Verify collection exists, belongs to project, and is website type
    collection_query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found or not accessible")

    if collection.collection_type != CollectionType.website:
        raise HTTPException(
            status_code=400,
            detail=f"Collection is not of type 'website'. Current type: {collection.collection_type.value}"
        )

    # Build query for crawl jobs
    query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.collection_id == collection_id,
            WebsiteCrawlJob.project_id == project_id,
            WebsiteCrawlJob.deleted_at.is_(None)
        )
    )

    # Apply status filter if provided
    if status:
        query = query.where(WebsiteCrawlJob.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(WebsiteCrawlJob.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    crawl_jobs = result.scalars().all()

    # Convert to response models
    job_responses = []
    for job in crawl_jobs:
        # Calculate progress percentage
        # If job is completed/cancelled/failed, progress is 100%
        if job.status in ("completed", "cancelled", "failed"):
            progress_percent = 100.0
        else:
            # Calculate based on pages_discovered (actual work to do)
            # Not max_pages (which is just a limit)
            total = max(job.pages_discovered, 1)
            progress_percent = min(100.0, (job.pages_crawled / total) * 100) if total > 0 else 0.0

        progress = CrawlProgressSchema(
            pages_discovered=job.pages_discovered,
            pages_crawled=job.pages_crawled,
            pages_processed=job.pages_processed,
            pages_failed=job.pages_failed,
            progress_percent=progress_percent,
        )

        job_responses.append(WebsiteCrawlJobResponse(
            id=job.id,
            collection_id=job.collection_id,
            start_url=job.start_url,
            max_pages=job.max_pages,
            max_depth=job.max_depth,
            include_patterns=job.include_patterns,
            exclude_patterns=job.exclude_patterns,
            status=job.status,
            progress=progress,
            crawl_options=job.crawl_options,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ))

    # Create pagination metadata
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )

    return WebsiteCrawlJobListResponse(
        data=job_responses,
        pagination=pagination
    )


@router.get(
    "/{collection_id}/pages",
    response_model=WebsitePageListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found or not accessible"},
        400: {"model": ErrorResponse, "description": "Collection is not of type 'website'"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_collection_pages(
    collection_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Number of pages to return"),
    offset: int = Query(0, ge=0, description="Number of pages to skip"),
    status: Optional[str] = Query(None, description="Filter by page status"),
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Retrieve all crawled pages for a specific website collection.

    This endpoint returns the list of website pages that have been crawled
    and associated with the collection. Only works for collections with
    collection_type='website'. Results are ordered by creation time (newest first).
    """
    # Verify collection exists, belongs to project, and is website type
    collection_query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None)
        )
    )
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found or not accessible")

    if collection.collection_type != CollectionType.website:
        raise HTTPException(
            status_code=400,
            detail=f"Collection is not of type 'website'. Current type: {collection.collection_type.value}"
        )

    # Build query for pages
    query = select(WebsitePage).where(
        and_(
            WebsitePage.collection_id == collection_id,
            WebsitePage.project_id == project_id,
        )
    )

    # Apply status filter if provided
    if status:
        query = query.where(WebsitePage.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    query = query.order_by(WebsitePage.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    pages = result.scalars().all()

    # Convert to response models
    page_responses = [
        WebsitePageResponse(
            id=page.id,
            crawl_job_id=page.crawl_job_id,
            collection_id=page.collection_id,
            url=page.url,
            title=page.title,
            depth=page.depth,
            content_length=page.content_length,
            meta_description=page.meta_description,
            status=page.status,
            http_status_code=page.http_status_code,
            file_id=page.file_id,
            error_message=page.error_message,
            created_at=page.created_at,
            updated_at=page.updated_at,
        )
        for page in pages
    ]

    # Create pagination metadata
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )

    return WebsitePageListResponse(
        data=page_responses,
        pagination=pagination
    )
