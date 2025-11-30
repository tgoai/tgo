"""RAG Website Crawl proxy endpoints.

Provides JWT-authenticated endpoints for staff to manage website crawl jobs.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES
from app.core.security import get_current_active_user
from app.core.logging import get_logger
from app.models.staff import Staff
from app.schemas.rag import (
    AddPageRequest,
    AddPageResponse,
    CrawlDeeperRequest,
    CrawlDeeperResponse,
    WebsiteCrawlCreateResponse,
    WebsiteCrawlJobListResponse,
    WebsiteCrawlJobResponse,
    WebsiteCrawlRequest,
    WebsitePageListResponse,
)
from app.services.rag_client import rag_client

logger = get_logger("endpoints.rag_websites")
router = APIRouter()


@router.get(
    "/crawl",
    response_model=WebsiteCrawlJobListResponse,
    responses=LIST_RESPONSES,
    summary="List Crawl Jobs",
    description="List all website crawl jobs for the current project.",
)
async def list_crawl_jobs(
    collection_id: Optional[UUID] = Query(None, description="Filter by collection ID"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by status"
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    current_user: Staff = Depends(get_current_active_user),
) -> WebsiteCrawlJobListResponse:
    """List crawl jobs from RAG service."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Listing crawl jobs",
        extra={
            "project_id": str(current_user.project_id),
            "collection_id": str(collection_id) if collection_id else None,
            "status": status_filter,
        },
    )

    result = await rag_client.list_crawl_jobs(
        project_id=str(current_user.project_id),
        collection_id=str(collection_id) if collection_id else None,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return WebsiteCrawlJobListResponse.model_validate(result)


@router.post(
    "/crawl",
    response_model=WebsiteCrawlCreateResponse,
    responses=CREATE_RESPONSES,
    status_code=201,
    summary="Create Crawl Job",
    description="Create a new website crawl job to crawl and index web pages.",
)
async def create_crawl_job(
    crawl_data: WebsiteCrawlRequest,
    collection_id: UUID = Query(..., description="Target collection ID"),
    current_user: Staff = Depends(get_current_active_user),
) -> WebsiteCrawlCreateResponse:
    """Create a new crawl job in RAG service."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Creating crawl job",
        extra={
            "project_id": str(current_user.project_id),
            "collection_id": str(collection_id),
            "start_url": crawl_data.start_url,
        },
    )

    result = await rag_client.create_crawl_job(
        project_id=str(current_user.project_id),
        collection_id=str(collection_id),
        crawl_data=crawl_data.model_dump(exclude_none=True),
    )
    return WebsiteCrawlCreateResponse.model_validate(result)


@router.get(
    "/crawl/{job_id}",
    response_model=WebsiteCrawlJobResponse,
    responses=CRUD_RESPONSES,
    summary="Get Crawl Job",
    description="Get details of a specific crawl job.",
)
async def get_crawl_job(
    job_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> WebsiteCrawlJobResponse:
    """Get a specific crawl job from RAG service."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Getting crawl job",
        extra={"project_id": str(current_user.project_id), "job_id": str(job_id)},
    )

    result = await rag_client.get_crawl_job(
        project_id=str(current_user.project_id),
        job_id=str(job_id),
    )
    return WebsiteCrawlJobResponse.model_validate(result)


@router.delete(
    "/crawl/{job_id}",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Delete Crawl Job",
    description="Delete a crawl job and all associated pages.",
)
async def delete_crawl_job(
    job_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """Delete a crawl job from RAG service."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Deleting crawl job",
        extra={"project_id": str(current_user.project_id), "job_id": str(job_id)},
    )

    await rag_client.delete_crawl_job(
        project_id=str(current_user.project_id),
        job_id=str(job_id),
    )


@router.post(
    "/crawl/{job_id}/cancel",
    response_model=WebsiteCrawlJobResponse,
    responses=CRUD_RESPONSES,
    summary="Cancel Crawl Job",
    description="Cancel a running crawl job.",
)
async def cancel_crawl_job(
    job_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> WebsiteCrawlJobResponse:
    """Cancel a running crawl job."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Cancelling crawl job",
        extra={"project_id": str(current_user.project_id), "job_id": str(job_id)},
    )

    result = await rag_client.cancel_crawl_job(
        project_id=str(current_user.project_id),
        job_id=str(job_id),
    )
    return WebsiteCrawlJobResponse.model_validate(result)


@router.get(
    "/crawl/{job_id}/pages",
    response_model=WebsitePageListResponse,
    responses=LIST_RESPONSES,
    summary="List Crawl Pages",
    description="List all pages crawled for a specific job.",
)
async def list_crawl_pages(
    job_id: UUID,
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by page status"
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of pages to return"),
    offset: int = Query(0, ge=0, description="Number of pages to skip"),
    current_user: Staff = Depends(get_current_active_user),
) -> WebsitePageListResponse:
    """List pages for a specific crawl job."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Listing crawl pages",
        extra={
            "project_id": str(current_user.project_id),
            "job_id": str(job_id),
            "status": status_filter,
        },
    )

    result = await rag_client.list_crawl_pages(
        project_id=str(current_user.project_id),
        job_id=str(job_id),
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return WebsitePageListResponse.model_validate(result)


@router.post(
    "/crawl/{job_id}/pages",
    response_model=AddPageResponse,
    responses=CREATE_RESPONSES,
    status_code=201,
    summary="Add Page To Crawl Job",
    description="""
    Add a single page URL to an existing crawl job.

    This endpoint allows manually adding a new page to the crawl queue.
    The page will be crawled and processed like other pages in the job.

    Deduplication rules:
    - If the URL already exists in the collection, it will be skipped
    - If the URL is currently being crawled (pending/fetched), it will be skipped
    - New pages are added with depth=0 (as new starting points)
    """,
)
async def add_page_to_crawl_job(
    job_id: UUID,
    page_data: AddPageRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> AddPageResponse:
    """Add a single page to an existing crawl job."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Adding page to crawl job",
        extra={
            "project_id": str(current_user.project_id),
            "job_id": str(job_id),
            "url": page_data.url,
        },
    )

    result = await rag_client.add_page_to_crawl_job(
        project_id=str(current_user.project_id),
        job_id=str(job_id),
        url=page_data.url,
    )
    return AddPageResponse.model_validate(result)


@router.post(
    "/pages/{page_id}/crawl-deeper",
    response_model=CrawlDeeperResponse,
    responses=CRUD_RESPONSES,
    summary="Crawl Deeper From Page",
    description="""
    Extract links from an existing page and add them to the crawl queue.

    This endpoint allows deep crawling from a specific page that has already
    been crawled. It extracts all links from the page's content and adds
    new URLs to the crawl queue.

    Deduplication rules:
    - URLs already in the collection are skipped
    - URLs currently being crawled are skipped
    - New pages have depth = source_page.depth + 1
    - Pages exceeding max_depth are not added
    """,
)
async def crawl_deeper_from_page(
    page_id: UUID,
    crawl_data: CrawlDeeperRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> CrawlDeeperResponse:
    """Extract links from an existing page and add them to the crawl queue."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )

    logger.info(
        "Crawl deeper from page",
        extra={
            "project_id": str(current_user.project_id),
            "page_id": str(page_id),
            "max_depth": crawl_data.max_depth,
        },
    )

    result = await rag_client.crawl_deeper_from_page(
        project_id=str(current_user.project_id),
        page_id=str(page_id),
        crawl_data=crawl_data.model_dump(exclude_none=True),
    )
    return CrawlDeeperResponse.model_validate(result)
