"""
Document chunking and text splitting module.

This module provides text chunking capabilities for optimal RAG performance.
It handles document splitting with configurable parameters and strategies
to create semantically meaningful chunks for embedding generation.

Key Components:
- Configurable text splitting with RecursiveCharacterTextSplitter
- Optimized chunk sizes for embedding models
- Overlap management for context preservation
- Token counting and estimation utilities
- Chunk metadata management and tracking

Features:
- Recursive character-based splitting for natural boundaries
- Configurable chunk size and overlap parameters
- Token counting for accurate chunk sizing
- Metadata preservation across chunks
- Performance optimization for large documents
"""

import re
from typing import Any, Dict, List
from uuid import UUID, uuid4

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .document_processing_errors import DocumentProcessingError, ProcessingStep
from .document_processing_types import (
    ChunkingStats,
    DocumentList,
    MetadataDict,
    TextSplitter as TextSplitterProtocol
)
from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)


def chunk_documents(
    documents: DocumentList,
    file_id: str,
    file_uuid: UUID,
    collection_id: UUID,
    project_id: UUID
) -> List[Dict[str, Any]]:
    """
    Split documents into chunks for optimal RAG performance.
    
    This function takes loaded documents and splits them into smaller chunks
    that are optimally sized for embedding generation and retrieval.
    
    Args:
        documents: List of Document objects to be chunked
        file_id: String ID of the file for logging
        file_uuid: UUID of the file being processed
        collection_id: UUID of the collection the file belongs to
        
    Returns:
        List of dictionaries containing chunk data ready for database storage
        
    Raises:
        DocumentProcessingError: If chunking fails
    """
    try:
        if not documents:
            logger.warning(f"No documents to chunk for file {file_id}")
            return []
        
        settings = get_settings()
        
        # Create text splitter with optimized parameters
        text_splitter = _create_text_splitter(settings)
        
        # Split documents into chunks
        chunks = []
        total_chunks = 0
        
        for doc_index, document in enumerate(documents):
            try:
                # Split the document into chunks
                doc_chunks = text_splitter.split_documents([document])
                
                # Process each chunk
                for chunk_index, chunk in enumerate(doc_chunks):
                    chunk_data = _create_chunk_data(
                        chunk=chunk,
                        file_uuid=file_uuid,
                        collection_id=collection_id,
                        project_id=project_id,
                        file_id=file_id,
                        doc_index=doc_index,
                        chunk_index=chunk_index + total_chunks
                    )
                    chunks.append(chunk_data)
                
                total_chunks += len(doc_chunks)
                logger.debug(f"Created {len(doc_chunks)} chunks from document {doc_index} in file {file_id}")
                
            except Exception as e:
                logger.error(f"Failed to chunk document {doc_index} in file {file_id}: {e}")
                raise DocumentProcessingError(
                    f"Failed to chunk document {doc_index}: {str(e)}",
                    file_id,
                    ProcessingStep.CHUNKING_DOCUMENTS,
                    e
                ) from e
        
        logger.info(f"Successfully created {len(chunks)} chunks from {len(documents)} documents for file {file_id}")
        return chunks
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Document chunking failed: {str(e)}",
            file_id,
            ProcessingStep.CHUNKING_DOCUMENTS,
            e
        ) from e


def _create_text_splitter(settings: Any) -> RecursiveCharacterTextSplitter:
    """
    Create a text splitter with optimized parameters.
    
    Args:
        settings: Application settings containing chunking configuration
        
    Returns:
        Configured RecursiveCharacterTextSplitter instance
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=[
            "\n\n",  # Paragraph breaks
            "\n",    # Line breaks
            " ",     # Word breaks
            ".",     # Sentence breaks
            ",",     # Clause breaks
            ""       # Character breaks (fallback)
        ],
        keep_separator=True,
        add_start_index=True
    )


def _create_chunk_data(
    chunk: Document,
    file_uuid: UUID,
    collection_id: UUID,
    project_id: UUID,
    file_id: str,
    doc_index: int,
    chunk_index: int
) -> Dict[str, Any]:
    """
    Create chunk data dictionary for database storage.

    Args:
        chunk: Document chunk to process
        file_uuid: UUID of the source file
        collection_id: UUID of the collection
        project_id: UUID of the project
        file_id: String ID of the file for chunk naming
        doc_index: Index of the source document
        chunk_index: Index of this chunk

    Returns:
        Dictionary containing chunk data ready for database storage
    """
    # Generate unique chunk ID
    chunk_id = f"{file_id}_chunk_{chunk_index}"
    
    # Calculate token count
    token_count = estimate_token_count(chunk.page_content)
    
    # Prepare metadata
    metadata = chunk.metadata.copy() if chunk.metadata else {}
    metadata.update({
        "chunk_index": chunk_index,
        "document_index": doc_index,
        "chunk_id": chunk_id
    })
    
    return {
        "id": uuid4(),
        "file_id": file_uuid,
        "collection_id": collection_id,
        "project_id": project_id,
        "chunk_id": chunk_id,
        "content": chunk.page_content,
        "character_count": len(chunk.page_content),
        "token_count": token_count,
        "chunk_index": chunk_index,
        "document_type": "paragraph",  # Default document type
        "metadata": metadata
    }


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for a given text.
    
    This provides a rough estimation of tokens based on word count and
    character patterns. For more accurate token counting, consider using
    the actual tokenizer from your embedding model.
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0
    
    # Simple estimation: roughly 4 characters per token for English text
    # This is a conservative estimate that works reasonably well for most content
    
    # Count words (more accurate for token estimation)
    words = len(text.split())
    
    # Count special characters and punctuation (often separate tokens)
    special_chars = len(re.findall(r'[^\w\s]', text))
    
    # Estimate tokens: words + some fraction of special characters
    estimated_tokens = words + (special_chars // 2)
    
    # Ensure minimum of 1 token for non-empty text
    return max(1, estimated_tokens)


def get_chunking_stats(chunks: List[Dict[str, Any]]) -> ChunkingStats:
    """
    Calculate statistics for a list of chunks.

    Args:
        chunks: List of chunk data dictionaries

    Returns:
        ChunkingStats object containing chunking statistics
    """
    if not chunks:
        return ChunkingStats(
            total_chunks=0,
            total_characters=0,
            total_tokens=0,
            avg_chunk_size=0,
            avg_tokens_per_chunk=0,
            min_chunk_size=0,
            max_chunk_size=0
        )

    total_characters = sum(chunk["character_count"] for chunk in chunks)
    total_tokens = sum(chunk["token_count"] for chunk in chunks)

    return ChunkingStats(
        total_chunks=len(chunks),
        total_characters=total_characters,
        total_tokens=total_tokens,
        avg_chunk_size=total_characters // len(chunks),
        avg_tokens_per_chunk=total_tokens // len(chunks),
        min_chunk_size=min(chunk["character_count"] for chunk in chunks),
        max_chunk_size=max(chunk["character_count"] for chunk in chunks)
    )


def validate_chunks(chunks: List[Dict[str, Any]], file_id: str) -> bool:
    """
    Validate chunk data before processing.
    
    Args:
        chunks: List of chunk data dictionaries to validate
        file_id: File ID for error reporting
        
    Returns:
        True if all chunks are valid
        
    Raises:
        DocumentProcessingError: If validation fails
    """
    try:
        if not chunks:
            logger.warning(f"No chunks to validate for file {file_id}")
            return True
        
        required_fields = ["id", "file_id", "collection_id", "chunk_id", "content", "token_count"]
        
        for i, chunk in enumerate(chunks):
            # Check required fields
            for field in required_fields:
                if field not in chunk:
                    raise DocumentProcessingError(
                        f"Chunk {i} missing required field: {field}",
                        file_id,
                        ProcessingStep.CHUNKING_DOCUMENTS
                    )
            
            # Validate content
            if not chunk["content"] or not chunk["content"].strip():
                raise DocumentProcessingError(
                    f"Chunk {i} has empty content",
                    file_id,
                    ProcessingStep.CHUNKING_DOCUMENTS
                )
            
            # Validate token count
            if chunk["token_count"] <= 0:
                raise DocumentProcessingError(
                    f"Chunk {i} has invalid token count: {chunk['token_count']}",
                    file_id,
                    ProcessingStep.CHUNKING_DOCUMENTS
                )
        
        logger.debug(f"Successfully validated {len(chunks)} chunks for file {file_id}")
        return True
        
    except Exception as e:
        if isinstance(e, DocumentProcessingError):
            raise
        raise DocumentProcessingError(
            f"Chunk validation failed: {str(e)}",
            file_id,
            ProcessingStep.CHUNKING_DOCUMENTS,
            e
        ) from e
