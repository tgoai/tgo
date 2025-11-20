"""
Embedding configuration endpoints (no authentication required).
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session_dependency
from ..logging_config import get_logger
from ..models.embedding_config import EmbeddingConfig
from ..schemas.embedding_config import (
    EmbeddingConfigBatchSyncRequest,
    EmbeddingConfigBatchSyncResponse,
    EmbeddingConfigCreate,
    EmbeddingConfigResponse,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/batch-sync",
    response_model=EmbeddingConfigBatchSyncResponse,
    summary="Batch upsert embedding configurations for multiple projects (no auth)",
)
async def batch_sync_embedding_configs(
    request: EmbeddingConfigBatchSyncRequest,
    db: AsyncSession = Depends(get_db_session_dependency),
):
    """Batch upsert embedding configs.

    Behavior per item:
    - Enforce dimensions == 1536 (phase 1 compatibility)
    - Upsert by (project_id, is_active=True): update if exists, else insert new
    - Continue on errors; return summary
    """
    success_count = 0
    errors: List[dict] = []

    for cfg in request.configs:
        # Validate dimensions (phase 1 constraint)
        if cfg.dimensions != 1536:
            errors.append({
                "project_id": str(cfg.project_id),
                "message": "Invalid dimensions: only 1536 is supported in phase 1",
            })
            continue

        # Validate provider/model minimally (provider already validated by schema)
        try:
            # Use a SAVEPOINT per item to isolate failures
            async with db.begin_nested():
                # Always target the active configuration for upsert
                result = await db.execute(
                    select(EmbeddingConfig).where(
                        EmbeddingConfig.project_id == cfg.project_id,
                        EmbeddingConfig.is_active.is_(True),
                    )
                )
                existing: EmbeddingConfig | None = result.scalar_one_or_none()

                if existing:
                    existing.provider = cfg.provider
                    existing.model = cfg.model
                    existing.dimensions = cfg.dimensions
                    existing.batch_size = cfg.batch_size
                    existing.api_key = cfg.api_key
                    existing.base_url = cfg.base_url
                    existing.is_active = True  # enforce active for this endpoint
                else:
                    new_rec = EmbeddingConfig(
                        project_id=cfg.project_id,
                        provider=cfg.provider,
                        model=cfg.model,
                        dimensions=cfg.dimensions,
                        batch_size=cfg.batch_size,
                        api_key=cfg.api_key,
                        base_url=cfg.base_url,
                        is_active=True,
                    )
                    db.add(new_rec)

                # Flush to validate constraints immediately
                await db.flush()

            success_count += 1
        except Exception as e:
            logger.error(
                "Failed to upsert embedding config",
                project_id=str(cfg.project_id),
                error=str(e),
            )
            errors.append({
                "project_id": str(cfg.project_id),
                "message": str(e),
            })
            # The nested transaction is rolled back; outer transaction remains usable
            continue

    failed_count = len(errors)
    logger.info(
        "Batch sync completed",
        success_count=success_count,
        failed_count=failed_count,
    )

    return EmbeddingConfigBatchSyncResponse(
        success_count=success_count,
        failed_count=failed_count,
        errors=errors,
    )


@router.get(
    "/{project_id}",
    response_model=EmbeddingConfigResponse,
    summary="Get active embedding configuration for a project (no auth)",
)
async def get_active_config(
    project_id: UUID,
    db: AsyncSession = Depends(get_db_session_dependency),
):
    result = await db.execute(
        select(EmbeddingConfig).where(
            EmbeddingConfig.project_id == project_id,
            EmbeddingConfig.is_active.is_(True),
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Active embedding configuration not found for project")
    return EmbeddingConfigResponse.model_validate(rec)

