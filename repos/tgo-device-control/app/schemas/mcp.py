"""MCP-related Pydantic schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPToolDefinition(BaseModel):
    """Schema for an MCP tool definition (from device)."""

    name: str = Field(..., description="Tool name")
    description: Optional[str] = Field(None, description="Tool description")
    inputSchema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        description="JSON Schema for inputs",
    )


class MCPToolsListResponse(BaseModel):
    """Response schema for listing MCP tools."""

    tools: List[MCPToolDefinition]


class MCPToolCallRequest(BaseModel):
    """Request schema for calling an MCP tool (REST helper)."""

    name: str = Field(..., description="Tool name to call")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )


class MCPToolCallResponse(BaseModel):
    """Response schema for MCP tool call."""

    content: Optional[List[Dict[str, Any]]] = None
    isError: bool = False
