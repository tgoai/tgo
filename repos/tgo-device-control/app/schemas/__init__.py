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
]
