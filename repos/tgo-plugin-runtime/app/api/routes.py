"""Plugin API endpoints."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.services.plugin_manager import plugin_manager
from app.services.installer import installer
from app.services.process_manager import process_manager
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
    ToolExecuteRequest,
    ToolExecuteResponse,
    InstalledPluginInfo,
    InstalledPluginListResponse,
)
from app.schemas.install import (
    PluginInstallRequest,
    PluginLifecycleResponse,
    PluginLogResponse,
    PluginFetchRequest,
    PluginFetchResponse,
)
from app.core.database import AsyncSessionLocal
from app.models.plugin import InstalledPlugin
from app.services.url_resolver import PluginURLResolver
from sqlalchemy import select

logger = get_logger("api.routes")
router = APIRouter()


# ==================== Plugin List ====================

@router.get("/plugins", response_model=PluginListResponse)
async def list_plugins(project_id: Optional[str] = None) -> PluginListResponse:
    """
    Get all registered plugins.
    
    Returns a list of all currently connected plugins with their capabilities.
    If project_id is provided, only returns global plugins and plugins for that project.
    """
    plugins = plugin_manager.get_all_plugins(project_id=project_id)
    return PluginListResponse(plugins=plugins, total=len(plugins))


@router.get("/plugins/installed", response_model=InstalledPluginListResponse)
async def list_installed_plugins(project_id: Optional[str] = None) -> InstalledPluginListResponse:
    """
    Get all installed plugins from database, plus active dev plugins.
    """
    infos = []
    
    # 1. Get from DB
    async with AsyncSessionLocal() as session:
        stmt = select(InstalledPlugin)
        if project_id:
            stmt = stmt.where(InstalledPlugin.project_id == project_id)
        
        result = await session.execute(stmt)
        db_plugins = result.scalars().all()
        
        for p in db_plugins:
            # Use process manager to get real-time status if available
            status_info = process_manager.get_status(p.plugin_id)
            status = status_info.get("status", p.status)
            pid = status_info.get("pid", p.pid)
            
            # Get capabilities if plugin is connected
            active_plugin = plugin_manager.get_plugin(p.plugin_id)
            capabilities = active_plugin.capabilities if active_plugin else []
            
            infos.append(InstalledPluginInfo(
                id=p.id,
                plugin_id=p.plugin_id,
                name=p.name,
                version=p.version,
                description=p.description,
                author=p.author,
                status=status,
                install_type=p.install_type,
                installed_at=p.installed_at,
                updated_at=p.updated_at,
                pid=pid,
                last_error=p.last_error,
                is_dev_mode=False,
                capabilities=capabilities
            ))

    # 2. Add active dev plugins
    active_plugins = list(plugin_manager.plugins.values())
    for ap in active_plugins:
        if ap.is_dev_mode:
            # Check project_id filter
            if project_id and ap.project_id != project_id:
                continue
            
            # Check if this dev plugin is already in the list (unlikely but possible)
            if any(info.plugin_id == ap.id for info in infos):
                continue

            infos.append(InstalledPluginInfo(
                id=None,
                plugin_id=ap.id,
                name=ap.name,
                version=ap.version,
                description=ap.description,
                author=ap.author,
                status="running",
                install_type="dev",
                installed_at=ap.connected_at,
                updated_at=ap.connected_at,
                is_dev_mode=True,
                capabilities=ap.capabilities
            ))
            
    return InstalledPluginListResponse(plugins=infos, total=len(infos))


@router.post("/plugins/fetch-info", response_model=PluginFetchResponse)
async def fetch_plugin_info(request: PluginFetchRequest) -> PluginFetchResponse:
    """
    Fetch plugin information from a URL (GitHub, Gitee, or custom).
    """
    resolver = PluginURLResolver()
    try:
        config = await resolver.resolve(request.url)
        return PluginFetchResponse(**config, source_url=request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch plugin info from {request.url}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error fetching plugin info: {e}")


@router.get("/plugins/{plugin_id}", response_model=PluginInfo)
async def get_plugin(plugin_id: str, project_id: Optional[str] = None) -> PluginInfo:
    """
    Get a specific plugin by ID.
    """
    plugin = plugin_manager.get_plugin(plugin_id, project_id=project_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin not found: {plugin_id}"
        )
    return plugin.to_info()


# ==================== Chat Toolbar ====================

@router.get("/plugins/chat-toolbar/buttons", response_model=ChatToolbarResponse)
async def get_chat_toolbar_buttons(project_id: Optional[str] = None) -> ChatToolbarResponse:
    """
    Get all chat toolbar buttons from registered plugins.
    
    Returns a list of buttons that should be displayed in the chat toolbar.
    """
    buttons = plugin_manager.get_chat_toolbar_buttons(project_id=project_id)
    return ChatToolbarResponse(buttons=buttons)


@router.post("/plugins/chat-toolbar/{plugin_id}/render", response_model=PluginRenderResponse)
async def render_chat_toolbar_plugin(
    plugin_id: str,
    request: PluginRenderRequest,
    project_id: Optional[str] = None,
) -> PluginRenderResponse:
    """
    Render a chat toolbar plugin's content.
    
    Called when user clicks a toolbar button.
    """
    plugin = plugin_manager.get_plugin(plugin_id, project_id=project_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin not found: {plugin_id}"
        )
    
    params = {
        "action_id": request.action_id,
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "visitor": request.visitor.model_dump(exclude_none=True) if request.visitor else None,
        "agent_id": request.agent_id,
        "context": request.context,
        "language": request.language,
    }
    
    result = await plugin_manager.send_request(plugin_id, "chat_toolbar/render", params)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Plugin did not respond in time"
        )
    
    return PluginRenderResponse(**result)


@router.post("/plugins/chat-toolbar/{plugin_id}/event", response_model=PluginActionResponse)
async def send_chat_toolbar_event(
    plugin_id: str,
    request: PluginEventRequest,
    project_id: Optional[str] = None,
) -> PluginActionResponse:
    """
    Send an event to a chat toolbar plugin.
    
    Called when user interacts with the toolbar plugin's UI.
    """
    plugin = plugin_manager.get_plugin(plugin_id, project_id=project_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin not found: {plugin_id}"
        )
    
    params = {
        "event_type": request.event_type,
        "action_id": request.action_id,
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "selected_id": request.selected_id,
        "language": request.language,
        "form_data": request.form_data,
        "payload": request.payload,
    }
    
    result = await plugin_manager.send_request(plugin_id, "chat_toolbar/event", params)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Plugin did not respond in time"
        )
    
    return PluginActionResponse(**result)


# ==================== Visitor Panel ====================

@router.post("/plugins/visitor-panel/render", response_model=VisitorPanelRenderResponse)
async def render_visitor_panels(
    request: VisitorPanelRenderRequest,
    project_id: Optional[str] = None,
) -> VisitorPanelRenderResponse:
    """
    Render all visitor panel plugins for a specific visitor.
    
    Returns a list of rendered panels from all plugins that support visitor_panel.
    """
    panels = await plugin_manager.render_visitor_panels(
        visitor_id=request.visitor_id,
        session_id=request.session_id,
        visitor=request.visitor,
        context=request.context or {},
        language=request.language,
        project_id=project_id,
    )
    return VisitorPanelRenderResponse(panels=panels)


# ==================== Generic Plugin Routes ====================

@router.post("/plugins/{plugin_id}/render", response_model=PluginRenderResponse)
async def render_plugin(
    plugin_id: str, 
    request: PluginRenderRequest,
    project_id: Optional[str] = None,
) -> PluginRenderResponse:
    """
    Trigger a plugin to render its UI.
    
    Sends a render request to the plugin and returns the JSON-UI response.
    """
    plugin = plugin_manager.get_plugin(plugin_id, project_id=project_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin not found: {plugin_id}"
        )
    
    # Determine the render method based on plugin capabilities
    method = "visitor_panel/render"
    for cap in plugin.capabilities:
        if cap.type == "chat_toolbar":
            method = "chat_toolbar/render"
            break
    
    params = {
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "visitor": request.visitor.model_dump(exclude_none=True) if request.visitor else None,
        "agent_id": request.agent_id,
        "action_id": request.action_id,
        "context": request.context,
        "language": request.language,
    }
    
    result = await plugin_manager.send_request(plugin_id, method, params)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Plugin did not respond in time"
        )
    
    return PluginRenderResponse(**result)


@router.post("/plugins/{plugin_id}/event", response_model=PluginActionResponse)
async def send_plugin_event(
    plugin_id: str, 
    request: PluginEventRequest,
    project_id: Optional[str] = None,
) -> PluginActionResponse:
    """
    Send an event to a plugin.
    
    Used when user interacts with plugin UI (button click, form submit, etc.).
    Returns the JSON-ACTION response.
    """
    plugin = plugin_manager.get_plugin(plugin_id, project_id=project_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin not found: {plugin_id}"
        )
    
    # Determine the event method based on plugin capabilities or explicit extension_type
    method = None
    if request.extension_type:
        method = f"{request.extension_type}/event"
    else:
        # Fallback to guessing (backward compatibility)
        method = "visitor_panel/event"
        for cap in plugin.capabilities:
            if cap.type == "chat_toolbar":
                method = "chat_toolbar/event"
                break
    
    params = {
        "event_type": request.event_type,
        "action_id": request.action_id,
        "visitor_id": request.visitor_id,
        "session_id": request.session_id,
        "selected_id": request.selected_id,
        "language": request.language,
        "form_data": request.form_data,
        "payload": request.payload,
    }
    
    result = await plugin_manager.send_request(plugin_id, method, params)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Plugin did not respond in time"
        )
    
    return PluginActionResponse(**result)


# ==================== Tool Execution (MCP) ====================

@router.post("/plugins/tools/execute/{plugin_id}/{tool_name}", response_model=ToolExecuteResponse)
async def execute_plugin_tool(
    plugin_id: str,
    tool_name: str,
    request: ToolExecuteRequest,
    project_id: Optional[str] = None,
) -> ToolExecuteResponse:
    """
    Execute an MCP tool provided by a plugin.
    """
    plugin = plugin_manager.get_plugin(plugin_id, project_id=project_id)
    if not plugin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plugin not found: {plugin_id}"
        )
    
    params = {
        "tool_name": tool_name,
        "arguments": request.arguments,
        "visitor_id": request.context.visitor_id,
        "session_id": request.context.session_id,
        "agent_id": request.context.agent_id,
        "language": request.context.language,
    }
    
    result = await plugin_manager.send_request(plugin_id, "tool/execute", params)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Plugin did not respond in time"
        )
    
    return ToolExecuteResponse(**result)


# ==================== Installation & Lifecycle ====================

@router.post("/plugins/install", response_model=InstalledPluginInfo)
async def install_plugin(request: PluginInstallRequest):
    """
    Install a plugin from GitHub or binary URL.
    """
    async with AsyncSessionLocal() as session:
        # Check if already exists
        stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == request.id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            plugin = existing
            plugin.name = request.name
            plugin.version = request.version
            plugin.description = request.description
            plugin.author = request.author
            plugin.status = "installing"
        else:
            plugin = InstalledPlugin(
                plugin_id=request.id,
                project_id=request.project_id,
                name=request.name,
                version=request.version,
                description=request.description,
                author=request.author,
                install_type="github" if request.source.github else "binary",
                source_config=request.source.model_dump(exclude_none=True),
                build_config=request.build.model_dump(exclude_none=True) if request.build else None,
                runtime_config=request.runtime.model_dump(exclude_none=True),
                status="installing"
            )
            session.add(plugin)
        
        await session.commit()
        await session.refresh(plugin)
        
        try:
            success, message, install_path = await installer.install(request)
            if success:
                plugin.status = "stopped"
                plugin.install_path = install_path
                await session.commit()
                await session.refresh(plugin)
                
                # Auto-start after install
                await process_manager.start_plugin(plugin.plugin_id, request.model_dump())
                
                # Get capabilities if plugin is connected
                active_plugin = plugin_manager.get_plugin(plugin.plugin_id)
                capabilities = active_plugin.capabilities if active_plugin else []
                
                return InstalledPluginInfo(
                    id=plugin.id,
                    plugin_id=plugin.plugin_id,
                    name=plugin.name,
                    version=plugin.version,
                    description=plugin.description,
                    author=plugin.author,
                    status=plugin.status,
                    install_type=plugin.install_type,
                    installed_at=plugin.installed_at,
                    updated_at=plugin.updated_at,
                    pid=plugin.pid,
                    last_error=plugin.last_error,
                    is_dev_mode=False,
                    capabilities=capabilities
                )
            else:
                plugin.status = "error"
                plugin.last_error = message
                await session.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed during installation of {request.id}: {e}")
            plugin.status = "error"
            plugin.last_error = str(e)
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )


@router.delete("/plugins/{plugin_id}/uninstall", response_model=Dict[str, Any])
async def uninstall_plugin(plugin_id: str, project_id: Optional[str] = None):
    """
    Uninstall a plugin.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == plugin_id)
        if project_id:
            stmt = stmt.where(InstalledPlugin.project_id == project_id)
        
        result = await session.execute(stmt)
        plugin = result.scalar_one_or_none()
        
        if not plugin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin {plugin_id} not found in database for this project"
            )
        
        # Stop process
        await process_manager.stop_plugin(plugin_id)
        
        # Remove files
        await installer.uninstall(plugin_id)
        
        # Remove from DB
        await session.delete(plugin)
        await session.commit()
        
        return {"success": True, "message": "Plugin uninstalled"}


@router.post("/plugins/{plugin_id}/start", response_model=PluginLifecycleResponse)
async def start_plugin(
    plugin_id: str, 
    request: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None
):
    """
    Start a plugin process.
    """
    config = None
    # If a full config is provided in the request body, use it
    if request and "id" in request and "source" in request:
        config = request
    else:
        # Fetch from DB
        async with AsyncSessionLocal() as session:
            stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == plugin_id)
            if project_id:
                stmt = stmt.where(InstalledPlugin.project_id == project_id)
                
            result = await session.execute(stmt)
            plugin = result.scalar_one_or_none()
            if not plugin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Plugin {plugin_id} not found in database for this project"
                )
            config = {
                "id": plugin.plugin_id,
                "project_id": str(plugin.project_id),
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
                "source": plugin.source_config,
                "build": plugin.build_config,
                "runtime": plugin.runtime_config
            }
            
    success, message = await process_manager.start_plugin(plugin_id, config)
    status_info = process_manager.get_status(plugin_id)
    
    return PluginLifecycleResponse(
        success=success,
        message=message,
        status=status_info.get("status"),
        pid=status_info.get("pid")
    )


@router.post("/plugins/{plugin_id}/stop", response_model=PluginLifecycleResponse)
async def stop_plugin(plugin_id: str, project_id: Optional[str] = None):
    """
    Stop a plugin process.
    """
    # Verify ownership
    async with AsyncSessionLocal() as session:
        stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == plugin_id)
        if project_id:
            stmt = stmt.where(InstalledPlugin.project_id == project_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plugin not found for this project")

    success = await process_manager.stop_plugin(plugin_id)
    status_info = process_manager.get_status(plugin_id)
    
    return PluginLifecycleResponse(
        success=success,
        message="Stopped" if success else "Failed to stop",
        status=status_info.get("status"),
        pid=None
    )


@router.post("/plugins/{plugin_id}/restart", response_model=PluginLifecycleResponse)
async def restart_plugin(plugin_id: str, project_id: Optional[str] = None):
    """
    Restart a plugin process.
    """
    # Verify ownership
    async with AsyncSessionLocal() as session:
        stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == plugin_id)
        if project_id:
            stmt = stmt.where(InstalledPlugin.project_id == project_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plugin not found for this project")

    success, message = await process_manager.restart_plugin(plugin_id)
    status_info = process_manager.get_status(plugin_id)
    
    return PluginLifecycleResponse(
        success=success,
        message=message,
        status=status_info.get("status"),
        pid=status_info.get("pid")
    )


@router.get("/plugins/{plugin_id}/logs", response_model=PluginLogResponse)
async def get_plugin_logs(plugin_id: str, project_id: Optional[str] = None):
    """
    Get plugin logs.
    """
    # Verify ownership
    async with AsyncSessionLocal() as session:
        stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == plugin_id)
        if project_id:
            stmt = stmt.where(InstalledPlugin.project_id == project_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plugin not found for this project")

    logs = process_manager.get_logs(plugin_id)
    return PluginLogResponse(plugin_id=plugin_id, logs=logs)


@router.get("/plugins/{plugin_id}/status", response_model=Dict[str, Any])
async def get_plugin_status(plugin_id: str, project_id: Optional[str] = None):
    """
    Get detailed plugin status.
    """
    # Verify ownership
    async with AsyncSessionLocal() as session:
        stmt = select(InstalledPlugin).where(InstalledPlugin.plugin_id == plugin_id)
        if project_id:
            stmt = stmt.where(InstalledPlugin.project_id == project_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plugin not found for this project")

    return process_manager.get_status(plugin_id)

