"""
QA pair processing tasks.

This module provides Celery tasks for processing QA pairs,
generating embeddings, and storing them in the vector store.

Unlike file processing, QA pairs are NOT chunked - each Q+A
is treated as a single document for embedding.
"""

import asyncio
from typing import Any, Dict, List
from uuid import UUID, uuid4

from .celery_app import celery_app
from .document_processing_errors import DocumentProcessingError, ProcessingStep
from ..database import get_db_session, reset_db_state
from ..logging_config import get_logger
from ..models import FileDocument, QAPair
from ..services.embedding import get_embedding_service_for_project
from ..services.vector_store import get_vector_store_service

logger = get_logger(__name__)


def build_qa_content(question: str, answer: str) -> str:
    """Build combined content from question and answer for embedding."""
    return f"问题: {question}\n\n答案: {answer}"


async def process_qa_pair_async(
    qa_pair_id: UUID,
    project_id: UUID,
    is_update: bool = False,
) -> Dict[str, Any]:
    """
    Process a single QA pair: create/update FileDocument and generate embedding.
    
    Args:
        qa_pair_id: UUID of the QA pair to process
        project_id: Project ID for embedding service resolution
        is_update: Whether this is an update to existing QA pair
        
    Returns:
        Dict with processing result
    """
    try:
        async with get_db_session() as db:
            # Load QA pair
            from sqlalchemy import select
            result = await db.execute(
                select(QAPair).where(QAPair.id == qa_pair_id)
            )
            qa_pair = result.scalar_one_or_none()
            
            if not qa_pair:
                raise DocumentProcessingError(
                    f"QA pair not found: {qa_pair_id}",
                    str(qa_pair_id),
                    ProcessingStep.LOADING_FILE
                )
            
            # Update status to processing
            qa_pair.status = "processing"
            await db.commit()
        
        # Build content for embedding
        content = build_qa_content(qa_pair.question, qa_pair.answer)
        
        # Get services
        vector_store_service = get_vector_store_service()
        embedding_service = await get_embedding_service_for_project(project_id)
        
        # Create or update FileDocument
        async with get_db_session() as db:
            if is_update and qa_pair.document_id:
                # Update existing document
                result = await db.execute(
                    select(FileDocument).where(FileDocument.id == qa_pair.document_id)
                )
                document = result.scalar_one_or_none()
                
                if document:
                    document.content = content
                    document.document_title = qa_pair.question[:500]
                    document.content_length = len(content)
                    document.tags = {
                        "qa_pair_id": str(qa_pair.id),
                        "source_type": "qa",
                        "category": qa_pair.category,
                        "subcategory": qa_pair.subcategory,
                    }
                else:
                    # Document was deleted, create new one
                    is_update = False
            
            if not is_update or not qa_pair.document_id:
                # Create new FileDocument (no file_id for QA pairs)
                document_id = uuid4()
                document = FileDocument(
                    id=document_id,
                    project_id=qa_pair.project_id,
                    file_id=None,  # QA pairs don't have associated files
                    collection_id=qa_pair.collection_id,
                    content=content,
                    document_title=qa_pair.question[:500],
                    content_length=len(content),
                    chunk_index=0,
                    content_type="qa_pair",
                    tags={
                        "qa_pair_id": str(qa_pair.id),
                        "source_type": "qa",
                        "category": qa_pair.category,
                        "subcategory": qa_pair.subcategory,
                    }
                )
                db.add(document)
                
                # Update QA pair with document reference
                result = await db.execute(
                    select(QAPair).where(QAPair.id == qa_pair_id)
                )
                qa_pair_to_update = result.scalar_one()
                qa_pair_to_update.document_id = document.id
            
            await db.commit()
            document_id = document.id
        
        # Generate embedding and add to vector store
        metadata = {
            "project_id": project_id,
            "collection_id": qa_pair.collection_id,
            "qa_pair_id": str(qa_pair.id),
            "chunk_id": str(document_id),
            "chunk_index": 0,
            "character_count": len(content),
            "token_count": len(content.split()),
            "document_type": "qa_pair",
            "source_type": "qa",
            "category": qa_pair.category,
        }
        
        documents = [(document_id, content, metadata)]
        
        vector_ids = await vector_store_service.add_documents_batch_for_project(
            documents=documents,
            project_key=str(project_id),
            embedding_client=embedding_service.embeddings_client,
        )
        
        # Update QA pair status
        async with get_db_session() as db:
            result = await db.execute(
                select(QAPair).where(QAPair.id == qa_pair_id)
            )
            qa_pair = result.scalar_one()
            qa_pair.status = "processed"
            await db.commit()
        
        logger.info(f"Successfully processed QA pair {qa_pair_id}")
        
        return {
            "success": True,
            "qa_pair_id": str(qa_pair_id),
            "document_id": str(document_id),
            "vector_id": vector_ids[0] if vector_ids else None,
        }
        
    except Exception as e:
        logger.error(f"Failed to process QA pair {qa_pair_id}: {e}")
        # Update status to failed
        try:
            async with get_db_session() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(QAPair).where(QAPair.id == qa_pair_id)
                )
                qa_pair = result.scalar_one_or_none()
                if qa_pair:
                    qa_pair.status = "failed"
                    qa_pair.error_message = str(e)[:1000]
                    await db.commit()
        except Exception:
            pass
        
        return {
            "success": False,
            "qa_pair_id": str(qa_pair_id),
            "error": str(e),
        }


async def process_qa_pairs_batch_async(
    qa_pair_ids: List[UUID],
    project_id: UUID,
) -> Dict[str, Any]:
    """
    Process multiple QA pairs in batch.

    Args:
        qa_pair_ids: List of QA pair UUIDs to process
        project_id: Project ID for embedding service resolution

    Returns:
        Dict with batch processing results
    """
    results = {
        "success": True,
        "processed_count": 0,
        "failed_count": 0,
        "results": [],
    }

    for qa_pair_id in qa_pair_ids:
        result = await process_qa_pair_async(qa_pair_id, project_id)
        results["results"].append(result)

        if result["success"]:
            results["processed_count"] += 1
        else:
            results["failed_count"] += 1

    results["success"] = results["failed_count"] == 0
    return results


async def delete_qa_pair_document_async(
    qa_pair_id: UUID,
    document_id: UUID,
    project_id: UUID,
) -> Dict[str, Any]:
    """
    Delete the FileDocument and vector embedding for a QA pair.

    Args:
        qa_pair_id: UUID of the QA pair
        document_id: UUID of the associated FileDocument
        project_id: Project ID

    Returns:
        Dict with deletion result
    """
    try:
        # Delete from vector store
        vector_store_service = get_vector_store_service()
        embedding_service = await get_embedding_service_for_project(project_id)

        try:
            vector_store = await vector_store_service.get_vector_store_for_project(
                str(project_id),
                embedding_service.embeddings_client
            )
            # Delete by document ID
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: vector_store.delete(ids=[str(document_id)])
            )
        except Exception as e:
            logger.warning(f"Failed to delete from vector store: {e}")

        # Delete FileDocument from database
        async with get_db_session() as db:
            from sqlalchemy import delete
            await db.execute(
                delete(FileDocument).where(FileDocument.id == document_id)
            )
            await db.commit()

        logger.info(f"Deleted document {document_id} for QA pair {qa_pair_id}")

        return {"success": True, "document_id": str(document_id)}

    except Exception as e:
        logger.error(f"Failed to delete document for QA pair {qa_pair_id}: {e}")
        return {"success": False, "error": str(e)}


# ============== Celery Tasks ==============

@celery_app.task(bind=True, name="process_qa_pair_task")
def process_qa_pair_task(self, qa_pair_id: str, project_id: str, is_update: bool = False) -> Dict[str, Any]:
    """
    Celery task for processing a single QA pair.

    Args:
        qa_pair_id: UUID string of the QA pair
        project_id: UUID string of the project
        is_update: Whether this is an update operation

    Returns:
        Processing result dictionary
    """
    try:
        qa_pair_uuid = UUID(qa_pair_id)
        project_uuid = UUID(project_id)

        reset_db_state()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                process_qa_pair_async(qa_pair_uuid, project_uuid, is_update)
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"QA pair processing task failed: {e}")
        return {
            "success": False,
            "qa_pair_id": qa_pair_id,
            "error": str(e),
        }


@celery_app.task(bind=True, name="process_qa_pairs_batch_task")
def process_qa_pairs_batch_task(self, qa_pair_ids: List[str], project_id: str) -> Dict[str, Any]:
    """
    Celery task for processing multiple QA pairs in batch.

    Args:
        qa_pair_ids: List of UUID strings
        project_id: UUID string of the project

    Returns:
        Batch processing result dictionary
    """
    try:
        qa_pair_uuids = [UUID(qid) for qid in qa_pair_ids]
        project_uuid = UUID(project_id)

        reset_db_state()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                process_qa_pairs_batch_async(qa_pair_uuids, project_uuid)
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"QA pairs batch processing task failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }

