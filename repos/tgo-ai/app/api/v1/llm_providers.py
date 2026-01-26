"""LLM Provider sync API for tgo-api -> tgo-ai."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.responses import build_error_responses
from app.core.logging import get_logger
from app.dependencies import get_db
from app.schemas.llm_provider import (
    LLMProviderResponse,
    LLMProviderSyncRequest,
    LLMProviderSyncResponse,
)
from app.services.llm_provider_service import LLMProviderService

logger = get_logger(__name__)

router = APIRouter()


def get_llm_provider_service(db: AsyncSession = Depends(get_db)) -> LLMProviderService:
    return LLMProviderService(db)


@router.post(
    "/sync",
    response_model=LLMProviderSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk upsert LLM Providers",
    description="Upsert LLM Providers. Each item must include id and project_id; if a provider (project_id, alias) exists it will be updated, otherwise created. The id is provided by tgo-api.",
    responses=build_error_responses([400, 500]),
)
async def sync_llm_providers(
    request: LLMProviderSyncRequest,
    service: LLMProviderService = Depends(get_llm_provider_service),
) -> LLMProviderSyncResponse:
    if not request.providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No providers provided for sync",
        )

    try:
        providers = await service.sync_providers(
            [p.model_dump() for p in request.providers],
        )
    except SQLAlchemyError as exc:
        logger.error(f"Database error during LLM provider sync: {str(exc)}", exc_info=exc)
        # If it's a conflict or other DB error, we want to see it
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync LLM providers: database error - {str(exc)}",
        )
    except Exception as exc:
        logger.error(f"Unexpected error during LLM provider sync: {str(exc)}", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync LLM providers: unexpected error - {str(exc)}",
        )

    if len(providers) != len(request.providers):
        logger.warning(
            "Provider sync count mismatch",
            expected=len(request.providers),
            actual=len(providers),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync incomplete: expected {len(request.providers)} providers, got {len(providers)}",
        )

    return LLMProviderSyncResponse(data=[LLMProviderResponse.from_orm_model(p) for p in providers])

