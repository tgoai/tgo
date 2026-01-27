"""Screenshot and debugging API endpoints."""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.services.session_service import SessionService

router = APIRouter()
logger = logging.getLogger(__name__)


class ScreenshotResponse(BaseModel):
    """Response body for screenshot operations."""

    session_id: UUID
    screenshot_id: str
    timestamp: str
    width: int
    height: int
    base64_image: Optional[str] = None  # Only if requested


class ScreenshotListResponse(BaseModel):
    """Response body for listing screenshots."""

    screenshots: list[ScreenshotResponse]
    total: int


@router.get("/screenshots/{session_id}/current")
async def get_current_screenshot(
    session_id: UUID,
    include_base64: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ScreenshotResponse:
    """Take and return a current screenshot of the session.

    This is useful for debugging and monitoring.
    """
    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        from app.core.agentbay_client import AgentBayClientFactory
        from app.core.encryption import decrypt_api_key
        from app.core.config import settings

        # Get controller
        config = session.config or {}
        encrypted_key = config.get("agentbay_api_key")
        api_key = decrypt_api_key(encrypted_key) if encrypted_key else settings.agentbay_api_key
        
        controller = AgentBayClientFactory.create_controller(
            environment_type=session.environment_type,
            api_key=api_key,
        )

        screenshot = await controller.take_screenshot(
            session.agentbay_session_id
        )

        # Generate screenshot ID and timestamp
        screenshot_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()

        # Estimate dimensions (PNG header parsing would be needed for accurate values)
        width = 1080  # Default mobile width
        height = 2340  # Default mobile height

        return ScreenshotResponse(
            session_id=session_id,
            screenshot_id=screenshot_id,
            timestamp=timestamp,
            width=width,
            height=height,
            base64_image=base64.b64encode(screenshot).decode("utf-8") if include_base64 else None,
        )
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to take screenshot: {e}")


@router.get("/screenshots/{session_id}/current/image")
async def get_current_screenshot_image(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Take and return a current screenshot as PNG image."""
    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        from app.core.agentbay_client import AgentBayClientFactory
        from app.core.encryption import decrypt_api_key
        from app.core.config import settings

        # Get controller
        config = session.config or {}
        encrypted_key = config.get("agentbay_api_key")
        api_key = decrypt_api_key(encrypted_key) if encrypted_key else settings.agentbay_api_key
        
        controller = AgentBayClientFactory.create_controller(
            environment_type=session.environment_type,
            api_key=api_key,
        )

        screenshot = await controller.take_screenshot(
            session.agentbay_session_id
        )

        return Response(
            content=screenshot,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename=screenshot-{session_id}.png"
            },
        )
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to take screenshot: {e}")


@router.get("/screenshots/{session_id}/history", response_model=ScreenshotListResponse)
async def list_screenshots(
    session_id: UUID,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> ScreenshotListResponse:
    """List recent screenshots for a session.

    Note: Screenshot history is not currently stored. This endpoint
    returns an empty list. Future versions may store screenshots
    for debugging and auditing purposes.
    """
    service = SessionService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Screenshot history not implemented yet
    return ScreenshotListResponse(
        screenshots=[],
        total=0,
    )


@router.get("/screenshots/{session_id}/{screenshot_id}/image")
async def get_screenshot_image(
    session_id: UUID,
    screenshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Get a specific screenshot as PNG image.

    Note: Screenshot storage is not currently implemented.
    This endpoint will return 404 for any screenshot_id.
    """
    raise HTTPException(
        status_code=404,
        detail="Screenshot storage not implemented. Use /current/image for live screenshots.",
    )
