"""Periodic and on-demand task to process waiting queue entries."""

from __future__ import annotations

import asyncio
from typing import Optional, Set
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models import (
    VisitorWaitingQueue,
    WaitingStatus,
    AssignmentSource,
)
from app.services.transfer_service import transfer_to_human

logger = get_logger("tasks.process_waiting_queue")

# Global state
_task: Optional[asyncio.Task] = None
_processing_lock = asyncio.Lock()
_processing_ids: Set[UUID] = set()  # Track currently processing entry IDs
_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the semaphore for concurrent processing control."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.QUEUE_PROCESS_MAX_WORKERS)
    return _semaphore


async def _process_single_entry_internal(
    db: Session,
    entry: VisitorWaitingQueue,
) -> bool:
    """
    Internal method to process a single queue entry.
    
    Args:
        db: Database session
        entry: VisitorWaitingQueue entry to process
        
    Returns:
        True if processed successfully (assigned or appropriately handled), False otherwise
    """
    try:
        # Record this attempt
        entry.record_attempt()
        db.flush()
        
        # Call transfer_to_human service to try assigning a staff
        result = await transfer_to_human(
            db=db,
            visitor_id=entry.visitor_id,
            project_id=entry.project_id,
            source=AssignmentSource.RULE,
            visitor_message=entry.visitor_message,
            session_id=entry.session_id,
            notes=f"From waiting queue (entry_id={entry.id}, source={entry.source})",
        )

        if result.success and result.assigned_staff_id:
            # Successfully assigned - mark entry as assigned
            entry.assign_to_staff(result.assigned_staff_id)
            db.commit()
            
            logger.info(
                f"Queue entry {entry.id} assigned to staff {result.assigned_staff_id}",
                extra={
                    "entry_id": str(entry.id),
                    "visitor_id": str(entry.visitor_id),
                    "staff_id": str(result.assigned_staff_id),
                    "wait_duration_seconds": entry.wait_duration_seconds,
                },
            )
            return True
            
        elif result.success and not result.assigned_staff_id:
            # No staff available - entry stays in queue
            # Check if we've exceeded max retries
            if entry.retry_count >= settings.QUEUE_PROCESS_MAX_RETRIES:
                entry.expire()
                db.commit()
                logger.warning(
                    f"Queue entry {entry.id} expired after {entry.retry_count} retries",
                    extra={
                        "entry_id": str(entry.id),
                        "visitor_id": str(entry.visitor_id),
                        "retry_count": entry.retry_count,
                    },
                )
            else:
                # Keep waiting, just update the attempt tracking
                db.commit()
                logger.debug(
                    f"Queue entry {entry.id} still waiting (attempt {entry.retry_count})",
                    extra={
                        "entry_id": str(entry.id),
                        "visitor_id": str(entry.visitor_id),
                        "retry_count": entry.retry_count,
                    },
                )
            return True
            
        else:
            # Transfer failed
            logger.warning(
                f"Failed to process queue entry {entry.id}: {result.message}",
                extra={
                    "entry_id": str(entry.id),
                    "visitor_id": str(entry.visitor_id),
                    "error": result.message,
                },
            )
            
            # Check if we've exceeded max retries
            if entry.retry_count >= settings.QUEUE_PROCESS_MAX_RETRIES:
                entry.expire()
                db.commit()
                logger.warning(
                    f"Queue entry {entry.id} expired after {entry.retry_count} failed attempts",
                    extra={
                        "entry_id": str(entry.id),
                        "retry_count": entry.retry_count,
                    },
                )
            else:
                db.commit()
            return False

    except Exception as e:
        logger.exception(
            f"Exception processing queue entry {entry.id}",
            extra={"entry_id": str(entry.id), "error": str(e)},
        )
        try:
            db.rollback()
        except Exception:
            pass
        return False


async def process_queue_entry(entry_id: UUID) -> bool:
    """
    Process a single queue entry by ID.
    
    This method is safe to call from anywhere and handles locking
    to prevent duplicate processing with the periodic task.
    
    Args:
        entry_id: UUID of the VisitorWaitingQueue entry to process
        
    Returns:
        True if processed successfully, False otherwise
    """
    # Check if already being processed
    async with _processing_lock:
        if entry_id in _processing_ids:
            logger.debug(f"Queue entry {entry_id} is already being processed")
            return False
        _processing_ids.add(entry_id)
    
    # Acquire semaphore for concurrency control
    semaphore = _get_semaphore()
    
    try:
        async with semaphore:
            db = SessionLocal()
            try:
                # Re-fetch the entry to ensure we have the latest state
                entry = (
                    db.query(VisitorWaitingQueue)
                    .filter(
                        VisitorWaitingQueue.id == entry_id,
                        VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
                    )
                    .first()
                )
                
                if not entry:
                    logger.debug(f"Queue entry {entry_id} not found or not waiting")
                    return False
                
                return await _process_single_entry_internal(db, entry)
                
            finally:
                db.close()
    finally:
        # Remove from processing set
        async with _processing_lock:
            _processing_ids.discard(entry_id)


async def trigger_process_entry(entry_id: UUID) -> None:
    """
    Trigger processing of a queue entry in the background.
    
    This is a fire-and-forget method that schedules processing
    without blocking the caller.
    
    Args:
        entry_id: UUID of the VisitorWaitingQueue entry to process
    """
    asyncio.create_task(process_queue_entry(entry_id))


async def _process_waiting_queue_batch() -> None:
    """Scan DB for waiting queue entries and process them in parallel."""
    db = SessionLocal()
    try:
        # Query waiting entries that need processing
        # Only select entries that haven't been attempted recently (respect retry delay)
        from datetime import datetime, timedelta
        retry_delay = timedelta(seconds=settings.QUEUE_PROCESS_RETRY_DELAY_SECONDS)
        cutoff_time = datetime.utcnow() - retry_delay
        
        entries = (
            db.query(VisitorWaitingQueue)
            .filter(
                VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
                # Only process entries that haven't been attempted recently
                (
                    (VisitorWaitingQueue.last_attempt_at.is_(None)) |
                    (VisitorWaitingQueue.last_attempt_at < cutoff_time)
                ),
            )
            .order_by(
                VisitorWaitingQueue.priority.desc(),  # Higher priority first
                VisitorWaitingQueue.position.asc(),   # Lower position first
            )
            .limit(settings.QUEUE_PROCESS_BATCH_SIZE)
            .all()
        )

        if not entries:
            logger.debug("Queue processor: no waiting entries to process")
            return

        # Filter out entries that are already being processed
        async with _processing_lock:
            entries_to_process = [
                e for e in entries if e.id not in _processing_ids
            ]
            # Mark them as being processed
            for e in entries_to_process:
                _processing_ids.add(e.id)

        if not entries_to_process:
            logger.debug("Queue processor: all entries are already being processed")
            return

        logger.info(
            f"Queue processor: processing {len(entries_to_process)} entries",
            extra={"count": len(entries_to_process)},
        )

        # Process entries in parallel with semaphore control
        semaphore = _get_semaphore()
        
        async def process_with_semaphore(entry: VisitorWaitingQueue) -> tuple[UUID, bool]:
            """Process a single entry with semaphore control."""
            async with semaphore:
                # Create new DB session for this entry
                entry_db = SessionLocal()
                try:
                    # Re-fetch to get latest state
                    fresh_entry = (
                        entry_db.query(VisitorWaitingQueue)
                        .filter(
                            VisitorWaitingQueue.id == entry.id,
                            VisitorWaitingQueue.status == WaitingStatus.WAITING.value,
                        )
                        .first()
                    )
                    
                    if not fresh_entry:
                        return entry.id, False
                    
                    result = await _process_single_entry_internal(entry_db, fresh_entry)
                    return entry.id, result
                except Exception as e:
                    logger.exception(
                        f"Exception in parallel processing for entry {entry.id}",
                        extra={"entry_id": str(entry.id), "error": str(e)},
                    )
                    return entry.id, False
                finally:
                    entry_db.close()
        
        # Run all tasks in parallel
        tasks = [process_with_semaphore(e) for e in entries_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        processed = 0
        failed = 0
        for result in results:
            if isinstance(result, Exception):
                failed += 1
            elif isinstance(result, tuple) and result[1]:
                processed += 1
            else:
                failed += 1
        
        # Remove all from processing set
        async with _processing_lock:
            for e in entries_to_process:
                _processing_ids.discard(e.id)

        logger.info(
            f"Queue processor: batch complete",
            extra={
                "total": len(entries_to_process),
                "processed": processed,
                "failed": failed,
            },
        )

    except Exception as e:
        logger.exception(
            "Queue processor: batch exception",
            extra={"error": str(e)},
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


async def _loop() -> None:
    """Main processing loop."""
    interval_sec = max(1, settings.QUEUE_PROCESS_INTERVAL_SECONDS)
    while True:
        try:
            await _process_waiting_queue_batch()
        except Exception as e:
            logger.exception(f"Queue processor loop exception: {e}")
        await asyncio.sleep(interval_sec)


def start_queue_processor() -> None:
    """Start periodic background task if enabled."""
    global _task
    if not settings.QUEUE_PROCESS_ENABLED:
        logger.info("Queue processor disabled by config")
        return
    if _task and not _task.done():
        return
    try:
        _task = asyncio.create_task(_loop())
        logger.info(
            "Queue processor task started",
            extra={
                "interval_seconds": settings.QUEUE_PROCESS_INTERVAL_SECONDS,
                "batch_size": settings.QUEUE_PROCESS_BATCH_SIZE,
                "max_workers": settings.QUEUE_PROCESS_MAX_WORKERS,
            },
        )
    except Exception as e:
        logger.warning(
            "Failed to start queue processor task",
            extra={"error": str(e)},
        )


async def stop_queue_processor() -> None:
    """Stop the periodic background task."""
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        _task = None
        logger.info("Queue processor task stopped")
