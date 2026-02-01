"""TCP JSON-RPC protocol schemas for Peekaboo device connections.

This module defines Pydantic models for the JSON-RPC 2.0 protocol
used to communicate with Peekaboo agents over TCP.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# =============================================================================
# Device Info and Authentication (Bind Code / Device Token)
# =============================================================================


class DeviceInfo(BaseModel):
    """Information about the connecting device."""

    name: str = Field(..., description="Device name")
    version: str = Field(..., description="Client version")
    os: Optional[str] = Field(
        default=None,
        description="Operating system name (required for first-time registration)",
    )
    osVersion: Optional[str] = Field(default=None, description="Operating system version")
    screenResolution: Optional[str] = Field(
        default=None, description="Screen resolution (e.g., '1920x1080')"
    )


class AuthParams(BaseModel):
    """Parameters for the auth request.

    Either bindCode or deviceToken must be provided, but not both.
    - bindCode: For first-time device registration
    - deviceToken: For reconnection of registered devices
    """

    bindCode: Optional[str] = Field(
        default=None, description="6-character bind code for first-time registration"
    )
    deviceToken: Optional[str] = Field(
        default=None, description="Device token for reconnection"
    )
    deviceInfo: DeviceInfo = Field(..., description="Device information")


class AuthResult(BaseModel):
    """Result of a successful auth request."""

    status: str = Field(default="ok", description="Status of authentication")
    deviceId: str = Field(..., description="Device UUID for subsequent operations")
    deviceToken: Optional[str] = Field(
        default=None,
        description="Device token (only returned on first-time registration, device must save this)",
    )
    projectId: str = Field(..., description="Project ID the device belongs to")
    message: str = Field(
        default="Authentication successful", description="Human-readable status message"
    )


# =============================================================================
# Legacy Agent Info (kept for backward compatibility)
# =============================================================================


class AgentInfo(BaseModel):
    """Information about the connected Peekaboo agent (legacy)."""

    name: str = Field(..., description="Agent name")
    version: str = Field(..., description="Agent version")
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of supported capabilities (e.g., tools/call, tools/list, ping)",
    )


class AgentAuthParams(BaseModel):
    """Parameters for the auth request (legacy)."""

    token: str = Field(..., description="Authentication token")
    agentInfo: AgentInfo = Field(..., description="Agent information")


class AgentAuthResult(BaseModel):
    """Result of a successful auth request (legacy)."""

    status: str = Field(default="ok", description="Status of authentication")
    agentId: str = Field(..., description="Assigned agent ID")
    message: str = Field(
        default="Authentication successful", description="Status message"
    )


class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Any] = Field(default=None, description="Additional error data")


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request message."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="Method parameters"
    )
    id: Optional[Union[int, str]] = Field(
        default=None, description="Request ID (None for notifications)"
    )


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response message."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Optional[Union[int, str]] = Field(default=None, description="Request ID")
    result: Optional[Any] = Field(default=None, description="Result on success")
    error: Optional[JsonRpcError] = Field(default=None, description="Error on failure")


class ToolInputSchema(BaseModel):
    """JSON Schema for tool input parameters."""

    type: str = Field(default="object", description="Schema type")
    properties: Dict[str, Any] = Field(
        default_factory=dict, description="Property definitions"
    )
    required: List[str] = Field(
        default_factory=list, description="Required properties"
    )


class ToolDefinition(BaseModel):
    """Definition of an available tool from the device."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: ToolInputSchema = Field(..., description="Input parameter schema")


class ToolsListResult(BaseModel):
    """Result of a tools/list request."""

    tools: List[ToolDefinition] = Field(..., description="List of available tools")


class ToolCallParams(BaseModel):
    """Parameters for a tools/call request."""

    name: str = Field(..., description="Tool name to call")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments"
    )


class ToolCallContentItem(BaseModel):
    """Content item in a tool call response."""

    type: str = Field(..., description="Content type: 'text' or 'image'")
    text: Optional[str] = Field(default=None, description="Text content")
    data: Optional[str] = Field(default=None, description="Base64 encoded image data")
    mimeType: Optional[str] = Field(default=None, description="MIME type for images")


class ToolCallResult(BaseModel):
    """Result of a tools/call request."""

    content: List[ToolCallContentItem] = Field(..., description="Response content")
    isError: bool = Field(default=False, description="Whether the call resulted in error")


class PingResult(BaseModel):
    """Result of a ping request."""

    pong: bool = Field(default=True, description="Pong flag")
    timestamp: int = Field(..., description="Unix timestamp")


# JSON-RPC 2.0 Error Codes
class JsonRpcErrorCode:
    """Standard JSON-RPC 2.0 error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Custom error codes
    AUTH_FAILED = -32001
    TOOL_NOT_FOUND = -32002
    TOOL_EXECUTION_FAILED = -32003
    CONNECTION_CLOSED = -32004
