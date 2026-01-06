"""Plugin API endpoints - Proxies to tgo-plugin-runtime service."""

from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Depends
import httpx
from sqlalchemy.orm import Session
from jose import jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.services.plugin_runtime_client import plugin_runtime_client
from app.models import Visitor, Staff
from app.schemas.plugin import (
    VisitorInfo,
    PluginListResponse,
    PluginInfo,
    PluginRenderRequest,
    PluginEventRequest,
    VisitorPanelRenderRequest,
    VisitorPanelRenderResponse,
    ChatToolbarResponse,
    PluginRenderResponse,
    PluginActionResponse,
    PluginInstallRequest,
    InstalledPluginInfo,
    InstalledPluginListResponse,
    DevTokenRequest,
    DevTokenResponse,
    PluginFetchRequest,
    PluginFetchResponse,
)

logger = get_logger("api.plugins")
router = APIRouter()


def _handle_runtime_error(e: Exception, context: str):
    """Helper to handle errors from plugin runtime service."""
    if isinstance(e, HTTPException):
        raise e
        
    if isinstance(e, httpx.HTTPStatusError):
        if 400 <= e.response.status_code < 500:
            try:
                detail = e.response.json().get("detail", e.response.text)
            except Exception:
                detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        logger.error(f"Plugin runtime service error ({e.response.status_code}) during {context}: {e.response.text}")
        raise HTTPException(status_code=502, detail="Plugin runtime service error")
    
    if isinstance(e, httpx.RequestError):
        logger.error(f"Plugin runtime connection error during {context}: {e}")
        raise HTTPException(status_code=502, detail="Plugin runtime service unavailable")
    
    logger.error(f"Unexpected error during {context}: {e}")
    raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _get_visitor_info(db_visitor: Visitor, language: Optional[str] = None) -> VisitorInfo:
    """Helper to create VisitorInfo with prioritized name logic."""
    name = db_visitor.name
    if not name:
        is_zh = language and language.lower().startswith("zh")
        if is_zh and db_visitor.nickname_zh:
            name = db_visitor.nickname_zh
        else:
            name = db_visitor.nickname or f"Visitor {str(db_visitor.id)[:4]}"

    return VisitorInfo(
        id=str(db_visitor.id),
        platform_open_id=db_visitor.platform_open_id,
        name=name,
        email=db_visitor.email,
        phone=db_visitor.phone_number,
        avatar=db_visitor.avatar_url,
        metadata=db_visitor.custom_attributes or {}
    )


def _enrich_visitor_info(
    request_visitor: Optional[VisitorInfo],
    visitor_id: Optional[str],
    language: Optional[str],
    db: Session
) -> Optional[VisitorInfo]:
    """Enrich visitor info from database if not provided."""
    if request_visitor:
        return request_visitor
    
    if not visitor_id:
        return None
    
    try:
        db_visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
        if db_visitor:
            return _get_visitor_info(db_visitor, language)
    except Exception as e:
        logger.warning(f"Failed to fetch visitor info: {e}")
    
    return None


# ==================== Plugin List ====================

@router.get("", response_model=PluginListResponse)
async def list_plugins(
    current_user: Staff = Depends(get_current_active_user)
) -> PluginListResponse:
    """Get all registered plugins, including global and project-specific ones."""
    try:
        data = await plugin_runtime_client.list_plugins(project_id=str(current_user.project_id))
        return PluginListResponse(**data)
    except Exception as e:
        _handle_runtime_error(e, "list_plugins")


@router.get("/chat-toolbar/buttons", response_model=ChatToolbarResponse)
async def get_chat_toolbar_buttons(
    current_user: Staff = Depends(get_current_active_user)
) -> ChatToolbarResponse:
    """Get all chat toolbar buttons from registered plugins for the current project."""
    try:
        data = await plugin_runtime_client.get_chat_toolbar_buttons(project_id=str(current_user.project_id))
        return ChatToolbarResponse(**data)
    except Exception as e:
        _handle_runtime_error(e, "get_chat_toolbar_buttons")


# ==================== Visitor Panel ====================

@router.post("/visitor-panel/render", response_model=VisitorPanelRenderResponse)
async def render_visitor_panels(
    request: VisitorPanelRenderRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
) -> VisitorPanelRenderResponse:
    """Render all visitor panel plugins for a specific visitor."""
    # Enrich visitor info
    visitor_info = _enrich_visitor_info(
        request.visitor,
        request.visitor_id,
        request.language,
        db
    )
    
    request_data = {
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "visitor": visitor_info.model_dump(exclude_none=True) if visitor_info else None,
        "language": request.language,
        "context": request.context or {},
    }
    
    try:
        data = await plugin_runtime_client.render_visitor_panels(request_data, project_id=str(current_user.project_id))
        return VisitorPanelRenderResponse(**data)
    except Exception as e:
        _handle_runtime_error(e, "render_visitor_panels")


# ==================== Chat Toolbar ====================

@router.post("/chat-toolbar/{plugin_id}/render", response_model=PluginRenderResponse)
async def render_chat_toolbar_plugin(
    plugin_id: str,
    request: PluginRenderRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
) -> PluginRenderResponse:
    """Render a chat toolbar plugin's content."""
    visitor_info = _enrich_visitor_info(
        request.visitor,
        request.visitor_id,
        request.language,
        db
    )
    
    request_data = {
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "visitor": visitor_info.model_dump(exclude_none=True) if visitor_info else None,
        "agent_id": request.agent_id,
        "action_id": request.action_id,
        "language": request.language,
        "context": request.context or {},
    }
    
    try:
        data = await plugin_runtime_client.render_chat_toolbar(
            plugin_id, 
            request_data, 
            project_id=str(current_user.project_id)
        )
        if data is None:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
        return PluginRenderResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_runtime_error(e, "render_chat_toolbar_plugin")


@router.post("/chat-toolbar/{plugin_id}/event", response_model=PluginActionResponse)
async def send_chat_toolbar_event(
    plugin_id: str,
    request: PluginEventRequest,
    current_user: Staff = Depends(get_current_active_user)
) -> PluginActionResponse:
    """Send an event to a chat toolbar plugin."""
    request_data = {
        "event_type": request.event_type,
        "action_id": request.action_id,
        "extension_type": request.extension_type,
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "selected_id": request.selected_id,
        "language": request.language,
        "form_data": request.form_data,
        "payload": request.payload or {},
    }
    
    try:
        data = await plugin_runtime_client.send_chat_toolbar_event(
            plugin_id, 
            request_data, 
            project_id=str(current_user.project_id)
        )
        if data is None:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
        return PluginActionResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_runtime_error(e, "send_chat_toolbar_event")


@router.get("/installed", response_model=InstalledPluginListResponse)
async def list_installed_plugins(
    current_user: Staff = Depends(get_current_active_user)
) -> InstalledPluginListResponse:
    """Get all installed plugins from database via runtime service."""
    try:
        data = await plugin_runtime_client.list_installed_plugins(project_id=str(current_user.project_id))
        return InstalledPluginListResponse(**data)
    except Exception as e:
        _handle_runtime_error(e, "list_installed_plugins")


@router.post("/fetch-info", response_model=PluginFetchResponse)
async def fetch_plugin_info(
    request: PluginFetchRequest,
    current_user: Staff = Depends(get_current_active_user)
) -> PluginFetchResponse:
    """Fetch plugin information from a URL (GitHub, Gitee, or custom)."""
    try:
        data = await plugin_runtime_client.fetch_plugin_info(request.url)
        if not data:
            raise HTTPException(status_code=400, detail="Could not fetch plugin information from the provided URL")
        return PluginFetchResponse(**data)
    except Exception as e:
        _handle_runtime_error(e, "fetch_plugin_info")


@router.post("/install", response_model=InstalledPluginInfo)
async def install_plugin(
    request: PluginInstallRequest,
    current_user: Staff = Depends(get_current_active_user)
) -> InstalledPluginInfo:
    """Install a new plugin via runtime service."""
    # Add project_id to request for runtime to store
    request_data = request.model_dump(exclude_none=True)
    request_data["project_id"] = str(current_user.project_id)
    
    try:
        data = await plugin_runtime_client.install_plugin(request_data)
        if data is None:
            raise HTTPException(status_code=500, detail="Installation failed at runtime")
        return InstalledPluginInfo(**data)
    except Exception as e:
        _handle_runtime_error(e, "install_plugin")


# ==================== Generic Plugin Routes ====================

@router.get("/{plugin_id}", response_model=PluginInfo)
async def get_plugin(
    plugin_id: str,
    current_user: Staff = Depends(get_current_active_user)
) -> PluginInfo:
    """Get a specific plugin by ID."""
    try:
        data = await plugin_runtime_client.get_plugin(plugin_id, project_id=str(current_user.project_id))
        if data is None:
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
        return PluginInfo(**data)
    except Exception as e:
        _handle_runtime_error(e, "get_plugin")


@router.delete("/{plugin_id}", response_model=dict)
async def uninstall_plugin(
    plugin_id: str,
    current_user: Staff = Depends(get_current_active_user)
) -> dict:
    """Uninstall a plugin via runtime service."""
    try:
        resp = await plugin_runtime_client.uninstall_plugin(plugin_id, project_id=str(current_user.project_id))
        if resp and resp.get("success"):
            return resp
        raise HTTPException(status_code=400, detail=resp.get("message") if resp else "Uninstallation failed")
    except Exception as e:
        _handle_runtime_error(e, "uninstall_plugin")


@router.post("/{plugin_id}/start", response_model=dict)
async def start_plugin(
    plugin_id: str,
    current_user: Staff = Depends(get_current_active_user)
) -> dict:
    """Start a plugin via runtime service."""
    try:
        # Pass None or empty dict, runtime will fetch config from DB if not provided
        resp = await plugin_runtime_client.start_plugin(plugin_id, None, project_id=str(current_user.project_id))
        if resp and resp.get("success"):
            return resp
        raise HTTPException(status_code=400, detail=resp.get("message") if resp else "Failed to start")
    except Exception as e:
        _handle_runtime_error(e, "start_plugin")


@router.post("/{plugin_id}/stop", response_model=dict)
async def stop_plugin(
    plugin_id: str,
    current_user: Staff = Depends(get_current_active_user)
) -> dict:
    """Stop a plugin via runtime service."""
    try:
        resp = await plugin_runtime_client.stop_plugin(plugin_id, project_id=str(current_user.project_id))
        if resp and resp.get("success"):
            return resp
        raise HTTPException(status_code=400, detail=resp.get("message") if resp else "Failed to stop")
    except Exception as e:
        _handle_runtime_error(e, "stop_plugin")


@router.post("/{plugin_id}/restart", response_model=dict)
async def restart_plugin(
    plugin_id: str,
    current_user: Staff = Depends(get_current_active_user)
) -> dict:
    """Restart a plugin via runtime service."""
    try:
        resp = await plugin_runtime_client.restart_plugin(plugin_id, project_id=str(current_user.project_id))
        if resp and resp.get("success"):
            return resp
        raise HTTPException(status_code=400, detail=resp.get("message") if resp else "Failed to restart")
    except Exception as e:
        _handle_runtime_error(e, "restart_plugin")


@router.get("/{plugin_id}/logs", response_model=dict)
async def get_plugin_logs(
    plugin_id: str,
    current_user: Staff = Depends(get_current_active_user)
) -> dict:
    """Get plugin logs via runtime service."""
    try:
        return await plugin_runtime_client.get_plugin_logs(plugin_id, project_id=str(current_user.project_id))
    except Exception as e:
        _handle_runtime_error(e, "get_plugin_logs")


@router.post("/dev-token", response_model=DevTokenResponse)
async def generate_dev_token(
    request: DevTokenRequest,
    current_user: Staff = Depends(get_current_active_user)
) -> DevTokenResponse:
    """Generate a dev token for plugin debugging in a specific project."""
    # TODO: Verify user has access to project
    
    expires_at = datetime.utcnow() + timedelta(hours=request.expires_hours)
    token_data = {
        "project_id": str(request.project_id),
        "user_id": str(current_user.id),
        "type": "plugin_dev",
        "exp": expires_at
    }
    
    token = jwt.encode(token_data, settings.SECRET_KEY, algorithm="HS256")
    
    return DevTokenResponse(
        token=token,
        expires_at=expires_at
    )
