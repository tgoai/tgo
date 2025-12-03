"""RAG Website Pages proxy endpoints.

Provides JWT-authenticated endpoints for staff to manage website pages in collections.
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
    CrawlProgressSchema,
    WebsitePageListResponse,
    WebsitePageResponse,
)
from app.services.rag_client import rag_client

logger = get_logger("endpoints.rag_websites")
router = APIRouter()


def _check_project(current_user: Staff) -> str:
    """Check if staff has a valid project and return project_id."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )
    return str(current_user.project_id)


@router.get(
    "/pages",
    response_model=WebsitePageListResponse,
    responses=LIST_RESPONSES,
    summary="List Pages",
    description="""
    List all pages in a collection.

    When tree_depth is specified, the response includes child pages in a hierarchical structure:
    - tree_depth=0 or None: Flat list (no children)
    - tree_depth=1: Include direct children only
    - tree_depth=2: Include children and grandchildren
    - tree_depth=-1: Include all descendants (unlimited depth)

    When no parent_page_id filter is specified and tree_depth > 0, returns root pages
    (where parent_page_id IS NULL) with their children.
    """,
)
async def list_pages(
    collection_id: UUID = Query(..., description="Collection ID"),
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by page status"
    ),
    depth: Optional[int] = Query(None, description="Filter by depth"),
    parent_page_id: Optional[UUID] = Query(None, description="Filter by parent page ID"),
    tree_depth: Optional[int] = Query(
        None,
        ge=-1,
        le=10,
        description="Number of child levels to include. 0/None=no children, 1=direct children, -1=unlimited"
    ),
    limit: int = Query(20, ge=1, le=100, description="Number of pages to return"),
    offset: int = Query(0, ge=0, description="Number of pages to skip"),
    current_user: Staff = Depends(get_current_active_user),
) -> WebsitePageListResponse:
    """List pages in a collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Listing website pages",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id),
            "status": status_filter,
            "depth": depth,
            "tree_depth": tree_depth,
        },
    )

    result = await rag_client.list_website_pages(
        project_id=project_id,
        collection_id=str(collection_id),
        status=status_filter,
        depth=depth,
        parent_page_id=str(parent_page_id) if parent_page_id else None,
        tree_depth=tree_depth,
        limit=limit,
        offset=offset,
    )
    return WebsitePageListResponse.model_validate(result)


@router.get(
    "/pages/{page_id}",
    response_model=WebsitePageResponse,
    responses=CRUD_RESPONSES,
    summary="Get Page",
    description="Get details of a specific page.",
)
async def get_page(
    page_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> WebsitePageResponse:
    """Get a specific page."""
    project_id = _check_project(current_user)

    logger.info(
        "Getting website page",
        extra={"project_id": project_id, "page_id": str(page_id)},
    )

    result = await rag_client.get_website_page(
        project_id=project_id,
        page_id=str(page_id),
    )
    return WebsitePageResponse.model_validate(result)


@router.post(
    "/pages",
    response_model=AddPageResponse,
    responses=CREATE_RESPONSES,
    status_code=201,
    summary="Add Page",
    description="""
    Add a page to crawl in a collection.

    This will create a page record and trigger crawling.
    If max_depth > 0, discovered links will also be crawled.

    Page Hierarchy:
    - If `parent_page_id` is provided, the new page will be a child of that page
    - The new page's depth will be parent.depth + 1
    - This allows building hierarchical page structures

    Deduplication:
    - If the URL already exists in the collection, it will be skipped
    """,
)
async def add_page(
    page_data: AddPageRequest,
    collection_id: UUID = Query(..., description="Target collection ID"),
    current_user: Staff = Depends(get_current_active_user),
) -> AddPageResponse:
    """Add a page to crawl in a collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Adding website page",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id),
            "url": page_data.url,
            "max_depth": page_data.max_depth,
            "parent_page_id": str(page_data.parent_page_id) if page_data.parent_page_id else None,
        },
    )

    # Convert to dict and ensure UUIDs are serialized as strings
    request_data = page_data.model_dump(exclude_none=True, mode="json")

    result = await rag_client.add_website_page(
        project_id=project_id,
        collection_id=str(collection_id),
        page_data=request_data,
    )
    return AddPageResponse.model_validate(result)


@router.delete(
    "/pages/{page_id}",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Delete Page",
    description="Delete a page from the collection.",
)
async def delete_page(
    page_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """Delete a page from the collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Deleting website page",
        extra={"project_id": project_id, "page_id": str(page_id)},
    )

    await rag_client.delete_website_page(
        project_id=project_id,
        page_id=str(page_id),
    )


@router.post(
    "/pages/{page_id}/recrawl",
    response_model=AddPageResponse,
    responses=CRUD_RESPONSES,
    summary="Recrawl Page",
    description="Trigger re-crawling of an existing page.",
)
async def recrawl_page(
    page_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> AddPageResponse:
    """Recrawl an existing page."""
    project_id = _check_project(current_user)

    logger.info(
        "Recrawling website page",
        extra={"project_id": project_id, "page_id": str(page_id)},
    )

    result = await rag_client.recrawl_website_page(
        project_id=project_id,
        page_id=str(page_id),
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
    project_id = _check_project(current_user)

    logger.info(
        "Crawl deeper from page",
        extra={
            "project_id": project_id,
            "page_id": str(page_id),
            "max_depth": crawl_data.max_depth,
        },
    )

    result = await rag_client.crawl_deeper_from_page(
        project_id=project_id,
        page_id=str(page_id),
        crawl_data=crawl_data.model_dump(exclude_none=True),
    )
    return CrawlDeeperResponse.model_validate(result)


@router.get(
    "/progress",
    response_model=CrawlProgressSchema,
    responses=CRUD_RESPONSES,
    summary="Get Crawl Progress",
    description="Get crawl progress for a collection.",
)
async def get_crawl_progress(
    collection_id: UUID = Query(..., description="Collection ID"),
    current_user: Staff = Depends(get_current_active_user),
) -> CrawlProgressSchema:
    """Get crawl progress for a collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Getting crawl progress",
        extra={"project_id": project_id, "collection_id": str(collection_id)},
    )

    result = await rag_client.get_crawl_progress(
        project_id=project_id,
        collection_id=str(collection_id),
    )
    return CrawlProgressSchema.model_validate(result)
