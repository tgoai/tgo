"""
Website crawling endpoints.

This module provides API endpoints for website crawling operations,
allowing users to crawl websites and generate RAG documents.
"""

import hashlib
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session_dependency
from ..logging_config import get_logger
from ..models import Collection, WebsiteCrawlJob, WebsitePage
from ..schemas.common import ErrorResponse, PaginationMetadata
from ..schemas.websites import (
    AddPageRequest,
    AddPageResponse,
    CrawlDeeperRequest,
    CrawlDeeperResponse,
    CrawlProgressSchema,
    WebsiteCrawlCreateResponse,
    WebsiteCrawlJobListResponse,
    WebsiteCrawlJobResponse,
    WebsiteCrawlRequest,
    WebsitePageListResponse,
    WebsitePageResponse,
)

router = APIRouter()
logger = get_logger(__name__)


def compute_url_hash(url: str) -> str:
    """Generate SHA-256 hash of URL for deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()


async def check_url_exists_in_collection(
    db: AsyncSession,
    collection_id: UUID,
    url_hash: str,
) -> Tuple[bool, Optional[str]]:
    """
    Check if a URL already exists in the collection's pages.

    Returns:
        Tuple of (exists: bool, status: Optional[str])
        - If exists=True, status contains the current page status
        - If exists=False, status is None
    """
    query = select(WebsitePage.status).where(
        and_(
            WebsitePage.collection_id == collection_id,
            WebsitePage.url_hash == url_hash,
        )
    )
    result = await db.execute(query)
    page_status = result.scalar_one_or_none()

    if page_status is not None:
        return (True, page_status)
    return (False, None)


async def check_urls_exist_in_collection(
    db: AsyncSession,
    collection_id: UUID,
    url_hashes: List[str],
) -> set:
    """
    Check which URLs already exist in the collection's pages.

    Returns:
        Set of url_hashes that already exist
    """
    if not url_hashes:
        return set()

    query = select(WebsitePage.url_hash).where(
        and_(
            WebsitePage.collection_id == collection_id,
            WebsitePage.url_hash.in_(url_hashes),
        )
    )
    result = await db.execute(query)
    existing_hashes = {row[0] for row in result.fetchall()}
    return existing_hashes


def _build_progress(job: WebsiteCrawlJob) -> CrawlProgressSchema:
    """Build progress schema from job."""
    # If job is completed/cancelled/failed, progress is 100%
    if job.status in ("completed", "cancelled", "failed"):
        progress_percent = 100.0
    else:
        # Calculate progress based on pages_discovered (actual work to do)
        # Not max_pages (which is just a limit)
        total = max(job.pages_discovered, 1)
        progress_percent = (job.pages_crawled / total) * 100 if total > 0 else 0
        progress_percent = min(progress_percent, 100.0)

    return CrawlProgressSchema(
        pages_discovered=job.pages_discovered,
        pages_crawled=job.pages_crawled,
        pages_processed=job.pages_processed,
        pages_failed=job.pages_failed,
        progress_percent=progress_percent,
    )


def _build_job_response(job: WebsiteCrawlJob) -> WebsiteCrawlJobResponse:
    """Build job response from model."""
    return WebsiteCrawlJobResponse(
        id=job.id,
        collection_id=job.collection_id,
        start_url=job.start_url,
        max_pages=job.max_pages,
        max_depth=job.max_depth,
        include_patterns=job.include_patterns,
        exclude_patterns=job.exclude_patterns,
        status=job.status,
        progress=_build_progress(job),
        crawl_options=job.crawl_options,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/crawl",
    response_model=WebsiteCrawlJobListResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_crawl_jobs(
    collection_id: Optional[UUID] = Query(None, description="Filter by collection ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    List all website crawl jobs for the specified project.
    """
    query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.deleted_at.is_(None),
            WebsiteCrawlJob.project_id == project_id,
        )
    )
    
    if collection_id:
        query = query.where(WebsiteCrawlJob.collection_id == collection_id)
    if status:
        query = query.where(WebsiteCrawlJob.status == status)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset(offset).limit(limit).order_by(WebsiteCrawlJob.created_at.desc())
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    job_responses = [_build_job_response(job) for job in jobs]
    
    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )
    
    return WebsiteCrawlJobListResponse(data=job_responses, pagination=pagination)


@router.post(
    "/crawl",
    response_model=WebsiteCrawlCreateResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "Collection not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_crawl_job(
    request: WebsiteCrawlRequest,
    collection_id: UUID = Query(..., description="Target collection ID"),
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Create a new website crawl job.
    
    This will start crawling the specified URL and generate RAG documents
    for all discovered pages within the configured limits.
    """
    # Verify collection exists and belongs to project
    collection_query = select(Collection).where(
        and_(
            Collection.id == collection_id,
            Collection.project_id == project_id,
            Collection.deleted_at.is_(None),
        )
    )
    collection_result = await db.execute(collection_query)
    collection = collection_result.scalar_one_or_none()
    
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Prepare crawl options
    crawl_options = None
    if request.options:
        crawl_options = request.options.model_dump()

    # Create crawl job
    job = WebsiteCrawlJob(
        project_id=project_id,
        collection_id=collection_id,
        start_url=str(request.start_url),
        max_pages=request.max_pages,
        max_depth=request.max_depth,
        include_patterns=request.include_patterns,
        exclude_patterns=request.exclude_patterns,
        crawl_options=crawl_options,
        status="pending",
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Queue crawl task
    from ..tasks.website_crawling import crawl_website_task

    try:
        task = crawl_website_task.delay(str(job.id))
        logger.info(f"Queued crawl job {job.id} with task {task.id}")
    except Exception as e:
        logger.warning(f"Failed to queue crawl task: {e}")

    return WebsiteCrawlCreateResponse(
        job_id=job.id,
        status=job.status,
        start_url=job.start_url,
        collection_id=job.collection_id,
        created_at=job.created_at,
        message="Crawl job created and queued for processing",
    )


@router.get(
    "/crawl/{job_id}",
    response_model=WebsiteCrawlJobResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_crawl_job(
    job_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Get details of a specific crawl job.
    """
    query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.id == job_id,
            WebsiteCrawlJob.project_id == project_id,
            WebsiteCrawlJob.deleted_at.is_(None),
        )
    )

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    return _build_job_response(job)


@router.post(
    "/crawl/{job_id}/cancel",
    response_model=WebsiteCrawlJobResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Job cannot be cancelled"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def cancel_crawl_job(
    job_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Cancel a running crawl job.
    """
    query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.id == job_id,
            WebsiteCrawlJob.project_id == project_id,
            WebsiteCrawlJob.deleted_at.is_(None),
        )
    )

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be cancelled (status: {job.status})"
        )

    # Update status
    job.status = "cancelled"
    await db.commit()
    await db.refresh(job)

    # Try to revoke Celery task
    if job.celery_task_id:
        try:
            from ..tasks.celery_app import celery_app
            celery_app.control.revoke(job.celery_task_id, terminate=True)
            logger.info(f"Revoked Celery task {job.celery_task_id}")
        except Exception as e:
            logger.warning(f"Failed to revoke task: {e}")

    return _build_job_response(job)


@router.delete(
    "/crawl/{job_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_crawl_job(
    job_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Delete a crawl job and all associated pages.
    """
    query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.id == job_id,
            WebsiteCrawlJob.project_id == project_id,
            WebsiteCrawlJob.deleted_at.is_(None),
        )
    )

    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    # Soft delete the job (cascade will handle pages)
    job.soft_delete()
    await db.commit()


@router.get(
    "/crawl/{job_id}/pages",
    response_model=WebsitePageListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_crawl_pages(
    job_id: UUID,
    status: Optional[str] = Query(None, description="Filter by page status"),
    limit: int = Query(20, ge=1, le=100, description="Number of pages to return"),
    offset: int = Query(0, ge=0, description="Number of pages to skip"),
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    List all pages crawled for a specific job.
    """
    # Verify job exists
    job_query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.id == job_id,
            WebsiteCrawlJob.project_id == project_id,
            WebsiteCrawlJob.deleted_at.is_(None),
        )
    )
    job_result = await db.execute(job_query)
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Crawl job not found")

    # Query pages
    query = select(WebsitePage).where(WebsitePage.crawl_job_id == job_id)

    if status:
        query = query.where(WebsitePage.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.offset(offset).limit(limit).order_by(WebsitePage.created_at.asc())

    result = await db.execute(query)
    pages = result.scalars().all()

    page_responses = [WebsitePageResponse.model_validate(page) for page in pages]

    pagination = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_next=offset + limit < total,
        has_previous=offset > 0,
    )

    return WebsitePageListResponse(data=page_responses, pagination=pagination)


@router.post(
    "/crawl/{job_id}/pages",
    response_model=AddPageResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "Crawl job not found"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def add_page_to_crawl_job(
    job_id: UUID,
    request: AddPageRequest,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Add a single page URL to an existing crawl job.

    This endpoint allows manually adding a new page to the crawl queue.
    The page will be crawled and processed like other pages in the job.

    Deduplication rules:
    - If the URL already exists in the collection, it will be skipped
    - If the URL is currently being crawled (pending/fetched), it will be skipped
    - New pages are added with depth=0 (as new starting points)
    """
    # Verify job exists and belongs to project
    job_query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.id == job_id,
            WebsiteCrawlJob.project_id == project_id,
            WebsiteCrawlJob.deleted_at.is_(None),
        )
    )
    job_result = await db.execute(job_query)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    # Check if job is in a valid state for adding pages
    if job.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add pages to job with status: {job.status}"
        )

    url = str(request.url)
    url_hash = compute_url_hash(url)

    # Check if URL already exists in collection
    exists, existing_status = await check_url_exists_in_collection(
        db, job.collection_id, url_hash
    )

    if exists:
        # Check if it's currently being crawled
        if existing_status in ("pending", "fetched"):
            return AddPageResponse(
                success=False,
                page_id=None,
                message=f"URL is currently being crawled (status: {existing_status})",
                status="crawling",
            )
        else:
            return AddPageResponse(
                success=False,
                page_id=None,
                message=f"URL already exists in collection (status: {existing_status})",
                status="exists",
            )

    # Create new page record
    new_page = WebsitePage(
        crawl_job_id=job_id,
        collection_id=job.collection_id,
        project_id=project_id,
        url=url,
        url_hash=url_hash,
        depth=0,  # Manual additions are treated as new starting points
        status="pending",
        content_length=0,
    )

    db.add(new_page)

    # Update job's pages_discovered count
    job.pages_discovered = (job.pages_discovered or 0) + 1

    await db.commit()
    await db.refresh(new_page)

    logger.info(f"Added page {url} to crawl job {job_id}")

    # Trigger crawl task if job is pending
    if job.status == "pending":
        from ..tasks.website_crawling import crawl_website_task
        try:
            task = crawl_website_task.delay(str(job_id))
            logger.info(f"Triggered crawl task {task.id} for job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to trigger crawl task: {e}")

    return AddPageResponse(
        success=True,
        page_id=new_page.id,
        message=f"Page added to crawl queue successfully",
        status="added",
    )


@router.post(
    "/pages/{page_id}/crawl-deeper",
    response_model=CrawlDeeperResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Page not found"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def crawl_deeper_from_page(
    page_id: UUID,
    request: CrawlDeeperRequest,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """
    Extract links from an existing page and add them to the crawl queue.

    This endpoint allows deep crawling from a specific page that has already
    been crawled. It extracts all links from the page's content and adds
    new URLs to the crawl queue.

    Deduplication rules:
    - URLs already in the collection are skipped
    - URLs currently being crawled are skipped
    - New pages have depth = source_page.depth + 1
    - Pages exceeding max_depth are not added
    """
    import fnmatch
    import re
    from urllib.parse import urljoin, urlparse

    # Get the source page
    page_query = select(WebsitePage).where(
        and_(
            WebsitePage.id == page_id,
            WebsitePage.project_id == project_id,
        )
    )
    page_result = await db.execute(page_query)
    source_page = page_result.scalar_one_or_none()

    if not source_page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Get the associated crawl job
    job_query = select(WebsiteCrawlJob).where(
        and_(
            WebsiteCrawlJob.id == source_page.crawl_job_id,
            WebsiteCrawlJob.deleted_at.is_(None),
        )
    )
    job_result = await db.execute(job_query)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Associated crawl job not found")

    # Check if page has content to extract links from
    if not source_page.content_markdown:
        return CrawlDeeperResponse(
            success=True,
            source_page_id=page_id,
            pages_added=0,
            pages_skipped=0,
            links_found=0,
            message="Page has no content to extract links from",
            added_urls=[],
        )

    # Calculate new depth and check max_depth limit
    new_depth = source_page.depth + 1
    max_allowed_depth = source_page.depth + request.max_depth

    if new_depth > max_allowed_depth:
        return CrawlDeeperResponse(
            success=True,
            source_page_id=page_id,
            pages_added=0,
            pages_skipped=0,
            links_found=0,
            message="Max depth reached, no pages added",
            added_urls=[],
        )

    # Extract links from content
    # Parse base domain from source page URL
    parsed_source = urlparse(source_page.url)
    base_domain = parsed_source.netloc

    # Simple regex for href extraction (same as in crawler.py)
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

    # Also look for markdown links
    md_link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)', re.IGNORECASE)

    raw_links = set()

    # Extract from HTML-style hrefs (if any HTML remnants)
    for match in href_pattern.finditer(source_page.content_markdown):
        raw_links.add(match.group(1))

    # Extract from markdown links
    for match in md_link_pattern.finditer(source_page.content_markdown):
        raw_links.add(match.group(2))

    # Also check page_metadata for stored links
    if source_page.page_metadata and "links" in source_page.page_metadata:
        for link in source_page.page_metadata.get("links", []):
            if isinstance(link, str):
                raw_links.add(link)
            elif isinstance(link, dict):
                raw_links.add(link.get("href", ""))

    # Normalize and filter links
    def normalize_url(url: str, base_url: str) -> Optional[str]:
        """Normalize and validate URL."""
        try:
            if not url or url.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                return None

            # Handle relative URLs
            if not url.startswith(('http://', 'https://')):
                url = urljoin(base_url, url)

            parsed = urlparse(url)

            # Remove fragments
            url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                url += f"?{parsed.query}"

            # Only allow same domain
            if parsed.netloc != base_domain:
                return None

            return url
        except Exception:
            return None

    def should_crawl(url: str) -> bool:
        """Check if URL matches include/exclude patterns."""
        # Use request patterns if provided, otherwise use job patterns
        exclude_patterns = request.exclude_patterns or job.exclude_patterns or []
        include_patterns = request.include_patterns or job.include_patterns or []

        for pattern in exclude_patterns:
            if fnmatch.fnmatch(url, pattern):
                return False

        if include_patterns:
            return any(fnmatch.fnmatch(url, p) for p in include_patterns)

        return True

    # Process and filter links
    valid_links = []
    for link in raw_links:
        normalized = normalize_url(link, source_page.url)
        if normalized and should_crawl(normalized):
            valid_links.append(normalized)

    valid_links = list(set(valid_links))  # Deduplicate
    links_found = len(valid_links)

    if not valid_links:
        return CrawlDeeperResponse(
            success=True,
            source_page_id=page_id,
            pages_added=0,
            pages_skipped=0,
            links_found=0,
            message="No valid links found in page",
            added_urls=[],
        )

    # Check which URLs already exist in collection
    url_to_hash = {url: compute_url_hash(url) for url in valid_links}
    existing_hashes = await check_urls_exist_in_collection(
        db, source_page.collection_id, list(url_to_hash.values())
    )

    # Filter out existing URLs
    new_urls = [url for url, h in url_to_hash.items() if h not in existing_hashes]
    skipped_count = len(valid_links) - len(new_urls)

    if not new_urls:
        return CrawlDeeperResponse(
            success=True,
            source_page_id=page_id,
            pages_added=0,
            pages_skipped=skipped_count,
            links_found=links_found,
            message="All discovered links already exist in collection",
            added_urls=[],
        )

    # Add new pages to the crawl queue
    added_urls = []
    for url in new_urls:
        new_page = WebsitePage(
            crawl_job_id=source_page.crawl_job_id,
            collection_id=source_page.collection_id,
            project_id=project_id,
            url=url,
            url_hash=url_to_hash[url],
            depth=new_depth,
            status="pending",
            content_length=0,
        )
        db.add(new_page)
        added_urls.append(url)

    # Update job's pages_discovered count
    job.pages_discovered = (job.pages_discovered or 0) + len(added_urls)

    await db.commit()

    logger.info(
        f"Added {len(added_urls)} pages from deep crawl of page {page_id}, "
        f"skipped {skipped_count} existing URLs"
    )

    # Trigger crawl task if job is pending or completed (restart crawling)
    if job.status in ("pending", "completed"):
        job.status = "crawling"
        await db.commit()

        from ..tasks.website_crawling import crawl_website_task
        try:
            task = crawl_website_task.delay(str(job.id))
            logger.info(f"Triggered crawl task {task.id} for job {job.id}")
        except Exception as e:
            logger.warning(f"Failed to trigger crawl task: {e}")

    return CrawlDeeperResponse(
        success=True,
        source_page_id=page_id,
        pages_added=len(added_urls),
        pages_skipped=skipped_count,
        links_found=links_found,
        message=f"Added {len(added_urls)} new pages to crawl queue",
        added_urls=added_urls,
    )

