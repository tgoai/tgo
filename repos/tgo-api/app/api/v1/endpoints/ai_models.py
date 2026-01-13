"""AI Model management endpoints."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models import AIModel, AIProvider, Staff
from app.schemas.ai_model import AIModelWithProvider, AIModelWithProviderListResponse

router = APIRouter()


@router.get("", response_model=AIModelWithProviderListResponse)
async def list_ai_models(
    model_type: Optional[str] = Query(None, pattern="^(chat|embedding)$"),
    is_active: Optional[bool] = Query(True),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> Any:
    """List AI models with provider info.
    
    This endpoint returns a flat list of models available in the current project,
    joined with their respective provider information.
    """
    project_id = current_user.project_id

    # Base query: join AIModel with AIProvider to filter by project_id and active status
    stmt = (
        select(AIModel, AIProvider)
        .join(AIProvider, AIModel.provider_id == AIProvider.id)
        .where(
            AIProvider.project_id == project_id,
            AIProvider.is_active == True,
            AIProvider.deleted_at.is_(None),
            AIModel.deleted_at.is_(None),
        )
    )

    if model_type:
        stmt = stmt.where(AIModel.model_type == model_type)
    
    if is_active is not None:
        stmt = stmt.where(AIModel.is_active == is_active)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Ordered list
    stmt = stmt.order_by(AIProvider.name.asc(), AIModel.model_name.asc())
    stmt = stmt.offset(offset).limit(limit)
    
    results = db.execute(stmt).all()

    data = []
    for model, provider in results:
        # Explicitly build dict to avoid any implicit ORM attribute access during serialization
        item = AIModelWithProvider(
            id=model.id,
            model_id=model.model_id,
            model_name=model.model_name,
            model_type=model.model_type,
            provider_id=provider.id,
            provider_name=provider.name,
            provider_kind=provider.provider,
            description=model.description,
            context_window=model.context_window,
            is_active=model.is_active,
        )
        data.append(item)

    # Return as dict to be handled by FastAPI's jsonable_encoder
    return AIModelWithProviderListResponse(
        data=data,
        pagination={
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
            "has_prev": offset > 0,
        },
    )
