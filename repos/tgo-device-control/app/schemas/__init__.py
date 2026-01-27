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
    "DeviceResponse",
    "DeviceListResponse",
    "DeviceCreateRequest",
    "DeviceUpdateRequest",
    "BindCodeResponse",
    "MCPToolDefinition",
    "MCPToolsListResponse",
    "MCPToolCallRequest",
    "MCPToolCallResponse",
]
