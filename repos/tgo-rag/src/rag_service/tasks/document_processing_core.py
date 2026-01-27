"""
Document processing core orchestration module.

This module provides the main document processing orchestration logic,
coordinating file loading, chunking, embedding generation, and status management.
It serves as the central coordinator for the entire document processing pipeline.

Key Components:
- Main processing orchestration function
- File status management and progress tracking
- Task coordination between different processing stages
- Performance monitoring and metrics collection
- Error handling and recovery coordination
- Database transaction management

Features:
- Coordinated multi-stage processing pipeline
- Real-time status updates and progress tracking
- Comprehensive error handling with proper rollback
- Performance metrics and timing analysis
- Memory-efficient processing for large files
- Robust transaction management
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from .document_loaders import get_document_loader
from .document_chunking import chunk_documents, get_chunking_stats, validate_chunks
from .document_embedding import generate_embeddings, get_embedding_service_info
from .document_processing_errors import (
    DocumentProcessingError,
    ProcessingStep,
    ProcessingStatus,
    _handle_processing_error,
    log_processing_step,
    log_processing_success
)
from .document_processing_types import (
    DocumentList,
    FileInfo,
    ProcessingResult
)
from ..database import get_db_session
from ..models import File, FileDocument, WebsitePage

logger = logging.getLogger(__name__)


async def _update_website_page_status(
    file_uuid: UUID,
    status: str,
    error_message: Optional[str] = None
) -> None:
    """
    Update WebsitePage status if the file was created from website crawling.

    This function checks if the file has an associated page_id in storage_metadata
    and updates the corresponding WebsitePage status.

    Args:
        file_uuid: UUID of the file
        status: New status for the WebsitePage ('processed' or 'failed')
        error_message: Optional error message if status is 'failed'
    """
    try:
        async with get_db_session() as db:
            # Load file to get storage_metadata
            result = await db.execute(
                select(File).where(File.id == file_uuid)
            )
            file_record = result.scalar_one_or_none()

            if not file_record:
                return

            # Check if this file came from website crawling
            storage_metadata = file_record.storage_metadata or {}
            page_id_str = storage_metadata.get("page_id")

            if not page_id_str:
                return  # Not a website crawl file

            try:
                page_uuid = UUID(page_id_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid page_id in storage_metadata: {page_id_str}")
                return

            # Update WebsitePage status
            page_result = await db.execute(
                select(WebsitePage).where(WebsitePage.id == page_uuid)
            )
            page = page_result.scalar_one_or_none()

            if page:
                page.status = status
                if error_message:
                    page.error_message = error_message
                await db.commit()
                logger.info(f"Updated WebsitePage {page_uuid} status to '{status}'")

    except SQLAlchemyError as e:
        logger.error(f"Failed to update WebsitePage status for file {file_uuid}: {e}")


async def update_website_page_status_by_file_id(
    file_id: str,
    status: str,
    error_message: Optional[str] = None
) -> None:
    """
    Update WebsitePage status using file_id string.

    This is a convenience wrapper for _update_website_page_status that handles
    UUID conversion and is safe to call when the file_id might be invalid.

    Args:
        file_id: String UUID of the file
        status: New status for the WebsitePage ('processed' or 'failed')
        error_message: Optional error message if status is 'failed'
    """
    try:
        file_uuid = UUID(file_id)
        await _update_website_page_status(file_uuid, status, error_message)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid file_id for page status update: {file_id} - {e}")


async def process_file_async(
    file_uuid: UUID,
    collection_id: UUID,
    task_id: Optional[str] = None,
    is_qa_mode: bool = False
) -> ProcessingResult:
    """
    Main asynchronous document processing function.
    
    This function orchestrates the complete document processing pipeline:
    1. Load and validate file information
    2. Extract content using appropriate document loader
    3. Chunk documents for optimal embedding size
    4. Generate embeddings using configured embedding service
    5. Store documents and embeddings in database
    6. Update file status and metrics
    
    Args:
        file_uuid: UUID of the file to process
        collection_id: UUID of the collection the file belongs to
        task_id: Optional Celery task ID for progress tracking
        is_qa_mode: Whether to generate QA pairs for the document
        
    Returns:
        Dictionary containing processing results and metrics
        
    Raises:
        DocumentProcessingError: For any processing failures
    """
    start_time = time.time()
    file_id = str(file_uuid)
    
    try:
        # Update status to processing
        await _update_file_status(file_uuid, ProcessingStatus.PROCESSING)
        log_processing_step(file_id, ProcessingStep.LOADING_FILE, f"Starting document processing (QA Mode: {is_qa_mode})")
        
        # Load file information
        file_info = await _load_file_info(file_uuid, file_id)
        
        # Load and extract document content
        documents = await _load_document_content(file_info, file_id)
        
        # Update status to chunking
        await _update_file_status(file_uuid, ProcessingStatus.CHUNKING_DOCUMENTS)
        
        # Chunk documents
        chunks = await _chunk_documents(documents, file_id, file_uuid, collection_id, file_info.project_id)
        
        # If QA mode is enabled, generate QA pairs and append to chunks
        if is_qa_mode:
            # QA generation proceeds without explicit status update (defaults to previous state)
            qa_chunks = await _generate_qa_pairs(chunks, file_id, file_uuid, collection_id, file_info.project_id)
            if qa_chunks:
                chunks.extend(qa_chunks)
        
        # Store document chunks in database
        await _store_document_chunks(chunks, file_id, file_info.project_id)
        
        # Update status to generating embeddings
        await _update_file_status(file_uuid, ProcessingStatus.GENERATING_EMBEDDINGS)
        
        # Generate embeddings
        await _generate_document_embeddings(chunks, file_id, file_uuid, collection_id)
        
        # Calculate final metrics
        processing_time = time.time() - start_time
        document_count = len(chunks)
        total_tokens = sum(chunk["token_count"] for chunk in chunks)
        
        # Update final status and metrics
        await _update_file_completion(file_uuid, document_count, total_tokens)

        # Update associated WebsitePage status if this file came from crawling
        await _update_website_page_status(file_uuid, "processed")

        # Log success
        log_processing_success(file_id, processing_time, document_count, total_tokens)

        return ProcessingResult(
            status=ProcessingStatus.COMPLETED.value,
            file_id=file_id,
            document_count=document_count,
            total_tokens=total_tokens,
            processing_time=processing_time,
            error=None
        )

    except Exception as e:
        logger.error(f"Async processing failed: {e}")
        return ProcessingResult(
            status=ProcessingStatus.FAILED.value,
            file_id=file_id,
            document_count=0,
            total_tokens=0,
            processing_time=0,
            error=str(e)
        )


async def _generate_qa_pairs(
    chunks: List[Dict[str, Any]], 
    file_id: str, 
    file_uuid: UUID, 
    collection_id: UUID, 
    project_id: UUID
) -> List[Dict[str, Any]]:
    """Generate QA pairs from document chunks."""
    from ..services.llm import get_llm_service_for_project
    from uuid import uuid4

    qa_chunks = []
    llm_service = await get_llm_service_for_project(project_id)
    
    total_chunks = len(chunks)
    logger.info(f"Starting QA generation for file {file_id} with {total_chunks} chunks")
    
    qa_inputs = []
    import asyncio
    
    for i, chunk in enumerate(chunks):
        qa_inputs.append((i, chunk))

    # Process in batches to avoid overwhelming the LLM API (configurable)
    from ..config import get_settings
    settings = get_settings()
    batch_size = settings.qa_generation_batch_size
    for k in range(0, len(qa_inputs), batch_size):
        batch = qa_inputs[k:k+batch_size]
        tasks = []
        for _, chunk in batch:
            tasks.append(llm_service.generate_qa_pairs(chunk["content"]))
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for idx, (original_idx, chunk) in enumerate(batch):
            result = batch_results[idx]
            
            if isinstance(result, Exception):
                logger.error(f"Error generating QA for chunk {chunk['chunk_index']}: {result}")
                continue
                
            qa_pairs = result
            if not qa_pairs:
                continue
                
            # Convert each QA pair to a document chunk
            for j, qa in enumerate(qa_pairs):
                question = qa.get("question", "").strip()
                answer = qa.get("answer", "").strip()
                
                if not question or not answer:
                    continue
                    
                # Format content as Q&A
                content = f"Question: {question}\nAnswer: {answer}"
                
                # Create QA chunk
                qa_chunk_id = f"{file_id}_qa_{chunk['chunk_index']}_{j}"
                
                qa_metadata = chunk["metadata"].copy()
                qa_metadata.update({
                    "is_qa": True,
                    "original_question": question,
                    "original_answer": answer,
                    "source_chunk_id": chunk["chunk_id"]
                })
                
                qa_chunk = {
                    "id": uuid4(),
                    "file_id": file_uuid,
                    "collection_id": collection_id,
                    "project_id": project_id,
                    "chunk_id": qa_chunk_id,
                    "content": content,
                    "character_count": len(content),
                    # Estimate tokens for QA pair
                    "token_count": len(content.split()) + 10, 
                    "chunk_index": chunk["chunk_index"], # Keep same index to appear near original? Or maybe separate.
                    "document_type": "qa_pair",
                    "metadata": qa_metadata
                }
                qa_chunks.append(qa_chunk)
                
            # Log progress every 10 chunks
            if (original_idx + 1) % 10 == 0:
                logger.info(f"QA Generation progress: {original_idx + 1}/{total_chunks} chunks processed")
            
    logger.info(f"QA Generation completed. Generated {len(qa_chunks)} QA pairs from {total_chunks} chunks.")
    return qa_chunks


async def _load_file_info(file_uuid: UUID, file_id: str) -> Any:
    """Load file information from database."""
    try:
        async with get_db_session() as db:
            result = await db.execute(
                select(File).where(File.id == file_uuid)
            )
            file_info = result.scalar_one_or_none()
            
            if not file_info:
                raise DocumentProcessingError(
                    f"File not found: {file_uuid}",
                    file_id,
                    ProcessingStep.LOADING_FILE
                )
            
            log_processing_step(file_id, ProcessingStep.LOADING_FILE, f"File loaded successfully: {file_info.original_filename}")
            return file_info
            
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Error loading file info: {str(e)}",
            file_id,
            ProcessingStep.LOADING_FILE,
            e
        ) from e


async def _load_document_content(file_info: Any, file_id: str) -> List[Any]:
    """Load document content using appropriate loader with PDF OCR fallback."""
    try:
        file_path = file_info.storage_path
        content_type = file_info.content_type

        # Primary: parser-based loader (fast path)
        loader = get_document_loader(file_path, content_type, file_id)
        loop = asyncio.get_event_loop()
        documents = await loop.run_in_executor(None, loader.load)

        def _is_effective(docs: List[Any]) -> bool:
            try:
                return bool(docs) and any(getattr(d, "page_content", "").strip() for d in docs)
            except Exception:
                return bool(docs)

        if _is_effective(documents):
            log_processing_step(
                file_id,
                ProcessingStep.EXTRACTING_CONTENT,
                f"Extracted content from {len(documents)} documents (primary parser)"
            )
            return documents

        # Fallback check for PDFs with no extractable text
        if content_type == "application/pdf" and not _is_effective(documents):
            raise DocumentProcessingError(
                "PDF appears to be scanned/image-based. Text extraction not supported for this PDF type. "
                "Please use a text-based PDF or enable OCR service.",
                file_id,
                ProcessingStep.EXTRACTING_CONTENT,
            )

        # If still no content, raise explicit error
        raise DocumentProcessingError(
            "No content extracted from file",
            file_id,
            ProcessingStep.EXTRACTING_CONTENT,
        )

    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Error loading document content: {str(e)}",
            file_id,
            ProcessingStep.EXTRACTING_CONTENT,
            e
        ) from e


async def _chunk_documents(documents: List[Any], file_id: str, file_uuid: UUID, collection_id: UUID, project_id: UUID) -> List[Dict[str, Any]]:
    """Chunk documents into optimal sizes."""
    try:
        # Chunk documents
        chunks = chunk_documents(documents, file_id, file_uuid, collection_id, project_id)
        
        # Validate chunks
        validate_chunks(chunks, file_id)
        
        # Log chunking statistics
        stats = get_chunking_stats(chunks)
        log_processing_step(
            file_id,
            ProcessingStep.CHUNKING_DOCUMENTS,
            f"Created {stats.total_chunks} chunks with {stats.total_tokens} total tokens"
        )
        
        return chunks
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Error chunking documents: {str(e)}",
            file_id,
            ProcessingStep.CHUNKING_DOCUMENTS,
            e
        ) from e


async def _store_document_chunks(chunks: List[Dict[str, Any]], file_id: str, project_id: UUID) -> None:
    """Store document chunks in database."""
    try:
        async with get_db_session() as db:
            # Create FileDocument instances
            file_documents = []
            for chunk in chunks:
                file_doc = FileDocument(
                    id=chunk["id"],
                    project_id=project_id,  # Required field
                    file_id=chunk["file_id"],
                    collection_id=chunk["collection_id"],
                    content=chunk["content"],
                    content_length=chunk["character_count"],  # character_count maps to content_length
                    token_count=chunk["token_count"],
                    chunk_index=chunk["chunk_index"],
                    content_type=chunk.get("document_type", "paragraph"),  # document_type maps to content_type
                    tags=chunk.get("metadata", {})  # metadata maps to tags
                )
                file_documents.append(file_doc)
            
            # Add all documents to session
            db.add_all(file_documents)
            await db.commit()
            
            log_processing_step(
                file_id,
                ProcessingStep.STORING_DOCUMENTS,
                f"Stored {len(file_documents)} document chunks"
            )
            
    except Exception as e:
        raise DocumentProcessingError(
            f"Error storing document chunks: {str(e)}",
            file_id,
            ProcessingStep.STORING_DOCUMENTS,
            e
        ) from e


async def _generate_document_embeddings(chunks: List[Dict[str, Any]], file_id: str, file_uuid: UUID, collection_id: UUID) -> None:
    """Generate embeddings for document chunks."""
    try:
        await generate_embeddings(chunks, file_id, file_uuid, collection_id)
        
        log_processing_step(
            file_id,
            ProcessingStep.GENERATING_EMBEDDINGS,
            f"Generated embeddings for {len(chunks)} chunks"
        )
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Error generating embeddings: {str(e)}",
            file_id,
            ProcessingStep.GENERATING_EMBEDDINGS,
            e
        ) from e


async def _update_file_status(file_uuid: UUID, status: ProcessingStatus) -> None:
    """Update file processing status."""
    try:
        async with get_db_session() as db:
            await db.execute(
                update(File)
                .where(File.id == file_uuid)
                .values(status=status.value)
            )
            await db.commit()
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to update file status to {status.value}: {e}")


async def _update_file_completion(file_uuid: UUID, document_count: int, total_tokens: int) -> None:
    """Update file with completion metrics."""
    try:
        async with get_db_session() as db:
            await db.execute(
                update(File)
                .where(File.id == file_uuid)
                .values(
                    status=ProcessingStatus.COMPLETED.value,
                    document_count=document_count,
                    total_tokens=total_tokens
                )
            )
            await db.commit()
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to update file completion metrics: {e}")
