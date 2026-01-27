"""Status monitoring API endpoints."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.services.session_service import SessionService
from app.services.message_service import MessageService
from app.domain.entities import SessionStatus

router = APIRouter()
logger = logging.getLogger(__name__)


class PlatformStatusResponse(BaseModel):
    """Status response for a platform's vision agent session."""

    platform_id: UUID
    app_type: str
    session_status: str  # active, paused, terminated, not_found
    app_login_status: str  # logged_in, qr_pending, offline
    last_heartbeat: Optional[str] = None
    last_screenshot_at: Optional[str] = None
    message_poll_active: bool
    pending_messages_count: int


class SystemStatusResponse(BaseModel):
    """Overall system status."""

    active_sessions: int
    total_platforms: int
    agentbay_connected: bool
    tgo_api_connected: bool
    database_connected: bool
    redis_connected: bool


@router.get("/status/platform/{platform_id}", response_model=PlatformStatusResponse)
async def get_platform_status(
    platform_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> PlatformStatusResponse:
    """Get status for a specific platform's vision agent session."""
    session_service = SessionService(db)
    message_service = MessageService(db)

    session = await session_service.get_session_by_platform(platform_id)

    if not session:
        return PlatformStatusResponse(
            platform_id=platform_id,
            app_type="unknown",
            session_status="not_found",
            app_login_status="offline",
            last_heartbeat=None,
            last_screenshot_at=None,
            message_poll_active=False,
            pending_messages_count=0,
        )

    pending_count = await message_service.get_pending_messages_count(platform_id)

    return PlatformStatusResponse(
        platform_id=session.platform_id,
        app_type=session.app_type,
        session_status=session.status,
        app_login_status=session.app_login_status,
        last_heartbeat=session.last_heartbeat.isoformat() if session.last_heartbeat else None,
        last_screenshot_at=session.last_screenshot_at.isoformat() if session.last_screenshot_at else None,
        message_poll_active=session.status == SessionStatus.ACTIVE.value,
        pending_messages_count=pending_count,
    )


@router.get("/status/system", response_model=SystemStatusResponse)
async def get_system_status(
    db: AsyncSession = Depends(get_db),
) -> SystemStatusResponse:
    """Get overall system status."""
    session_service = SessionService(db)

    # Get active sessions
    active_sessions = await session_service.list_active_sessions()

    # Check database connectivity (if we got here, it's working)
    database_connected = True

    # TODO: Check AgentBay connectivity
    agentbay_connected = True  # Placeholder

    # TODO: Check tgo-api connectivity
    tgo_api_connected = True  # Placeholder

    # TODO: Check Redis connectivity
    redis_connected = True  # Placeholder

    return SystemStatusResponse(
        active_sessions=len(active_sessions),
        total_platforms=len(active_sessions),  # Same for now
        agentbay_connected=agentbay_connected,
        tgo_api_connected=tgo_api_connected,
        database_connected=database_connected,
        redis_connected=redis_connected,
    )
