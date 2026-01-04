"""Pydantic schemas for Plugin system."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PluginCapability(BaseModel):
    """Plugin capability declaration."""
    type: str = Field(..., description="Extension point type: visitor_panel, chat_toolbar, sidebar_iframe, channel_integration")
    title: str = Field(..., description="Display title")
    icon: Optional[str] = Field(None, description="Icon name (Lucide)")
    priority: int = Field(10, description="Display priority (lower = higher priority)")
    tooltip: Optional[str] = Field(None, description="Tooltip text")
    shortcut: Optional[str] = Field(None, description="Keyboard shortcut")
    url: Optional[str] = Field(None, description="URL for iframe plugins")
    width: Optional[int] = Field(None, description="Width for iframe plugins")


class VisitorInfo(BaseModel):
    """Basic visitor information provided to plugins."""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PluginInfo(BaseModel):
    """Plugin information returned to clients."""
    id: str = Field(..., description="Unique plugin ID")
    name: str = Field(..., description="Plugin name")
    version: str = Field(..., description="Plugin version")
    description: Optional[str] = Field(None, description="Plugin description")
    author: Optional[str] = Field(None, description="Plugin author")
    capabilities: List[PluginCapability] = Field(default_factory=list)
    connected_at: datetime = Field(..., description="Connection timestamp")
    status: str = Field("connected", description="Plugin status: connected, disconnected")


class PluginListResponse(BaseModel):
    """Response for plugin list endpoint."""
    plugins: List[PluginInfo]
    total: int


class PluginRenderRequest(BaseModel):
    """Request to render plugin UI."""
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    visitor: Optional[VisitorInfo] = None
    agent_id: Optional[str] = None
    action_id: Optional[str] = None
    language: Optional[str] = Field(None, description="Language code (e.g., 'zh-CN', 'en-US')")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PluginEventRequest(BaseModel):
    """Request to send event to plugin."""
    event_type: str = Field(..., description="Event type: button_click, item_select, form_submit")
    action_id: str = Field(..., description="Action ID that triggered the event")
    extension_type: Optional[str] = Field(None, description="The extension point type: visitor_panel or chat_toolbar")
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    selected_id: Optional[str] = None
    language: Optional[str] = Field(None, description="Language code (e.g., 'zh-CN', 'en-US')")
    form_data: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PluginRenderResponse(BaseModel):
    """Response from plugin render request (JSON-UI)."""
    template: str = Field(..., description="Template type: key_value, table, card, etc.")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PluginActionResponse(BaseModel):
    """Response from plugin event request (JSON-ACTION)."""
    action: str = Field(..., description="Action type: open_url, insert_text, show_toast, etc.")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class VisitorPanelRenderRequest(BaseModel):
    """Request to render all visitor panel plugins."""
    visitor_id: str
    session_id: Optional[str] = None
    visitor: Optional[VisitorInfo] = None
    language: Optional[str] = Field(None, description="Language code (e.g., 'zh-CN', 'en-US')")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PluginPanelItem(BaseModel):
    """Rendered item for visitor panel."""
    plugin_id: str
    title: str
    icon: Optional[str] = None
    priority: int = 10
    ui: PluginRenderResponse


class VisitorPanelRenderResponse(BaseModel):
    """Response containing all visitor panel plugin renders."""
    panels: List[PluginPanelItem] = Field(default_factory=list)



class ChatToolbarButton(BaseModel):
    """Chat toolbar button info."""
    plugin_id: str
    title: str
    icon: Optional[str] = None
    tooltip: Optional[str] = None
    shortcut: Optional[str] = None


class ChatToolbarResponse(BaseModel):
    """Response for chat toolbar buttons."""
    buttons: List[ChatToolbarButton]

