"""Internal API endpoints for platform management.

These endpoints are called by tgo-api to notify tgo-platform about platform changes.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/internal", tags=["internal"])


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
