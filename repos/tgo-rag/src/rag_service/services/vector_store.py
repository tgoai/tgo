"""
Vector store service using langchain-postgres for vector operations.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import ProgrammingError
from langchain_postgres import PGEngine, PGVectorStore
from langchain_core.documents import Document
from langchain_postgres.v2.vectorstores import DistanceStrategy
from langchain_postgres.v2.hybrid_search_config import (
    HybridSearchConfig,
    reciprocal_rank_fusion,
)
from sqlalchemy import create_engine

from ..config import get_settings
from ..database import get_db_session
from ..logging_config import get_logger
from ..models import FileDocument
from .embedding import get_embedding_service

logger = get_logger(__name__)

TABLE_NAME = FileDocument.table_name
ID_COLUMN = "id"
CONTENT_COLUMN = "content"
METADATA_COLUMNS = ["file_id", "collection_id", "project_id"]
VECTOR_SIZE = 1536


class VectorStoreService:
    """Service for vector storage and retrieval operations."""

    def __init__(self):
        """Initialize the vector store service."""
        self.settings = get_settings()
        self.embedding_service = get_embedding_service()
        # Legacy single-store (global) instance
        self._vector_store: Optional[PGVectorStore] = None
        # Per-project vector store cache keyed by project key (e.g., project_id)
        self._vector_stores: dict[str, PGVectorStore] = {}
        self._pg_engine: Optional[PGEngine] = None
        self._hybrid_search_config = None

    def _create_hybrid_search_config(self) -> HybridSearchConfig:
        """
        Create hybrid search configuration for PGVectorStore.

        Returns:
            HybridSearchConfig: Configuration for hybrid search
        """
        return HybridSearchConfig(
            tsv_column=f"{CONTENT_COLUMN}_tsv",
            tsv_lang="pg_catalog.english",
            fusion_function=reciprocal_rank_fusion,
            fusion_function_parameters={
                "rrf_k": 60,
                "fetch_top_k": 20,
            },
        )

    async def get_vector_store(self) -> PGVectorStore:
        """
        Get or create the PGVectorStore instance.

        Returns:
            PGVectorStore instance for vector operations
        """
        if self._vector_store is None:
            # Create synchronous engine for langchain-postgres
            sync_db_url = self.settings.database_url

            # Create PGEngine instance
            self._pg_engine = PGEngine.from_connection_string(sync_db_url)

            # Create hybrid search configuration
            self._hybrid_search_config = self._create_hybrid_search_config()

            try:
                self._pg_engine.init_vectorstore_table(
                    table_name=TABLE_NAME,
                    id_column= ID_COLUMN,
                    content_column=CONTENT_COLUMN,
                    metadata_columns=METADATA_COLUMNS,
                    vector_size=VECTOR_SIZE,
                    hybrid_search_config=self._hybrid_search_config
                )

            except ProgrammingError as e:
                print(f"Table already exists. Skipping creation.{str(e)}")
            # Create PGVectorStore instance using the create method
            self._vector_store = await PGVectorStore.create(
                engine=self._pg_engine,
                embedding_service=self.embedding_service.embeddings_client,
                id_column=ID_COLUMN,
                metadata_columns=METADATA_COLUMNS,
                content_column=CONTENT_COLUMN,
                table_name=TABLE_NAME,
                distance_strategy=DistanceStrategy.COSINE_DISTANCE,
                hybrid_search_config=self._hybrid_search_config,
            )
        return self._vector_store

    async def get_vector_store_for_project(self, project_key: str, embeddings_client: Any) -> PGVectorStore:
        """Get or create a PGVectorStore instance bound to a specific project/config.

        A separate store object is cached per project key so that the appropriate
        embedding client (provider/model/api key) is used for that project.
        """
        # Initialize shared PGEngine and hybrid config once
        if self._pg_engine is None:
            sync_db_url = self.settings.database_url
            self._pg_engine = PGEngine.from_connection_string(sync_db_url)
            self._hybrid_search_config = self._create_hybrid_search_config()
            try:
                self._pg_engine.init_vectorstore_table(
                    table_name=TABLE_NAME,
                    id_column=ID_COLUMN,
                    content_column=CONTENT_COLUMN,
                    metadata_columns=METADATA_COLUMNS,
                    vector_size=VECTOR_SIZE,
                    hybrid_search_config=self._hybrid_search_config,
                )
            except ProgrammingError as e:
                print(f"Table already exists. Skipping creation.{str(e)}")

        # Create per-project store if missing
        if project_key not in self._vector_stores:
            self._vector_stores[project_key] = await PGVectorStore.create(
                engine=self._pg_engine,
                embedding_service=embeddings_client,
                id_column=ID_COLUMN,
                metadata_columns=METADATA_COLUMNS,
                content_column=CONTENT_COLUMN,
                table_name=TABLE_NAME,
                distance_strategy=DistanceStrategy.COSINE_DISTANCE,
                hybrid_search_config=self._hybrid_search_config,
            )

        return self._vector_stores[project_key]


    async def add_documents_batch_for_project(
        self,
        documents: List[Tuple[UUID, str, Optional[Dict[str, Any]]]],
        project_key: str,
        embedding_client: Any,
    ) -> List[str]:
        """Add multiple documents using the project-scoped embedding client.

        This mirrors add_documents_batch but binds to a per-project vector store
        created with the given embedding client.
        """
        if not documents:
            return []

        try:
            # Create/retrieve per-project vector store bound to the embedding client
            vector_store = await self.get_vector_store_for_project(project_key, embedding_client)

            # Get batch size from settings, with a maximum of 10 for Qwen3 compatibility
            max_batch_size = min(self.settings.embedding_batch_size, 10)
            logger.info(f"Processing {len(documents)} documents in batches of {max_batch_size} for project {project_key}")

            all_vector_ids: List[str] = []
            total_batches = (len(documents) + max_batch_size - 1) // max_batch_size

            import asyncio
            loop = asyncio.get_event_loop()

            # Process documents in batches
            for batch_idx in range(0, len(documents), max_batch_size):
                batch_documents = documents[batch_idx:batch_idx + max_batch_size]
                batch_num = (batch_idx // max_batch_size) + 1
                logger.debug(f"Processing batch {batch_num}/{total_batches} with {len(batch_documents)} documents for project {project_key}")

                # Prepare lists
                document_ids = [doc[0] for doc in batch_documents]
                contents = [doc[1] for doc in batch_documents]
                metadatas: List[Dict[str, Any]] = []
                for doc_id, content, metadata in batch_documents:
                    doc_metadata = metadata or {}
                    doc_metadata.update({
                        "document_id": str(doc_id),
                        "content_length": len(content),
                    })
                    metadatas.append(doc_metadata)

                try:
                    vector_ids = await loop.run_in_executor(
                        None,
                        lambda: vector_store.add_texts(
                            texts=contents,
                            metadatas=metadatas,
                            ids=[str(doc_id) for doc_id in document_ids],
                        )
                    )
                    all_vector_ids.extend(vector_ids)
                    logger.debug(f"Successfully processed batch {batch_num}/{total_batches} for project {project_key}")
                except Exception as batch_error:
                    logger.error(f"Failed to process batch {batch_num}/{total_batches} for project {project_key}: {str(batch_error)}")
                    all_vector_ids.extend([""] * len(batch_documents))

            logger.info(f"Completed batch processing for project {project_key}: {len(all_vector_ids)} total documents processed")
            return all_vector_ids

        except Exception as e:
            logger.error(f"Failed to add document embeddings batch for project {project_key}: {str(e)}")
            raise



    async def add_document_embedding(
        self,
        document_id: UUID,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a document embedding to the vector store.

        Args:
            document_id: UUID of the document
            content: Document content to embed
            metadata: Optional metadata to store with the embedding

        Returns:
            Vector ID in the vector store

        Raises:
            Exception: If embedding generation or storage fails
        """
        try:
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(content)

            # Prepare metadata
            doc_metadata = metadata or {}
            doc_metadata.update({
                "document_id": str(document_id),
                "content_length": len(content),
            })

            # Add to vector store
            vector_store = await self.get_vector_store()

            # Run synchronous operation in thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            vector_ids = await loop.run_in_executor(
                None,
                lambda: vector_store.add_texts(
                    texts=[content],
                    metadatas=[doc_metadata],
                    ids=[str(document_id)]
                )
            )

            vector_id = vector_ids[0] if vector_ids else str(document_id)

            # Update document record with embedding info
            await self._update_document_embedding_info(
                document_id,
                embedding
            )

            logger.info(f"Added embedding for document {document_id}")
            return vector_id

        except Exception as e:
            logger.error(f"Failed to add document embedding {document_id}: {str(e)}")
            raise

    async def add_documents_batch(
        self,
        documents: List[Tuple[UUID, str, Optional[Dict[str, Any]]]]
    ) -> List[str]:
        """
        Add multiple document embeddings in batch with automatic batch size management.

        This method automatically splits large batches into smaller chunks to respect
        API limitations (e.g., Qwen3 API limit of 10 documents per batch).

        Args:
            documents: List of (document_id, content, metadata) tuples

        Returns:
            List of vector IDs in the vector store

        Raises:
            Exception: If batch processing fails
        """
        if not documents:
            return []

        try:
            # Get batch size from settings, with a maximum of 10 for Qwen3 compatibility
            max_batch_size = min(self.settings.embedding_batch_size, 10)
            logger.info(f"Processing {len(documents)} documents in batches of {max_batch_size}")

            all_vector_ids = []
            total_batches = (len(documents) + max_batch_size - 1) // max_batch_size

            # Process documents in batches
            for batch_idx in range(0, len(documents), max_batch_size):
                batch_documents = documents[batch_idx:batch_idx + max_batch_size]
                batch_num = (batch_idx // max_batch_size) + 1
                logger.debug(f"Processing batch {batch_num}/{total_batches} with {len(batch_documents)} documents")

                try:
                    # Process single batch
                    batch_vector_ids = await self._process_single_batch(batch_documents)
                    all_vector_ids.extend(batch_vector_ids)

                    logger.debug(f"Successfully processed batch {batch_num}/{total_batches}")

                except Exception as batch_error:
                    logger.error(f"Failed to process batch {batch_num}/{total_batches}: {str(batch_error)}")
                    # Continue with other batches instead of failing completely
                    # Add empty strings as placeholders for failed batch
                    all_vector_ids.extend([""] * len(batch_documents))

            logger.info(f"Completed batch processing: {len(all_vector_ids)} total documents processed")
            return all_vector_ids

        except Exception as e:
            logger.error(f"Failed to add document embeddings batch: {str(e)}")
            raise

    async def _process_single_batch(
        self,
        batch_documents: List[Tuple[UUID, str, Optional[Dict[str, Any]]]]
    ) -> List[str]:
        """
        Process a single batch of documents.

        Args:
            batch_documents: List of (document_id, content, metadata) tuples for this batch

        Returns:
            List of vector IDs for this batch

        Raises:
            Exception: If batch processing fails
        """
        # Extract data for batch processing
        document_ids = [doc[0] for doc in batch_documents]
        contents = [doc[1] for doc in batch_documents]
        metadatas = []

        for doc_id, content, metadata in batch_documents:
            doc_metadata = metadata or {}
            doc_metadata.update({
                "document_id": str(doc_id),
                "content_length": len(content),
            })
            metadatas.append(doc_metadata)

        # Add to vector store
        vector_store = await self.get_vector_store()

        # Run synchronous operation in thread pool
        import asyncio
        loop = asyncio.get_event_loop()

        print("contents--->",len(contents))
        vector_ids = await loop.run_in_executor(
            None,
            lambda: vector_store.add_texts(
                texts=contents,
                metadatas=metadatas,
                ids=[str(doc_id) for doc_id in document_ids]
            )
        )

        return vector_ids

    async def similarity_search(
        self,
        query: str,
        k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search in the vector store.

        Args:
            query: Search query text
            k: Number of results to return
            filter_dict: Optional metadata filters
            score_threshold: Minimum similarity score threshold

        Returns:
            List of (content, score, metadata) tuples

        Raises:
            Exception: If search fails
        """
        try:
            vector_store = await self.get_vector_store()
            # Run synchronous operation in thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: vector_store.similarity_search_with_score(
                    query=query,
                    k=k,
                    filter=filter_dict
                )
            )


            # Filter by score threshold if provided
            if score_threshold is not None and score_threshold > 0:
                results = [
                    (doc, score) for doc, score in results
                    if score >= score_threshold
                ]

            logger.debug(f"Similarity search returned {len(results)} results")

            # 1- score,  the smaller, the more similar in langchain-postgres
            new_results = []
            for doc, score in results:
                if score is not None:
                    new_results.append((doc, score))

            return new_results

        except Exception as e:
            logger.error(f"Similarity search failed: {str(e)}")
            raise


    async def similarity_search_for_project(
        self,
        query: str,
        project_key: str,
        embeddings_client: Any,
        k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search using a vector store bound to the project's
        embedding configuration.

        Args:
            query: Search query text
            project_key: Project identifier (e.g., project_id as string)
            embeddings_client: Embedding client configured for the project
            k: Number of results to return
            filter_dict: Optional metadata filters
            score_threshold: Minimum similarity score threshold

        Returns:
            List of (Document, score) tuples
        """
        try:
            # Use per-project vector store bound to the provided embedding client
            vector_store = await self.get_vector_store_for_project(project_key, embeddings_client)
            # Run synchronous operation in thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: vector_store.similarity_search_with_score(
                    query=query,
                    k=k,
                    filter=filter_dict,
                ),
            )

            # Filter by score threshold if provided
            if score_threshold is not None and score_threshold > 0:
                results = [(doc, score) for doc, score in results if score >= score_threshold]

            # Ensure we only return entries with a numeric score
            new_results = []
            for doc, score in results:
                if score is not None:
                    new_results.append((doc, score))
            return new_results
        except Exception as e:
            logger.error(f"Similarity search (per-project) failed: {str(e)}")
            raise

    async def delete_document_embedding(self, document_id: UUID) -> bool:
        """
        Delete a document embedding from the vector store.

        Args:
            document_id: UUID of the document to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            vector_store = await self.get_vector_store()

            # Run synchronous operation in thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: vector_store.delete(ids=[str(document_id)])
            )

            logger.info(f"Deleted embedding for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document embedding {document_id}: {str(e)}")
            return False

    async def _update_document_embedding_info(
        self,
        document_id: UUID,
        embedding: List[float]
    ) -> None:
        """
        Update document record with embedding information.

        Args:
            document_id: Document UUID
            embedding: Embedding vector
        """
        try:
            # Import here to avoid circular imports
            from ..database import async_session_factory, create_session_factory
            from sqlalchemy import update, select

            # Ensure session factory is initialized
            if async_session_factory is None:
                create_session_factory()

            # Use session factory directly to avoid context manager issues in Celery
            async with async_session_factory() as db:
                try:
                    # First check if document exists
                    result = await db.execute(
                        select(FileDocument).where(FileDocument.id == document_id)
                    )
                    document = result.scalar_one_or_none()

                    if not document:
                        logger.warning(f"Document {document_id} not found for embedding update")
                        return

                    # Update document with embedding info
                    stmt = update(FileDocument).where(
                        FileDocument.id == document_id
                    ).values(
                        embedding=embedding,
                        embedding_model=self.embedding_service.get_embedding_model(),
                        embedding_dimensions=self.embedding_service.get_embedding_dimensions(),
                    )

                    await db.execute(stmt)
                    await db.commit()

                    logger.debug(f"Updated embedding info for document {document_id}")

                except Exception as e:
                    await db.rollback()
                    raise e
                finally:
                    await db.close()

        except Exception as e:
            logger.error(f"Failed to update document embedding info for {document_id}: {str(e)}")
            # Don't raise the exception to avoid breaking the entire batch process
            # The embeddings are still generated and stored in the vector store


# Global vector store service instance
_vector_store_service: Optional[VectorStoreService] = None


def get_vector_store_service() -> VectorStoreService:
    """
    Get the global vector store service instance.

    Returns:
        VectorStoreService instance
    """
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service
