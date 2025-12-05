"""RAG QA Pairs proxy endpoints.

Provides JWT-authenticated endpoints for staff to manage QA pairs in collections.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES
from app.core.security import get_current_active_user
from app.core.logging import get_logger
from app.models.staff import Staff
from app.schemas.rag import (
    QACategoryListResponse,
    QAPairBatchCreateRequest,
    QAPairBatchCreateResponse,
    QAPairCreateRequest,
    QAPairImportRequest,
    QAPairListResponse,
    QAPairResponse,
    QAPairUpdateRequest,
)
from app.services.rag_client import rag_client

logger = get_logger("endpoints.rag_qa_pairs")
router = APIRouter()


def _check_project(current_user: Staff) -> str:
    """Check if staff has a valid project and return project_id."""
    if not current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project",
        )
    return str(current_user.project_id)


@router.post(
    "/{collection_id}/qa-pairs",
    response_model=QAPairResponse,
    responses=CREATE_RESPONSES,
    summary="Create QA Pair",
    description="Add a single question-answer pair to a QA collection.",
)
async def create_qa_pair(
    collection_id: UUID,
    qa_data: QAPairCreateRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> QAPairResponse:
    """Create a single QA pair in a collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Creating QA pair",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id),
            "question_preview": qa_data.question[:50] if qa_data.question else None,
        },
    )

    result = await rag_client.create_qa_pair(
        project_id=project_id,
        collection_id=str(collection_id),
        qa_data=qa_data.model_dump(exclude_none=True),
    )
    return QAPairResponse.model_validate(result)


@router.get(
    "/{collection_id}/qa-pairs",
    response_model=QAPairListResponse,
    responses=LIST_RESPONSES,
    summary="List QA Pairs",
    description="Get paginated list of QA pairs in a collection.",
)
async def list_qa_pairs(
    collection_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: Staff = Depends(get_current_active_user),
) -> QAPairListResponse:
    """List QA pairs in a collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Listing QA pairs",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id),
            "category": category,
            "status": status_filter,
        },
    )

    result = await rag_client.list_qa_pairs(
        project_id=project_id,
        collection_id=str(collection_id),
        limit=limit,
        offset=offset,
        category=category,
        status=status_filter,
    )
    return QAPairListResponse.model_validate(result)


@router.post(
    "/{collection_id}/qa-pairs/batch",
    response_model=QAPairBatchCreateResponse,
    responses=CREATE_RESPONSES,
    summary="Batch Create QA Pairs",
    description="Create multiple QA pairs at once (max 1000).",
)
async def batch_create_qa_pairs(
    collection_id: UUID,
    batch_data: QAPairBatchCreateRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> QAPairBatchCreateResponse:
    """Batch create QA pairs in a collection."""
    project_id = _check_project(current_user)

    logger.info(
        "Batch creating QA pairs",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id),
            "count": len(batch_data.qa_pairs),
        },
    )

    result = await rag_client.batch_create_qa_pairs(
        project_id=project_id,
        collection_id=str(collection_id),
        qa_data=batch_data.model_dump(exclude_none=True),
    )
    return QAPairBatchCreateResponse.model_validate(result)


@router.post(
    "/{collection_id}/qa-pairs/import",
    response_model=QAPairBatchCreateResponse,
    responses=CREATE_RESPONSES,
    summary="Import QA Pairs",
    description="Import QA pairs from JSON or CSV format.",
)
async def import_qa_pairs(
    collection_id: UUID,
    import_data: QAPairImportRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> QAPairBatchCreateResponse:
    """Import QA pairs from JSON/CSV."""
    project_id = _check_project(current_user)

    logger.info(
        "Importing QA pairs",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id),
            "format": import_data.format,
        },
    )

    result = await rag_client.import_qa_pairs(
        project_id=project_id,
        collection_id=str(collection_id),
        import_data=import_data.model_dump(exclude_none=True),
    )
    return QAPairBatchCreateResponse.model_validate(result)


@router.get(
    "/qa-pairs/{qa_pair_id}",
    response_model=QAPairResponse,
    responses=CRUD_RESPONSES,
    summary="Get QA Pair",
    description="Get a single QA pair by ID.",
)
async def get_qa_pair(
    qa_pair_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> QAPairResponse:
    """Get a single QA pair."""
    project_id = _check_project(current_user)

    logger.info(
        "Getting QA pair",
        extra={"project_id": project_id, "qa_pair_id": str(qa_pair_id)},
    )

    result = await rag_client.get_qa_pair(
        project_id=project_id,
        qa_pair_id=str(qa_pair_id),
    )
    return QAPairResponse.model_validate(result)


@router.put(
    "/qa-pairs/{qa_pair_id}",
    response_model=QAPairResponse,
    responses=CRUD_RESPONSES,
    summary="Update QA Pair",
    description="Update an existing QA pair.",
)
async def update_qa_pair(
    qa_pair_id: UUID,
    qa_data: QAPairUpdateRequest,
    current_user: Staff = Depends(get_current_active_user),
) -> QAPairResponse:
    """Update a QA pair."""
    project_id = _check_project(current_user)

    logger.info(
        "Updating QA pair",
        extra={"project_id": project_id, "qa_pair_id": str(qa_pair_id)},
    )

    result = await rag_client.update_qa_pair(
        project_id=project_id,
        qa_pair_id=str(qa_pair_id),
        qa_data=qa_data.model_dump(exclude_none=True),
    )
    return QAPairResponse.model_validate(result)


@router.delete(
    "/qa-pairs/{qa_pair_id}",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Delete QA Pair",
    description="Soft delete a QA pair and its associated document.",
)
async def delete_qa_pair(
    qa_pair_id: UUID,
    current_user: Staff = Depends(get_current_active_user),
) -> None:
    """Delete a QA pair."""
    project_id = _check_project(current_user)

    logger.info(
        "Deleting QA pair",
        extra={"project_id": project_id, "qa_pair_id": str(qa_pair_id)},
    )

    await rag_client.delete_qa_pair(
        project_id=project_id,
        qa_pair_id=str(qa_pair_id),
    )


@router.get(
    "/qa-categories",
    response_model=QACategoryListResponse,
    responses=LIST_RESPONSES,
    summary="List QA Categories",
    description="Get distinct QA pair categories for the project, optionally filtered by collection.",
)
async def list_qa_categories(
    collection_id: Optional[UUID] = Query(None, description="Optional collection ID to filter"),
    current_user: Staff = Depends(get_current_active_user),
) -> QACategoryListResponse:
    """List distinct QA categories."""
    project_id = _check_project(current_user)

    logger.info(
        "Listing QA categories",
        extra={
            "project_id": project_id,
            "collection_id": str(collection_id) if collection_id else None,
        },
    )

    result = await rag_client.list_qa_categories(
        project_id=project_id,
        collection_id=str(collection_id) if collection_id else None,
    )
    return QACategoryListResponse.model_validate(result)

