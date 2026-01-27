"""Internal API endpoints for platform management.

These endpoints are called by tgo-api to notify tgo-platform about platform changes,
and by tgo-vision-agent to send inbound messages.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.db.models import Platform
from app.domain.entities import NormalizedMessage
from app.domain.services.dispatcher import process_message

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)


class SlackPlatformConfig(BaseModel):
    """Slack platform configuration passed from tgo-api."""
    platform_id: str
    project_id: str
    api_key: Optional[str] = None
    bot_token: str
    app_token: str
    signing_secret: Optional[str] = None


class ReloadResponse(BaseModel):
    success: bool
    message: str


@router.post("/slack/reload", response_model=ReloadResponse)
async def reload_slack_platform(config: SlackPlatformConfig, request: Request):
    """Hot-reload a Slack platform listener.
    
    Called by tgo-api when a Slack platform is enabled or its config is updated.
    tgo-api passes the platform config directly to avoid cross-database queries.
    """
    slack_listener = getattr(request.app.state, "slack_listener", None)
    if not slack_listener:
        raise HTTPException(status_code=503, detail="Slack listener not initialized")
    
    try:
        success = await slack_listener.reload_platform_with_config(
            platform_id=config.platform_id,
            project_id=config.project_id,
            api_key=config.api_key,
            bot_token=config.bot_token,
            app_token=config.app_token,
            signing_secret=config.signing_secret,
        )
        if success:
            return ReloadResponse(success=True, message=f"Slack platform {config.platform_id} reloaded successfully")
        else:
            return ReloadResponse(success=False, message=f"Failed to reload Slack platform {config.platform_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slack/stop/{platform_id}", response_model=ReloadResponse)
async def stop_slack_platform(platform_id: str, request: Request):
    """Stop a Slack platform listener.
    
    Called by tgo-api when a Slack platform is disabled.
    """
    slack_listener = getattr(request.app.state, "slack_listener", None)
    if not slack_listener:
        raise HTTPException(status_code=503, detail="Slack listener not initialized")
    
    try:
        success = await slack_listener.stop_platform(platform_id)
        if success:
            return ReloadResponse(success=True, message=f"Slack platform {platform_id} stopped successfully")
        else:
            return ReloadResponse(success=False, message=f"Platform {platform_id} was not running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Vision Agent Inbound Messages ---

class VisionAgentInboundMessage(BaseModel):
    """Inbound message from tgo-vision-agent."""

    platform_id: str = Field(..., description="Platform ID (UUID string)")
    platform_type: str = Field(..., description="Platform type (e.g., wechat_personal)")
    from_uid: str = Field(..., description="Contact/sender ID")
    content: str = Field(..., description="Message content")
    msg_type: int = Field(default=1, description="Message type: 1=text, 2=image, etc.")
    extra: Optional[dict] = Field(default=None, description="Extra metadata")


class VisionAgentInboundResponse(BaseModel):
    """Response for vision agent inbound message."""

    success: bool
    message: str


@router.post("/vision-agent/inbound", response_model=VisionAgentInboundResponse)
async def vision_agent_inbound(
    msg: VisionAgentInboundMessage,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive an inbound message from tgo-vision-agent.

    Called by tgo-vision-agent when a new message is detected via UI automation.
    This endpoint processes the message through the normal AI pipeline.
    """
    try:
        # Validate platform_id format
        try:
            platform_uuid = UUID(msg.platform_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid platform_id format")

        # Look up platform to get API key
        platform = await db.scalar(
            select(Platform).where(
                Platform.id == platform_uuid,
                Platform.is_active.is_(True),
            )
        )
        if not platform:
            raise HTTPException(status_code=404, detail="Platform not found or inactive")

        if not platform.api_key:
            raise HTTPException(status_code=400, detail="Platform has no API key configured")

        # Build normalized message
        extra = msg.extra or {}
        extra["source"] = "vision_agent"

        normalized = NormalizedMessage(
            platform_id=platform_uuid,
            platform_type=msg.platform_type,
            platform_api_key=platform.api_key,
            from_uid=msg.from_uid,
            content=msg.content,
            extra=extra,
        )

        # Process through AI pipeline
        tgo_api_client = request.app.state.tgo_api_client
        sse_manager = request.app.state.sse_manager

        await process_message(normalized, db, tgo_api_client, sse_manager)

        logger.info(
            f"Vision agent inbound message processed: platform={msg.platform_id}, "
            f"from={msg.from_uid}"
        )

        return VisionAgentInboundResponse(
            success=True,
            message="Message processed successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process vision agent inbound message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
