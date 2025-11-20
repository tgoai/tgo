"""
Document processing error handling module.

This module provides error handling utilities for document processing tasks including:
- Custom exception classes for different processing stages
- Processing step enumeration for error context
- Error handling utilities and recovery mechanisms
- Structured error reporting and logging

Key Components:
- ProcessingStep: Enumeration of processing stages for error context
- DocumentProcessingError: Custom exception with detailed error information
- Error handling utilities for graceful failure recovery
"""

from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..database import get_db_session
from ..logging_config import get_logger
from ..models import File

logger = get_logger(__name__)


class ProcessingStep(Enum):
    """Enumeration of document processing steps for error tracking."""
    LOADING_FILE = "loading_file"
    EXTRACTING_CONTENT = "extracting_content"
    CHUNKING_DOCUMENTS = "chunking_documents"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    STORING_DOCUMENTS = "storing_documents"
    UPDATING_STATUS = "updating_status"


class ProcessingStatus(Enum):
    """Document processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    CHUNKING_DOCUMENTS = "chunking_documents"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class DocumentProcessingError(Exception):
    """
    Custom exception for document processing errors.
    
    Provides detailed error information including:
    - File ID for error tracking
    - Processing step where error occurred
    - Original exception for debugging
    - Structured error context
    """
    
    def __init__(
        self,
        message: str,
        file_id: str,
        step: ProcessingStep,
        original_exception: Optional[Exception] = None
    ):
        """
        Initialize document processing error.
        
        Args:
            message: Human-readable error message
            file_id: ID of the file being processed
            step: Processing step where error occurred
            original_exception: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.file_id = file_id
        self.step = step
        self.original_exception = original_exception
    
    def __str__(self) -> str:
        """Return formatted error message."""
        return f"DocumentProcessingError in {self.step.value} for file {self.file_id}: {self.message}"
    
    def to_dict(self) -> dict:
        """Convert error to dictionary for structured logging."""
        return {
            "error_type": "DocumentProcessingError",
            "message": self.message,
            "file_id": self.file_id,
            "step": self.step.value,
            "original_exception": str(self.original_exception) if self.original_exception else None
        }


async def _handle_processing_error(
    file_uuid: UUID,
    file_id: str,
    processing_error: Exception,
    step: ProcessingStep
) -> None:
    """
    Handle processing errors by updating file status and logging.
    
    Args:
        file_uuid: UUID of the file being processed
        file_id: String ID of the file for logging
        processing_error: Exception that occurred during processing
        step: Processing step where error occurred
    """
    try:
        # Log the error with context
        error_context = {
            "file_id": file_id,
            "file_uuid": str(file_uuid),
            "step": step.value,
            "error_type": type(processing_error).__name__,
            "error_message": str(processing_error)
        }
        
        logger.error(f"Document processing failed for file {file_id}: {processing_error}", extra=error_context)
        
        # Update file status to failed
        async with get_db_session() as db:
            try:
                # Get the file record
                result = await db.execute(
                    select(File).where(File.id == file_uuid)
                )
                file_record = result.scalar_one_or_none()
                
                if file_record:
                    file_record.status = ProcessingStatus.FAILED.value
                    file_record.error_message = str(processing_error)
                    await db.commit()
                    logger.info(f"Updated file status to failed for file {file_id}")
                else:
                    logger.warning(f"File record not found for UUID {file_uuid}")
                    
            except SQLAlchemyError as db_error:
                await db.rollback()
                logger.error(f"Failed to update file status for {file_id}: {db_error}")
                
    except Exception as e:
        # Log the error handling failure, but don't raise to avoid masking original error
        logger.error(f"Error handling failed for file {file_id}: {e}")


def create_processing_error(
    message: str,
    file_id: str,
    step: ProcessingStep,
    original_exception: Optional[Exception] = None
) -> DocumentProcessingError:
    """
    Create a DocumentProcessingError with proper context.
    
    Args:
        message: Error message
        file_id: File ID for context
        step: Processing step where error occurred
        original_exception: Original exception if available
        
    Returns:
        DocumentProcessingError instance
    """
    return DocumentProcessingError(
        message=message,
        file_id=file_id,
        step=step,
        original_exception=original_exception
    )


def log_processing_step(file_id: str, step: ProcessingStep, message: str) -> None:
    """
    Log a processing step with structured context.
    
    Args:
        file_id: File ID for context
        step: Current processing step
        message: Log message
    """
    logger.info(
        f"Processing step {step.value} for file {file_id}: {message}",
        extra={
            "file_id": file_id,
            "step": step.value,
            "step_message": message
        }
    )


def log_processing_success(file_id: str, processing_time: float, document_count: int, total_tokens: int) -> None:
    """
    Log successful processing completion with metrics.
    
    Args:
        file_id: File ID for context
        processing_time: Total processing time in seconds
        document_count: Number of documents created
        total_tokens: Total tokens processed
    """
    logger.info(
        f"Document processing completed successfully for file {file_id}",
        extra={
            "file_id": file_id,
            "processing_time": processing_time,
            "document_count": document_count,
            "total_tokens": total_tokens,
            "status": "completed"
        }
    )
