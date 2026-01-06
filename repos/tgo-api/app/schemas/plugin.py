"""Pydantic schemas for Plugin system."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class PluginCapability(BaseModel):
    """Plugin capability declaration."""
    type: str = Field(..., description="Extension point type: visitor_panel, chat_toolbar, sidebar_iframe, channel_integration, mcp_tools")
    title: str = Field(..., description="Display title")
    icon: Optional[str] = Field(None, description="Icon name (Lucide)")
    priority: int = Field(10, description="Display priority (lower = higher priority)")
    tooltip: Optional[str] = Field(None, description="Tooltip text")
    shortcut: Optional[str] = Field(None, description="Keyboard shortcut")
    url: Optional[str] = Field(None, description="URL for iframe plugins")
    width: Optional[int] = Field(None, description="Width for iframe plugins")
    tools: Optional[List["MCPToolDefinition"]] = Field(None, description="Tool definitions for mcp_tools type")


class MCPToolParameter(BaseModel):
    """MCP tool parameter definition."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type: string, number, boolean, enum")
    description: Optional[str] = Field(None, description="Parameter description")
    required: bool = Field(False, description="Whether parameter is required")
    enum_values: Optional[List[str]] = Field(None, description="Enum values if type is enum")


class MCPToolDefinition(BaseModel):
    """MCP tool definition."""
    name: str = Field(..., description="Tool name (identifier)")
    title: str = Field(..., description="Display title")
    description: Optional[str] = Field(None, description="Tool description")
    parameters: Optional[List[MCPToolParameter]] = Field(default_factory=list, description="Tool parameters")


# Update forward reference
PluginCapability.model_rebuild()


class VisitorInfo(BaseModel):
    """Basic visitor information provided to plugins."""
    id: str
    platform_open_id: Optional[str] = Field(None, description="Visitor unique identifier on the platform")
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
    is_dev_mode: bool = False


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


class PluginFetchRequest(BaseModel):
    """Request to fetch plugin info from a URL."""
    url: str = Field(..., description="Plugin URL (GitHub, Gitee, or custom)")


class PluginFetchResponse(BaseModel):
    """Information fetched from a plugin's YAML configuration."""
    id: str
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    source: Dict[str, Any]
    build: Optional[Dict[str, Any]] = None
    runtime: Optional[Dict[str, Any]] = None
    source_url: str


class ToolExecuteContext(BaseModel):
    """Context for tool execution."""
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    language: Optional[str] = None


class ToolExecuteRequest(BaseModel):
    """Request to execute a plugin tool."""
    arguments: Dict[str, Any] = Field(..., description="Tool arguments")
    context: ToolExecuteContext = Field(..., description="Execution context")


class ToolExecuteResponse(BaseModel):
    """Response from plugin tool execution."""
    success: bool = Field(True, description="Whether execution was successful")
    content: str = Field("", description="Text content to return to AI")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured data returned by the tool")
    error: Optional[str] = Field(None, description="Error message if success is False")


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


# ==================== Installation Schemas ====================

class PluginSourceGithub(BaseModel):
    """GitHub source configuration."""
    repo: str = Field(..., description="GitHub repository (e.g., tgoai/tgo-plugin-ticket)")
    ref: str = Field("main", description="Branch, tag, or commit hash")
    path: str = Field("/", description="Path to plugin source in repo")


class PluginSourceBinary(BaseModel):
    """Binary source configuration."""
    url: str = Field(..., description="URL to download binary. Supports ${os} and ${arch}")


class PluginSourceConfig(BaseModel):
    """Source configuration."""
    github: Optional[PluginSourceGithub] = None
    binary: Optional[PluginSourceBinary] = None


class PluginBuildGo(BaseModel):
    """Go build configuration."""
    main: str = Field("./cmd/plugin", description="Path to main file")
    output: str = Field("plugin", description="Output binary name")


class PluginBuildPython(BaseModel):
    """Python build configuration."""
    entrypoint: str = Field("main.py", description="Entrypoint script")
    requirements: str = Field("requirements.txt", description="Requirements file")


class PluginBuildNodeJS(BaseModel):
    """Node.js build configuration."""
    entrypoint: str = Field("index.js", description="Entrypoint script")
    package: str = Field("package.json", description="Package file")


class PluginBuildConfig(BaseModel):
    """Build configuration."""
    language: str = Field(..., description="go | python | nodejs")
    go: Optional[PluginBuildGo] = None
    python: Optional[PluginBuildPython] = None
    nodejs: Optional[PluginBuildNodeJS] = None


class PluginRuntimeConfig(BaseModel):
    """Runtime configuration."""
    args: List[str] = Field(default_factory=list, description="Command line arguments")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    auto_restart: bool = Field(True, description="Auto restart on crash")
    restart_delay: int = Field(5, description="Restart delay in seconds")


class PluginInstallRequest(BaseModel):
    """Request to install a plugin via YAML."""
    id: str = Field(..., description="Unique plugin identifier")
    name: str = Field(..., description="Display name")
    version: str = Field(..., description="Version")
    description: Optional[str] = None
    author: Optional[str] = None
    homepage: Optional[str] = None
    license: Optional[str] = None
    source: PluginSourceConfig = Field(..., description="Source configuration")
    build: Optional[PluginBuildConfig] = None
    runtime: PluginRuntimeConfig = Field(default_factory=PluginRuntimeConfig)


class InstalledPluginInfo(BaseModel):
    """Information about an installed plugin."""
    id: Optional[UUID] = None
    plugin_id: str
    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None
    status: str
    install_type: Optional[str] = None
    installed_at: datetime
    updated_at: datetime
    pid: Optional[int] = None
    last_error: Optional[str] = None
    is_dev_mode: bool = False
    capabilities: List[PluginCapability] = Field(default_factory=list)


class InstalledPluginListResponse(BaseModel):
    """Response for installed plugin list endpoint."""
    plugins: List[InstalledPluginInfo]
    total: int


class DevTokenRequest(BaseModel):
    """Request to generate a dev token."""
    project_id: UUID = Field(..., description="Project ID to associate with the plugin")
    expires_hours: int = Field(24, description="Token expiration in hours")


class DevTokenResponse(BaseModel):
    """Response containing the generated dev token."""
    token: str
    expires_at: datetime

