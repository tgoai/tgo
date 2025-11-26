"""
Maintenance tasks for the RAG service.

This module provides periodic maintenance tasks including:
- Cleanup of failed tasks and orphaned records
- Database maintenance and optimization
- File system cleanup for orphaned files
- Performance monitoring and health checks

Key Components:
- Failed task cleanup and recovery
- Orphaned file detection and removal
- Database optimization tasks
- System health monitoring
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import select, delete, and_
from sqlalchemy.exc import SQLAlchemyError

from .celery_app import celery_app
from .document_processing_errors import ProcessingStatus
from ..database import get_db_session
from ..logging_config import get_logger
from ..models import File, FileDocument

logger = get_logger(__name__)


@celery_app.task(name="src.rag_service.tasks.maintenance.cleanup_failed_tasks")
def cleanup_failed_tasks() -> Dict[str, Any]:
    """
    Cleanup failed tasks and orphaned records.
    
    This task performs periodic maintenance including:
    - Removing old failed file records
    - Cleaning up orphaned document chunks
    - Resetting stuck processing tasks
    - Logging cleanup statistics
    
    Returns:
        Dictionary containing cleanup statistics
    """
    import asyncio
    from ..database import reset_db_state
    
    try:
        # Reset database state before creating new event loop
        # This prevents 'Future attached to a different loop' errors
        reset_db_state()
        
        # Run the async cleanup function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_cleanup_failed_tasks_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Maintenance task failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "cleaned_files": 0,
            "cleaned_documents": 0,
            "reset_tasks": 0
        }


async def _cleanup_failed_tasks_async() -> Dict[str, Any]:
    """
    Async implementation of failed task cleanup.
    
    Returns:
        Dictionary containing cleanup statistics
    """
    start_time = datetime.now()
    cleaned_files = 0
    cleaned_documents = 0
    reset_tasks = 0
    
    try:
        async with get_db_session() as db:
            # Define cleanup thresholds
            failed_threshold = datetime.now() - timedelta(days=7)  # Remove failed tasks older than 7 days
            stuck_threshold = datetime.now() - timedelta(hours=2)  # Reset tasks stuck for more than 2 hours
            
            # 1. Clean up old failed file records
            logger.info("Starting cleanup of old failed file records")
            
            failed_files_query = select(File).where(
                and_(
                    File.status == ProcessingStatus.FAILED.value,
                    File.updated_at < failed_threshold
                )
            )
            
            result = await db.execute(failed_files_query)
            failed_files = result.scalars().all()
            
            for file_record in failed_files:
                try:
                    # Delete associated documents first
                    await db.execute(
                        delete(FileDocument).where(FileDocument.file_id == file_record.id)
                    )
                    
                    # Delete the file record
                    await db.delete(file_record)
                    cleaned_files += 1
                    
                    logger.debug(f"Cleaned up failed file: {file_record.id}")
                    
                except Exception as e:
                    logger.error(f"Error cleaning up file {file_record.id}: {e}")
                    continue
            
            # 2. Clean up orphaned document chunks (documents without parent files)
            logger.info("Starting cleanup of orphaned document chunks")
            
            orphaned_docs_query = select(FileDocument).where(
                ~FileDocument.file_id.in_(
                    select(File.id)
                )
            )
            
            result = await db.execute(orphaned_docs_query)
            orphaned_docs = result.scalars().all()
            
            for doc in orphaned_docs:
                try:
                    await db.delete(doc)
                    cleaned_documents += 1
                    logger.debug(f"Cleaned up orphaned document: {doc.id}")
                    
                except Exception as e:
                    logger.error(f"Error cleaning up document {doc.id}: {e}")
                    continue
            
            # 3. Reset stuck processing tasks
            logger.info("Starting reset of stuck processing tasks")
            
            stuck_files_query = select(File).where(
                and_(
                    File.status == ProcessingStatus.PROCESSING.value,
                    File.updated_at < stuck_threshold
                )
            )
            
            result = await db.execute(stuck_files_query)
            stuck_files = result.scalars().all()
            
            for file_record in stuck_files:
                try:
                    file_record.status = ProcessingStatus.FAILED.value
                    file_record.error_message = "Task reset due to timeout during maintenance"
                    reset_tasks += 1
                    
                    logger.debug(f"Reset stuck task for file: {file_record.id}")
                    
                except Exception as e:
                    logger.error(f"Error resetting stuck task for file {file_record.id}: {e}")
                    continue
            
            # Commit all changes
            await db.commit()
            
        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Log summary
        logger.info(
            f"Maintenance cleanup completed: "
            f"cleaned {cleaned_files} files, "
            f"{cleaned_documents} documents, "
            f"reset {reset_tasks} stuck tasks "
            f"in {execution_time:.2f} seconds"
        )
        
        return {
            "status": "completed",
            "execution_time": execution_time,
            "cleaned_files": cleaned_files,
            "cleaned_documents": cleaned_documents,
            "reset_tasks": reset_tasks,
            "timestamp": start_time.isoformat()
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error during maintenance cleanup: {e}")
        return {
            "status": "failed",
            "error": f"Database error: {str(e)}",
            "cleaned_files": cleaned_files,
            "cleaned_documents": cleaned_documents,
            "reset_tasks": reset_tasks
        }
        
    except Exception as e:
        logger.error(f"Unexpected error during maintenance cleanup: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "cleaned_files": cleaned_files,
            "cleaned_documents": cleaned_documents,
            "reset_tasks": reset_tasks
        }


@celery_app.task(name="src.rag_service.tasks.maintenance.health_check")
def health_check() -> Dict[str, Any]:
    """
    Perform system health check.
    
    Returns:
        Dictionary containing health status information
    """
    import asyncio
    from ..database import reset_db_state
    
    try:
        # Reset database state before creating new event loop
        # This prevents 'Future attached to a different loop' errors
        reset_db_state()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_health_check_async())
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _health_check_async() -> Dict[str, Any]:
    """
    Async implementation of health check.
    
    Returns:
        Dictionary containing health status
    """
    try:
        async with get_db_session() as db:
            # Check database connectivity
            result = await db.execute(select(1))
            result.scalar()
            
            # Get basic statistics
            files_count = await db.execute(select(File).count())
            total_files = files_count.scalar()
            
            docs_count = await db.execute(select(FileDocument).count())
            total_documents = docs_count.scalar()
            
            # Check for stuck tasks
            stuck_threshold = datetime.now() - timedelta(hours=2)
            stuck_query = select(File).where(
                and_(
                    File.status == ProcessingStatus.PROCESSING.value,
                    File.updated_at < stuck_threshold
                )
            )
            stuck_result = await db.execute(stuck_query)
            stuck_tasks = len(stuck_result.scalars().all())
            
            return {
                "status": "healthy",
                "database": "connected",
                "total_files": total_files,
                "total_documents": total_documents,
                "stuck_tasks": stuck_tasks,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
