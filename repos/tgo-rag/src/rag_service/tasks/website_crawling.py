"""
Website crawling tasks for RAG document generation.

This module provides Celery tasks for website crawling operations,
orchestrating the complete pipeline from URL crawling to document embedding.
"""

import asyncio
from typing import Any, Dict
from uuid import UUID

from .celery_app import celery_app
from ..logging_config import get_logger

logger = get_logger(__name__)


async def process_crawl_job_async(
    job_id: UUID,
    task_id: str = None,
) -> Dict[str, Any]:
    """
    Async function to process a website crawl job.
    
    This function orchestrates the complete crawling pipeline:
    1. Load crawl job configuration
    2. Initialize crawler with settings
    3. Crawl pages and extract content
    4. Create file records for each page
    5. Trigger document processing for RAG
    6. Update job status and metrics
    
    Args:
        job_id: UUID of the crawl job to process
        task_id: Optional Celery task ID for tracking
        
    Returns:
        Dictionary containing crawl results and metrics
    """
    from sqlalchemy import select, update
    from ..database import get_db_session
    from ..models import WebsiteCrawlJob, WebsitePage, File, Collection
    from ..services.crawler import WebCrawlerService, CrawlOptions
    from ..config import get_settings
    import os
    from uuid import uuid4
    
    settings = get_settings()
    
    try:
        # Load crawl job from database
        async with get_db_session() as db:
            result = await db.execute(
                select(WebsiteCrawlJob).where(WebsiteCrawlJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Crawl job not found: {job_id}")
                return {"status": "failed", "error": "Job not found"}
            
            # Update status to crawling
            job.status = "crawling"
            job.celery_task_id = task_id
            await db.commit()
            
            # Store job config for use outside session
            job_config = {
                "id": job.id,
                "project_id": job.project_id,
                "collection_id": job.collection_id,
                "start_url": job.start_url,
                "max_pages": job.max_pages,
                "max_depth": job.max_depth,
                "include_patterns": job.include_patterns,
                "exclude_patterns": job.exclude_patterns,
                "crawl_options": job.crawl_options or {},
            }
        
        # Initialize crawler
        options = CrawlOptions(
            render_js=job_config["crawl_options"].get("render_js", False),
            respect_robots_txt=job_config["crawl_options"].get("respect_robots_txt", True),
            delay_seconds=job_config["crawl_options"].get("delay_seconds", 1.0),
            user_agent=job_config["crawl_options"].get("user_agent"),
            timeout_seconds=job_config["crawl_options"].get("timeout_seconds", 30),
        )
        
        crawler = WebCrawlerService(
            start_url=job_config["start_url"],
            max_pages=job_config["max_pages"],
            max_depth=job_config["max_depth"],
            include_patterns=job_config["include_patterns"],
            exclude_patterns=job_config["exclude_patterns"],
            options=options,
        )
        
        pages_crawled = 0
        pages_processed = 0
        pages_failed = 0
        
        # Crawl website and process pages
        async for page in crawler.crawl_website():
            try:
                async with get_db_session() as db:
                    # Create WebsitePage record
                    website_page = WebsitePage(
                        crawl_job_id=job_config["id"],
                        collection_id=job_config["collection_id"],
                        project_id=job_config["project_id"],
                        url=page.url,
                        url_hash=page.url_hash,
                        title=page.title,
                        depth=page.depth,
                        content_markdown=page.content_markdown,
                        content_length=page.content_length,
                        content_hash=page.content_hash,
                        meta_description=page.meta_description,
                        http_status_code=page.http_status_code,
                        page_metadata=page.metadata,
                        status="fetched",
                    )
                    db.add(website_page)
                    await db.flush()
                    
                    # Create a virtual file for document processing
                    if page.content_markdown and page.content_length > 0:
                        # Save markdown content to temp file
                        file_id = uuid4()
                        safe_title = (page.title or "page")[:100].replace("/", "_")
                        filename = f"{safe_title}_{file_id}.md"
                        storage_path = os.path.join(settings.upload_dir, str(file_id))
                        
                        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
                        with open(storage_path, "w", encoding="utf-8") as f:
                            f.write(page.content_markdown)
                        
                        # Create File record
                        file_record = File(
                            id=file_id,
                            project_id=job_config["project_id"],
                            collection_id=job_config["collection_id"],
                            original_filename=filename,
                            file_size=len(page.content_markdown.encode("utf-8")),
                            content_type="text/markdown",
                            storage_provider="local",
                            storage_path=storage_path,
                            storage_metadata={
                                "source": "website_crawl",
                                "source_url": page.url,
                                "crawl_job_id": str(job_config["id"]),
                            },
                            status="pending",
                            description=page.meta_description,
                        )
                        db.add(file_record)

                        # Link page to file
                        website_page.file_id = file_id
                        website_page.status = "extracted"

                        await db.commit()

                        # Trigger document processing
                        from .document_processing import process_file_task
                        process_file_task.delay(
                            str(file_id),
                            str(job_config["collection_id"])
                        )

                        website_page.status = "processed"
                        pages_processed += 1
                    else:
                        website_page.status = "failed"
                        website_page.error_message = "No content extracted"
                        pages_failed += 1

                    await db.commit()

                    # Update job progress
                    await db.execute(
                        update(WebsiteCrawlJob)
                        .where(WebsiteCrawlJob.id == job_config["id"])
                        .values(
                            pages_discovered=crawler.pages_discovered,
                            pages_crawled=crawler.pages_crawled,
                            pages_processed=pages_processed,
                            pages_failed=pages_failed,
                        )
                    )
                    await db.commit()

                pages_crawled += 1

            except Exception as e:
                logger.error(f"Error processing page {page.url}: {e}")
                pages_failed += 1

                async with get_db_session() as db:
                    await db.execute(
                        update(WebsiteCrawlJob)
                        .where(WebsiteCrawlJob.id == job_config["id"])
                        .values(pages_failed=pages_failed)
                    )
                    await db.commit()

        # Update final job status
        async with get_db_session() as db:
            await db.execute(
                update(WebsiteCrawlJob)
                .where(WebsiteCrawlJob.id == job_config["id"])
                .values(
                    status="completed",
                    pages_discovered=crawler.pages_discovered,
                    pages_crawled=pages_crawled,
                    pages_processed=pages_processed,
                    pages_failed=pages_failed,
                )
            )
            await db.commit()

        logger.info(
            f"Crawl job {job_id} completed: "
            f"crawled={pages_crawled}, processed={pages_processed}, failed={pages_failed}"
        )

        return {
            "status": "completed",
            "job_id": str(job_id),
            "pages_crawled": pages_crawled,
            "pages_processed": pages_processed,
            "pages_failed": pages_failed,
        }

    except Exception as e:
        logger.error(f"Crawl job {job_id} failed: {e}")

        # Update job status to failed
        try:
            async with get_db_session() as db:
                await db.execute(
                    update(WebsiteCrawlJob)
                    .where(WebsiteCrawlJob.id == job_id)
                    .values(
                        status="failed",
                        error_message=str(e),
                    )
                )
                await db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")

        return {
            "status": "failed",
            "job_id": str(job_id),
            "error": str(e),
        }


@celery_app.task(bind=True, name="crawl_website_task")
def crawl_website_task(self, job_id: str) -> Dict[str, Any]:
    """
    Celery task for processing website crawl jobs.

    This task orchestrates the complete website crawling pipeline:
    1. Load crawl job configuration from database
    2. Initialize crawl4ai crawler
    3. Crawl pages and extract content
    4. Create file records for each page
    5. Trigger document processing for RAG embedding
    6. Update job status and metrics

    Args:
        job_id: UUID string of the crawl job to process

    Returns:
        Dictionary containing crawl results and metrics
    """
    from ..database import reset_db_state

    try:
        job_uuid = UUID(job_id)

        # Reset database state
        reset_db_state()

        # Run async processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                process_crawl_job_async(job_uuid, self.request.id)
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Crawl task failed for job {job_id}: {e}")
        return {
            "status": "failed",
            "job_id": job_id,
            "error": str(e),
        }

