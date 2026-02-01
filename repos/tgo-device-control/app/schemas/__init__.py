"""Pydantic schemas for TGO Device Control Service."""

from app.schemas.device import (
    DeviceResponse,
    DeviceListResponse,
    DeviceCreateRequest,
    DeviceUpdateRequest,
    BindCodeResponse,
)
from app.schemas.mcp import (
    MCPToolDefinition,
    MCPToolsListResponse,
    MCPToolCallRequest,
    MCPToolCallResponse,
)
from app.schemas.agentos import (
    AgentRunEventType,
    ActionInfo,
    AgentRunEvent,
    AgentRunRequest,
    AgentConfig,
    AgentRunResponse,
    AgentListResponse,
    CancelRunRequest,
    CancelRunResponse,
    ToolInfo,
)

__all__ = [
    # Device schemas
    "DeviceResponse",
    "DeviceListResponse",
    "DeviceCreateRequest",
    "DeviceUpdateRequest",
    "BindCodeResponse",
    # MCP schemas
    "MCPToolDefinition",
    "MCPToolsListResponse",
    "MCPToolCallRequest",
    "MCPToolCallResponse",
    # AgentOS schemas
    "AgentRunEventType",
    "ActionInfo",
    "AgentRunEvent",
    "AgentRunRequest",
    "AgentConfig",
    "AgentRunResponse",
    "AgentListResponse",
    "CancelRunRequest",
    "CancelRunResponse",
    "ToolInfo",
]
