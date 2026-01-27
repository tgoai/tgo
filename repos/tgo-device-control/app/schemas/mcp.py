"""MCP-related Pydantic schemas."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MCPToolParameter(BaseModel):
    """Schema for a tool parameter."""

    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None


class MCPToolDefinition(BaseModel):
    """Schema for an MCP tool definition."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: Dict[str, Any] = Field(..., description="JSON Schema for inputs")


class MCPToolsListResponse(BaseModel):
    """Response schema for listing MCP tools."""

    tools: List[MCPToolDefinition]


class MCPToolCallRequest(BaseModel):
    """Request schema for calling an MCP tool."""

    name: str = Field(..., description="Tool name to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    project_id: UUID = Field(..., description="Project ID")
    device_id: Optional[UUID] = Field(None, description="Specific device ID to use")


class MCPToolCallResponse(BaseModel):
    """Response schema for MCP tool call."""

    success: bool
    content: Optional[Any] = None
    error: Optional[str] = None


class MCPScreenshotResult(BaseModel):
    """Result schema for screenshot tool."""

    screenshot_url: str
    width: int
    height: int
    timestamp: str


class MCPClickResult(BaseModel):
    """Result schema for click tool."""

    success: bool
    x: int
    y: int
    button: str


class MCPTypeResult(BaseModel):
    """Result schema for type tool."""

    success: bool
    text: str
    characters_typed: int


class MCPScrollResult(BaseModel):
    """Result schema for scroll tool."""

    success: bool
    direction: str
    amount: int


class MCPScreenSizeResult(BaseModel):
    """Result schema for screen size tool."""

    width: int
    height: int
