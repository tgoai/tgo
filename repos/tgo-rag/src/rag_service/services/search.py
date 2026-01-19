"""
Search service implementing hybrid search with vector similarity and keyword matching.
"""

import asyncio
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
from .query_processor import get_query_processor

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
                            metadata=document_info.get("metadata", {}),
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
            from ..models import File as FileModel
            async with get_db_session() as db:
                # Detect if query has Chinese characters
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in query)
                
                # Build query using trigram similarity for Chinese and TSV for English
                if has_chinese:
                    # Trigram similarity matching for Chinese (requires pg_trgm)
                    # We also combine with ILIKE for exact substring matching
                    base_query = select(
                        FileDocument,
                        FileModel,
                        func.similarity(FileDocument.content, query).label('rank')
                    ).outerjoin(
                        FileModel, FileDocument.file_id == FileModel.id
                    ).where(
                        and_(
                            or_(
                                FileDocument.content.op('%')(query),
                                FileDocument.content.ilike(f"%{query}%")
                            ),
                            FileDocument.project_id == project_id
                        )
                    )
                else:
                    # Standard TSV for English/other languages
                    base_query = select(
                        FileDocument,
                        FileModel,
                        func.ts_rank_cd(
                            FileDocument.content_tsv,
                            func.websearch_to_tsquery('english', query) # Use english for non-chinese
                        ).label('rank')
                    ).outerjoin(
                        FileModel, FileDocument.file_id == FileModel.id
                    ).where(
                        and_(
                            FileDocument.content_tsv.op('@@')(
                                func.websearch_to_tsquery('english', query)
                            ),
                            FileDocument.project_id == project_id
                        )
                    )

                # Apply content_type filter
                if filters and "content_type" in filters:
                    content_types = filters["content_type"]
                    if isinstance(content_types, list):
                        base_query = base_query.where(FileDocument.content_type.in_(content_types))
                    else:
                        base_query = base_query.where(FileDocument.content_type == content_types)

                # Apply score threshold and ordering
                if min_score > 0 and not has_chinese:
                    base_query = base_query.where(text(f"ts_rank_cd(content_tsv, websearch_to_tsquery('english', :query)) >= {min_score}"))
                elif min_score > 0 and has_chinese:
                    base_query = base_query.where(func.similarity(FileDocument.content, query) >= min_score)
                
                base_query = base_query.order_by(text("rank DESC")).limit(limit)
                
                # Execute query
                result = await db.execute(base_query, {"query": query})
                rows = result.all()
                
                # Convert to search results
                search_results = []
                for document, file, rank in rows:
                    source_name = file.original_filename if file else "Unknown"
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
                        metadata={
                            "source": source_name,
                            "filename": source_name,
                            "file_size": file.file_size if file else 0
                        },
                        created_at=document.created_at,
                    )
                    search_results.append(search_result)
                
                logger.debug(f"[KeywordSearch] Found {len(search_results)} results for query '{query}'")
                
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
        Perform hybrid search with RRF fusion, optional reranking, and traceability metadata.
        """
        start_time = time.time()
        try:
            # 0. Query preprocessing - expand query for better recall
            processor = get_query_processor()
            query_variants = await processor.expand_query(query)
            
            # 1. Candidate Retrieval (Semantic + Keyword)
            # Use configurable candidate multiplier for better reranking quality
            candidate_limit = limit * self.settings.candidate_multiplier
            
            # Multi-query retrieval for better recall
            # We accumulate RRF scores for each unique document across all query variants and search types
            k = self.settings.rrf_k
            scores: Dict[UUID, float] = {}
            docs_cache: Dict[UUID, SearchResult] = {}
            rank_info: Dict[UUID, Dict[str, List[int]]] = {}
            
            for q_idx, q in enumerate(query_variants):
                semantic_task = self.semantic_search(
                    query=q,
                    project_id=project_id,
                    collection_id=collection_id,
                    limit=candidate_limit,
                    min_score=min_score,
                    filters=filters
                )
                
                keyword_task = self.keyword_search(
                    query=q,
                    project_id=project_id,
                    collection_id=collection_id,
                    limit=candidate_limit,
                    min_score=min_score,
                    filters=filters
                )
                
                semantic_res, keyword_res = await asyncio.gather(semantic_task, keyword_task)
                
                # Accumulate semantic results for this variant
                for rank, result in enumerate(semantic_res.results):
                    doc_id = result.document_id
                    score = 1.0 / (k + rank + 1)
                    scores[doc_id] = scores.get(doc_id, 0.0) + score
                    
                    if doc_id not in docs_cache:
                        docs_cache[doc_id] = result
                    
                    if doc_id not in rank_info:
                        rank_info[doc_id] = {"semantic": [], "keyword": []}
                    rank_info[doc_id]["semantic"].append(rank + 1)
                
                # Accumulate keyword results for this variant
                for rank, result in enumerate(keyword_res.results):
                    doc_id = result.document_id
                    score = 1.0 / (k + rank + 1)
                    scores[doc_id] = scores.get(doc_id, 0.0) + score
                    
                    if doc_id not in docs_cache:
                        docs_cache[doc_id] = result
                        
                    if doc_id not in rank_info:
                        rank_info[doc_id] = {"semantic": [], "keyword": []}
                    rank_info[doc_id]["keyword"].append(rank + 1)
            
            # Sort by accumulated RRF score
            sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            
            # 3. Take top results with normalized scores and traceability metadata
            final_docs = []
            if sorted_docs:
                # Normalize scores to 0-1 range (top result = 1.0 if we had a range)
                # But RRF scores are summations, so we normalize relative to the max found
                max_rrf = sorted_docs[0][1]
                min_rrf = sorted_docs[-1][1] if len(sorted_docs) > 1 else 0
                rrf_range = max_rrf - min_rrf if max_rrf != min_rrf else 1.0
                
                for doc_id, rrf_score in sorted_docs[:limit]:
                    doc = docs_cache[doc_id]
                    # Normalize score: 0-1 range
                    normalized_score = (rrf_score - min_rrf) / rrf_range if rrf_range > 0 else 1.0
                    
                    # Inject traceability metadata
                    doc.metadata = doc.metadata or {}
                    info = rank_info[doc_id]
                    doc.metadata.update({
                        "rrf_score_raw": round(rrf_score, 6),
                        "semantic_ranks": info["semantic"],
                        "keyword_ranks": info["keyword"],
                        "query_variants_count": len(query_variants)
                    })
                    # For compatibility, set best ranks
                    doc.metadata["semantic_rank"] = min(info["semantic"]) if info["semantic"] else None
                    doc.metadata["keyword_rank"] = min(info["keyword"]) if info["keyword"] else None
                    
                    doc.relevance_score = round(normalized_score, 4)
                    final_docs.append(doc)

            # Create search metadata
            search_time_ms = int((time.time() - start_time) * 1000)
            search_metadata = SearchMetadata(
                query=query,
                total_results=len(scores),
                returned_results=len(final_docs),
                search_time_ms=search_time_ms,
                filters_applied=filters,
                search_type="hybrid_rrf"
            )

            return SearchResponse(
                results=final_docs,
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
        from ..models import File  # Import locally to avoid circular imports if any
        
        async with get_db_session() as db:
            query = select(FileDocument, File).outerjoin(
                File, FileDocument.file_id == File.id
            ).where(
                and_(
                    FileDocument.id == document_id,
                    FileDocument.project_id == project_id
                )
            )
            result = await db.execute(query)
            row = result.first()
            
            if row:
                document, file = row
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
                    "metadata": {
                        "source": file.original_filename if file else "Unknown",
                        "filename": file.original_filename if file else None,
                        "file_size": file.file_size if file else None,
                    }
                }
            
            return None

    def _create_content_preview(self, content: Optional[str], length: int = 200) -> str:
        """
        Create a preview of the content for display.

        Args:
            content: Full content string
            length: Maximum length of preview

        Returns:
            Truncated content string
        """
        if not content:
            return ""
        
        if len(content) <= length:
            return content
            
        return content[:length] + "..."


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
