"""
Search service implementing hybrid search with vector similarity and keyword matching.
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db_session
from ..logging_config import get_logger
from ..models import FileDocument
from ..schemas.search import SearchMetadata, SearchResult, SearchResponse
from .vector_store import get_vector_store_service
from .embedding import get_embedding_service_for_project

logger = get_logger(__name__)


class SearchService:
    """Service for performing hybrid search operations."""
    
    def __init__(self):
        """Initialize the search service."""
        self.settings = get_settings()
        self.vector_store_service = get_vector_store_service()
    
    async def semantic_search(
        self,
        query: str,
        project_id: UUID,
        collection_id: Optional[UUID] = None,
        limit: int = 20,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> SearchResponse:
        """
        Perform semantic search using vector similarity.

        Args:
            query: Search query text
            project_id: Project ID for multi-tenant isolation
            collection_id: Optional collection to search within
            limit: Maximum number of results
            min_score: Minimum similarity score threshold
            filters: Additional filters to apply

        Returns:
            SearchResponse with results and metadata
        """
        start_time = time.time()

        try:
            # Build metadata filters for vector store with project isolation
            vector_filters = {"project_id": str(project_id)}
            if collection_id:
                vector_filters["collection_id"] = str(collection_id)
            
            if filters:
                # Add additional filters
                if "content_type" in filters:
                    vector_filters["content_type"] = filters["content_type"]
                if "language" in filters:
                    vector_filters["language"] = filters["language"]
            
            # Resolve project-scoped embedding service and perform per-project similarity search
            embedding_service = await get_embedding_service_for_project(project_id)
            vector_results = await self.vector_store_service.similarity_search_for_project(
                query=query,
                project_key=str(project_id),
                embeddings_client=embedding_service.embeddings_client,
                k=limit,
                filter_dict=vector_filters if vector_filters else None,
                score_threshold=min_score,
            )

            # Convert vector results to search results
            search_results = []
            for doc, score in vector_results:
                document_id = doc.id
                if document_id:
                    # Get full document info from database with project filtering
                    document_info = await self._get_document_info(UUID(document_id), project_id)
                    if document_info:
                        search_result = SearchResult(
                            document_id=UUID(document_id),
                            file_id=document_info["file_id"],
                            collection_id=document_info.get("collection_id"),
                            relevance_score=score,
                            content_preview=self._create_content_preview(doc.page_content),
                            document_title=document_info.get("document_title"),
                            content_type=document_info.get("content_type", "paragraph"),
                            chunk_index=document_info.get("chunk_index"),
                            page_number=document_info.get("page_number"),
                            section_title=document_info.get("section_title"),
                            tags=document_info.get("tags"),
                            created_at=document_info["created_at"],
                        )
                        search_results.append(search_result)
            
            # Create search metadata
            search_time_ms = int((time.time() - start_time) * 1000)
            search_metadata = SearchMetadata(
                query=query,
                total_results=len(search_results),
                returned_results=len(search_results),
                search_time_ms=search_time_ms,
                filters_applied=filters,
                search_type="semantic"
            )
            
            return SearchResponse(
                results=search_results,
                search_metadata=search_metadata
            )
            
        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            raise
    
    async def keyword_search(
        self,
        query: str,
        project_id: UUID,
        collection_id: Optional[UUID] = None,
        limit: int = 20,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> SearchResponse:
        """
        Perform keyword search using PostgreSQL full-text search.

        Args:
            query: Search query text
            project_id: Project ID for multi-tenant isolation
            collection_id: Optional collection to search within
            limit: Maximum number of results
            min_score: Minimum relevance score threshold
            filters: Additional filters to apply

        Returns:
            SearchResponse with results and metadata
        """
        start_time = time.time()

        try:
            async with get_db_session() as db:
                # Build base query with project filtering
                base_query = select(
                    FileDocument,
                    func.ts_rank_cd(
                        func.to_tsvector('english', FileDocument.content),
                        func.plainto_tsquery('english', query)
                    ).label('rank')
                ).where(
                    and_(
                        func.to_tsvector('english', FileDocument.content).op('@@')(
                            func.plainto_tsquery('english', query)
                        ),
                        FileDocument.content.isnot(None),
                        FileDocument.project_id == project_id
                    )
                )

                # Apply collection filter
                if collection_id:
                    base_query = base_query.where(FileDocument.collection_id == collection_id)
                
                # Apply additional filters
                if filters:
                    if "content_type" in filters:
                        if isinstance(filters["content_type"], list):
                            base_query = base_query.where(
                                FileDocument.content_type.in_(filters["content_type"])
                            )
                        else:
                            base_query = base_query.where(
                                FileDocument.content_type == filters["content_type"]
                            )
                    
                    if "language" in filters:
                        base_query = base_query.where(FileDocument.language == filters["language"])
                    
                    if "min_confidence" in filters:
                        base_query = base_query.where(
                            FileDocument.confidence_score >= filters["min_confidence"]
                        )
                
                # Apply score threshold and ordering
                if min_score > 0:
                    base_query = base_query.having(text(f"ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', :query)) >= {min_score}"))
                
                base_query = base_query.order_by(text("rank DESC")).limit(limit)
                
                # Execute query
                result = await db.execute(base_query, {"query": query})
                rows = result.all()
                
                # Convert to search results
                search_results = []
                for document, rank in rows:
                    search_result = SearchResult(
                        document_id=document.id,
                        file_id=document.file_id,
                        collection_id=document.collection_id,
                        relevance_score=float(rank),
                        content_preview=self._create_content_preview(document.content),
                        document_title=document.document_title,
                        content_type=document.content_type,
                        chunk_index=document.chunk_index,
                        page_number=document.page_number,
                        section_title=document.section_title,
                        tags=document.tags,
                        created_at=document.created_at,
                    )
                    search_results.append(search_result)
                
                # Create search metadata
                search_time_ms = int((time.time() - start_time) * 1000)
                search_metadata = SearchMetadata(
                    query=query,
                    total_results=len(search_results),
                    returned_results=len(search_results),
                    search_time_ms=search_time_ms,
                    filters_applied=filters,
                    search_type="keyword"
                )
                
                return SearchResponse(
                    results=search_results,
                    search_metadata=search_metadata
                )
                
        except Exception as e:
            logger.error(f"Keyword search failed: {str(e)}")
            raise
    
    async def hybrid_search(
        self,
        query: str,
        project_id: UUID,
        collection_id: Optional[UUID] = None,
        limit: int = 20,
        min_score: float = 0.0,
        filters: Optional[Dict[str, Any]] = None
    ) -> SearchResponse:
        """
        Perform hybrid search using PGVectorStore's built-in hybrid search capabilities.

        This method leverages PGVectorStore's native hybrid search which combines
        semantic vector search with PostgreSQL's full-text search (TSV) capabilities
        using reciprocal rank fusion for optimal results.

        Args:
            query: Search query text
            project_id: Project ID for multi-tenant isolation
            collection_id: Optional collection to search within
            limit: Maximum number of results
            min_score: Minimum combined score threshold
            semantic_weight: Weight for semantic search (kept for API compatibility, not used)
            keyword_weight: Weight for keyword search (kept for API compatibility, not used)
            filters: Additional filters to apply

        Returns:
            SearchResponse with hybrid search results using native PGVectorStore capabilities
        """
        start_time = time.time()

        try:
            # Build filter dictionary for project and collection filtering
            filter_dict = {"project_id": {"$eq": project_id}}
            if collection_id:
                filter_dict["collection_id"] = {"$eq": collection_id}

            # Add any additional filters
            if filters:
                filter_dict.update(filters)

            # Use PGVectorStore's per-project hybrid (vector) search by binding the project's embedding client
            embedding_service = await get_embedding_service_for_project(project_id)
            vector_results = await self.vector_store_service.similarity_search_for_project(
                query=query,
                project_key=str(project_id),
                embeddings_client=embedding_service.embeddings_client,
                k=limit,
                filter_dict=filter_dict,
                score_threshold=min_score,
            )

            # Convert vector store results to SearchResult objects
            search_results = []
            for doc, score in vector_results:
                document_id = doc.id
                if document_id:
                    # Get additional document info from database
                    document_info = await self._get_document_info(UUID(document_id), project_id)
                    if document_info:
                        search_result = SearchResult(
                            document_id=UUID(document_id),
                            file_id=document_info.get("file_id"),
                            collection_id=document_info.get("collection_id"),
                            relevance_score=float(score),
                            content_preview=doc.page_content,
                            document_title=document_info.get("document_title"),
                            content_type=document_info.get("content_type"),
                            chunk_index=document_info.get("chunk_index"),
                            page_number=document_info.get("page_number"),
                            section_title=document_info.get("section_title"),
                            tags=document_info.get("tags", {}),
                            created_at=document_info.get("created_at"),
                        )
                        search_results.append(search_result)

            # Create search metadata
            search_time_ms = int((time.time() - start_time) * 1000)
            search_metadata = SearchMetadata(
                query=query,
                total_results=len(search_results),
                returned_results=len(search_results),
                search_time_ms=search_time_ms,
                filters_applied=filters,
                search_type="hybrid"
            )

            return SearchResponse(
                results=search_results,
                search_metadata=search_metadata
            )
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            raise
    

    async def _get_document_info(self, document_id: UUID, project_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get document information from database with project filtering.

        Args:
            document_id: Document UUID
            project_id: Project ID for multi-tenant isolation

        Returns:
            Document information dictionary or None if not found
        """
        async with get_db_session() as db:
            query = select(FileDocument).where(
                and_(
                    FileDocument.id == document_id,
                    FileDocument.project_id == project_id
                )
            )
            result = await db.execute(query)
            document = result.scalar_one_or_none()
            
            if document:
                return {
                    "file_id": document.file_id,
                    "collection_id": document.collection_id,
                    "document_title": document.document_title,
                    "content_type": document.content_type,
                    "chunk_index": document.chunk_index,
                    "page_number": document.page_number,
                    "section_title": document.section_title,
                    "tags": document.tags,
                    "created_at": document.created_at,
                }
            
            return None


# Global search service instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """
    Get the global search service instance.
    
    Returns:
        SearchService instance
    """
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
