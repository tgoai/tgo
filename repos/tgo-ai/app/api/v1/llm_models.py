"""LLM Model sync API for tgo-api -> tgo-ai."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import build_error_responses
from app.core.logging import get_logger
from app.dependencies import get_db
from app.schemas.llm_model import (
    LLMModelResponse,
    LLMModelSyncRequest,
    LLMModelSyncResponse,
)
from app.services.llm_model_service import LLMModelService

logger = get_logger(__name__)

router = APIRouter()


def get_llm_model_service(db: AsyncSession = Depends(get_db)) -> LLMModelService:
    return LLMModelService(db)


@router.post(
    "/sync",
    response_model=LLMModelSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk upsert LLM Models",
    description="Upsert LLM Models. The id is provided by tgo-api.",
    responses=build_error_responses([400, 500]),
)
async def sync_llm_models(
    request: LLMModelSyncRequest,
    service: LLMModelService = Depends(get_llm_model_service),
) -> LLMModelSyncResponse:
    if not request.models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No models provided for sync",
        )

    try:
        models = await service.sync_models(
            [m.model_dump() for m in request.models],
        )
    except SQLAlchemyError as exc:
        logger.error("Database error during LLM model sync", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync LLM models: database error",
        )
    except Exception as exc:
        logger.error("Unexpected error during LLM model sync", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync LLM models: unexpected error",
        )

    return LLMModelSyncResponse(data=[LLMModelResponse.from_orm_model(m) for m in models])
