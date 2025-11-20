"""
Document embedding generation module.

This module provides embedding generation capabilities for document chunks
using various embedding models and vector store integration for semantic search.

Key Components:
- Embedding generation using multiple providers (OpenAI, Qwen3)
- Vector store integration for embedding storage and retrieval
- Batch processing for efficient embedding generation
- Error handling and retry mechanisms for embedding failures
- Performance monitoring and optimization

Features:
- Multi-provider embedding support (OpenAI, Qwen3-Embedding)
- Efficient batch processing for large document sets
- Vector store integration with pgvector
- Comprehensive error handling and recovery
- Performance metrics and monitoring
- Memory-efficient processing for large files
"""

import asyncio
from typing import Any, Dict, List
from uuid import UUID

from .document_processing_errors import DocumentProcessingError, ProcessingStep
from .document_processing_types import (
    ChunkDataList,
    EmbeddingList,
    EmbeddingServiceInfo,
    EmbeddingStats,
    EmbeddingVector,
    MetadataDict,
    VectorStoreService as VectorStoreServiceProtocol
)
from ..logging_config import get_logger
from ..services.embedding import get_embedding_service, get_embedding_service_for_project
from ..services.vector_store import get_vector_store_service

logger = get_logger(__name__)


async def generate_embeddings(
    chunks: List[Dict[str, Any]],
    file_id: str,
    file_uuid: UUID,
    collection_id: UUID
) -> None:
    """
    Generate embeddings for document chunks and store them in the vector store.
    
    This function processes document chunks to generate vector embeddings
    using the configured embedding service and stores them in the vector store
    for semantic search capabilities.
    
    Args:
        chunks: List of chunk data dictionaries
        file_id: String ID of the file for logging
        file_uuid: UUID of the file being processed
        collection_id: UUID of the collection
        
    Raises:
        DocumentProcessingError: If embedding generation fails
    """
    try:
        if not chunks:
            logger.warning(f"No chunks to generate embeddings for file {file_id}")
            return
        
        # Resolve project and services
        vector_store_service = get_vector_store_service()
        project_id = chunks[0].get("project_id")
        embedding_service = await get_embedding_service_for_project(project_id)

        # Add embeddings to vector store (project-scoped)
        await _add_embeddings_to_vector_store(
            chunks=chunks,
            file_id=file_id,
            collection_id=collection_id,
            vector_store_service=vector_store_service,
            embedding_service=embedding_service,
            project_id=project_id,
        )

        logger.info(f"Successfully stored embeddings for file {file_id}")
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Failed to generate embeddings: {str(e)}",
            file_id,
            ProcessingStep.GENERATING_EMBEDDINGS,
            e
        ) from e


async def _add_embeddings_to_vector_store(
    chunks: List[Dict[str, Any]],
    file_id: str,
    collection_id: UUID,
    vector_store_service: Any,  # Using Any for now since the actual service doesn't match the protocol
    embedding_service: Any,
    project_id: UUID,
) -> None:
    """
    Add embeddings to the vector store with proper error handling.

    Args:
        chunks: List of chunk data dictionaries
        file_id: String ID of the file for logging
        collection_id: UUID of the collection
        vector_store_service: Vector store service instance

    Raises:
        DocumentProcessingError: If vector store operations fail
    """
    try:
        # Prepare documents for vector store in the format expected by add_documents_batch
        # The method expects List[Tuple[UUID, str, Optional[Dict[str, Any]]]]
        documents = []

        for chunk in chunks:
            # Get document ID from chunk
            document_id = chunk["id"]  # This should be the UUID
            content = chunk["content"]

            # Prepare metadata with proper UUID types for database fields
            metadata = {
                "file_id": chunk["file_id"],  # Keep as UUID
                "project_id": chunk["project_id"],  # Keep as UUID
                "collection_id": collection_id,  # Keep as UUID
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk["chunk_index"],
                "character_count": chunk["character_count"],
                "token_count": chunk["token_count"],
                "document_type": chunk.get("document_type", "paragraph")
            }

            # Add any additional metadata from the chunk
            if "metadata" in chunk and isinstance(chunk["metadata"], dict):
                metadata.update(chunk["metadata"])

            # Create tuple in the format expected by the vector store service
            documents.append((document_id, content, metadata))

        # Add documents to vector store in batch (project-scoped embedding client)
        vector_ids = await vector_store_service.add_documents_batch_for_project(
            documents=documents,
            project_key=str(project_id),
            embedding_client=embedding_service.embeddings_client,
        )

        # If any vector IDs are empty placeholders, treat as a batch failure
        failed_count = sum(1 for vid in vector_ids if not vid)
        if failed_count > 0 or len(vector_ids) != len(documents):
            raise DocumentProcessingError(
                f"Vector store batch processing failed: {failed_count} of {len(documents)} documents",
                file_id,
                ProcessingStep.GENERATING_EMBEDDINGS,
            )

        logger.debug(f"Added {len(vector_ids)} documents to vector store for file {file_id}")

    except Exception as e:
        logger.error(f"Failed to add document embeddings batch: {str(e)}")
        raise DocumentProcessingError(
            f"Failed to add embeddings to vector store: {str(e)}",
            file_id,
            ProcessingStep.GENERATING_EMBEDDINGS,
            e
        ) from e


async def validate_embeddings(
    embeddings: List[List[float]],
    expected_dimensions: int,
    file_id: str
) -> bool:
    """
    Validate embedding vectors for consistency and correctness.
    
    Args:
        embeddings: List of embedding vectors to validate
        expected_dimensions: Expected number of dimensions per embedding
        file_id: File ID for error reporting
        
    Returns:
        True if all embeddings are valid
        
    Raises:
        DocumentProcessingError: If validation fails
    """
    try:
        if not embeddings:
            logger.warning(f"No embeddings to validate for file {file_id}")
            return True
        
        for i, embedding in enumerate(embeddings):
            # Check if embedding is a list/array of numbers
            if not isinstance(embedding, (list, tuple)):
                raise DocumentProcessingError(
                    f"Embedding {i} is not a list/array: {type(embedding)}",
                    file_id,
                    ProcessingStep.GENERATING_EMBEDDINGS
                )
            
            # Check dimensions
            if len(embedding) != expected_dimensions:
                raise DocumentProcessingError(
                    f"Embedding {i} has wrong dimensions: expected {expected_dimensions}, got {len(embedding)}",
                    file_id,
                    ProcessingStep.GENERATING_EMBEDDINGS
                )
            
            # Check if all values are numbers
            for j, value in enumerate(embedding):
                if not isinstance(value, (int, float)):
                    raise DocumentProcessingError(
                        f"Embedding {i}, dimension {j} is not a number: {type(value)}",
                        file_id,
                        ProcessingStep.GENERATING_EMBEDDINGS
                    )
        
        logger.debug(f"Successfully validated {len(embeddings)} embeddings for file {file_id}")
        return True
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Embedding validation failed: {str(e)}",
            file_id,
            ProcessingStep.GENERATING_EMBEDDINGS,
            e
        ) from e


def get_embedding_stats(embeddings: EmbeddingList) -> EmbeddingStats:
    """
    Calculate statistics for embedding vectors.

    Args:
        embeddings: List of embedding vectors

    Returns:
        EmbeddingStats object containing embedding statistics
    """
    if not embeddings:
        return EmbeddingStats(
            total_embeddings=0,
            dimensions=0,
            total_values=0
        )

    dimensions = len(embeddings[0]) if embeddings else 0
    total_values = len(embeddings) * dimensions

    # Calculate basic statistics
    all_values = [value for embedding in embeddings for value in embedding]

    if all_values:
        return EmbeddingStats(
            total_embeddings=len(embeddings),
            dimensions=dimensions,
            total_values=total_values,
            min_value=min(all_values),
            max_value=max(all_values),
            avg_value=sum(all_values) / len(all_values)
        )
    else:
        return EmbeddingStats(
            total_embeddings=len(embeddings),
            dimensions=dimensions,
            total_values=total_values
        )


async def get_embedding_service_info() -> EmbeddingServiceInfo:
    """
    Get information about the current embedding service configuration.

    Returns:
        EmbeddingServiceInfo object containing embedding service information
    """
    try:
        embedding_service = get_embedding_service()

        return EmbeddingServiceInfo(
            provider=embedding_service.get_embedding_provider(),
            model=embedding_service.get_embedding_model(),
            dimensions=embedding_service.get_embedding_dimensions()
        )

    except Exception as e:
        logger.error(f"Failed to get embedding service info: {e}")
        return EmbeddingServiceInfo(
            provider="unknown",
            model="unknown",
            dimensions=0,
            error=str(e)
        )


async def test_embedding_generation(test_text: str = "Test embedding generation") -> Dict[str, Any]:
    """
    Test embedding generation with a sample text.
    
    Args:
        test_text: Text to use for testing
        
    Returns:
        Dictionary containing test results
    """
    try:
        embedding_service = get_embedding_service()
        
        # Generate test embedding
        start_time = asyncio.get_event_loop().time()
        embedding = await embedding_service.generate_embedding(test_text)
        end_time = asyncio.get_event_loop().time()
        
        return {
            "success": True,
            "provider": embedding_service.get_embedding_provider(),
            "model": embedding_service.get_embedding_model(),
            "dimensions": len(embedding),
            "generation_time": end_time - start_time,
            "test_text_length": len(test_text)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "test_text_length": len(test_text)
        }
