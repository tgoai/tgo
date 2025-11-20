"""
Document processing tasks for file upload and content extraction.

This module provides the main Celery task interface for document processing,
orchestrating the complete document processing pipeline through modular components.

The processing pipeline includes:
- File content extraction from various formats (PDF, Word, Text, Markdown, HTML)
- Document chunking for optimal RAG performance
- Vector embedding generation for semantic search
- Database persistence with proper session management
- Comprehensive error handling and recovery
- Performance monitoring and logging

Architecture:
- Modular design with single responsibility principle
- Unified parser-based document loading
- Configurable chunking and embedding strategies
- Multi-provider embedding support (OpenAI, Qwen3)
- Robust error handling with detailed context
- Real-time progress tracking and status updates

This module serves as the main entry point for Celery tasks while delegating
specific functionality to specialized modules for better maintainability.
"""

from typing import Any, Dict
from uuid import UUID

from .celery_app import celery_app
from .document_processing_core import process_file_async
from .document_processing_errors import ProcessingStatus
from ..logging_config import get_logger

# Configure logger with structured formatting
logger = get_logger(__name__)


@celery_app.task(bind=True, name="process_file_task")
def process_file_task(self, file_id: str, collection_id: str) -> Dict[str, Any]:
    """
    Celery task for processing uploaded files.
    
    This task orchestrates the complete document processing pipeline:
    1. Load and validate file information
    2. Extract content using appropriate document loader
    3. Chunk documents for optimal embedding size
    4. Generate embeddings using configured embedding service
    5. Store documents and embeddings in database
    6. Update file status and metrics
    
    Args:
        file_id: UUID string of the file to process
        collection_id: UUID string of the collection the file belongs to
        
    Returns:
        Dictionary containing processing results and metrics
    """
    import asyncio
    from uuid import UUID
    
    try:
        # Convert string IDs to UUIDs
        file_uuid = UUID(file_id)
        collection_uuid = UUID(collection_id)
        
        # Run the async processing function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                process_file_async(file_uuid, collection_uuid, self.request.id)
            )
            # Convert ProcessingResult to dictionary for JSON serialization
            return {
                "status": result.status,
                "file_id": result.file_id,
                "document_count": result.document_count,
                "total_tokens": result.total_tokens,
                "processing_time": result.processing_time,
                "error": result.error
            }
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Task execution failed for file {file_id}: {e}")
        return {
            "status": ProcessingStatus.FAILED.value,
            "file_id": file_id,
            "document_count": 0,
            "total_tokens": 0,
            "processing_time": 0,
            "error": str(e)
        }
