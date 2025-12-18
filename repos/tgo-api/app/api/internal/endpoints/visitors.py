"""Internal visitor management endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_user_language, UserLanguage
from app.models import Visitor
from app.schemas.visitor import VisitorResponse, set_visitor_display_nickname
from app.api.v1.endpoints.channels import _build_enriched_visitor_payload, _get_visitor_with_relations

router = APIRouter()


@router.get(
    "/{visitor_id}",
    response_model=VisitorResponse,
    summary="Get enriched visitor information",
    description="Retrieve comprehensive visitor data including basic info, tags, system info, and latest 10 activities.",
)
async def get_internal_visitor_info(
    visitor_id: UUID,
    project_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """
    Retrieve enriched visitor information for internal services.
    
    This endpoint is designed for internal service communication and does not require JWT authentication.
    It requires a project_id for scoping.
    """
    # 1) Get visitor with all relations pre-loaded
    visitor = _get_visitor_with_relations(db, visitor_id, project_id)
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )

    # 2) Build enriched payload (tags, system info, recent activities, etc.)
    accept_language = request.headers.get("Accept-Language")
    visitor_payload = _build_enriched_visitor_payload(
        visitor=visitor,
        db=db,
        project_id=project_id,
        accept_language=accept_language,
        user_language=user_language,
    )

    # 3) Set display nickname based on language
    set_visitor_display_nickname(visitor_payload, user_language)

    return visitor_payload
