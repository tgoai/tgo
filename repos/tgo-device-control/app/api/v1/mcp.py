"""MCP REST API endpoints for debugging and non-MCP clients.

The primary MCP Streamable HTTP endpoint is at ``POST /mcp/{device_id}``
(defined in ``main.py``). These REST endpoints provide a convenient
alternative for manual testing and debugging.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.services.mcp_server import mcp_proxy
from app.services.tcp_connection_manager import tcp_connection_manager

router = APIRouter()
logger = get_logger(__name__)


@router.get("/tools/{device_id}")
async def list_device_tools(device_id: str):
    """List available MCP tools from a specific device (REST helper).

    This fetches tools directly from the connected device via TCP RPC.
    """
    connection = tcp_connection_manager.get_connection(device_id)
    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} is not connected",
        )

    result = await mcp_proxy.handle_list_tools(device_id)
    return result


@router.post("/tools/{device_id}/call")
async def call_device_tool(
    device_id: str,
    name: str,
    arguments: Dict[str, Any] = {},
):
    """Call a tool on a specific device (REST helper).

    This forwards the tool call directly to the connected device via TCP RPC.
    No name mapping or argument transformation is performed.
    """
    connection = tcp_connection_manager.get_connection(device_id)
    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} is not connected",
        )

    params = {"name": name, "arguments": arguments}
    result = await mcp_proxy.handle_call_tool(device_id, params)
    return result
