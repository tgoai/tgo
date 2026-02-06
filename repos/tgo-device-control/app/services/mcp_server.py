"""MCP Server - Pure transparent proxy for device tools.

This module implements the MCP Streamable HTTP protocol as a transparent
proxy to connected devices. It does NOT define any static tools, nor
perform any tool name mapping or argument transformation. All tool
definitions come from the devices themselves via TCP RPC ``tools/list``,
and all tool calls are forwarded as-is via ``tools/call``.

The ``device_id`` is resolved from the URL path (``/mcp/{device_id}``).
"""

from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging import get_logger
from app.services.tcp_connection_manager import tcp_connection_manager

logger = get_logger("services.mcp_server")


class MCPProxy:
    """Transparent MCP proxy that forwards all requests to connected devices.

    No static tool definitions, no name mapping, no argument transformation.
    """

    # ------------------------------------------------------------------ #
    #  MCP protocol handlers                                              #
    # ------------------------------------------------------------------ #

    def handle_initialize(self) -> Dict[str, Any]:
        """Handle MCP ``initialize`` method."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "tgo-device-control",
                "version": settings.SERVICE_VERSION,
            },
        }

    async def handle_list_tools(self, device_id: str) -> Dict[str, Any]:
        """Fetch tool list from device and return as-is.

        Args:
            device_id: Target device identifier.

        Returns:
            ``{"tools": [...]}`` with raw tool definitions from the device.
        """
        connection = tcp_connection_manager.get_connection(device_id)
        if not connection:
            logger.warning(f"list_tools: device {device_id} not connected")
            return {"tools": []}

        raw_tools = await connection.list_tools()
        return {"tools": raw_tools or []}

    async def handle_call_tool(
        self, device_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Forward tool call to device as-is (no mapping, no transformation).

        Args:
            device_id: Target device identifier.
            params: MCP ``tools/call`` params containing ``name`` and ``arguments``.

        Returns:
            Raw tool call result from the device.
        """
        name: str = params.get("name", "")
        arguments: Dict[str, Any] = params.get("arguments", {})

        connection = tcp_connection_manager.get_connection(device_id)
        if not connection:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Device {device_id} is not connected",
                    }
                ],
                "isError": True,
            }

        result = await connection.call_tool(name, arguments)
        if result is None:
            return {
                "content": [
                    {"type": "text", "text": "Error: Device request timed out"}
                ],
                "isError": True,
            }

        # Return result from device as-is (already in MCP content format)
        return result

    # ------------------------------------------------------------------ #
    #  Unified JSON-RPC dispatcher                                        #
    # ------------------------------------------------------------------ #

    async def handle_jsonrpc(
        self, device_id: str, body: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Dispatch a JSON-RPC 2.0 request to the appropriate handler.

        Args:
            device_id: Target device identifier (from URL path).
            body: Parsed JSON-RPC request body.

        Returns:
            JSON-RPC response dict, or ``None`` for notifications.
        """
        method: str = body.get("method", "")
        params: Dict[str, Any] = body.get("params", {})
        request_id = body.get("id")

        # Notifications (no ``id``) – acknowledge silently
        if request_id is None:
            return None

        result: Dict[str, Any]

        if method == "initialize":
            result = self.handle_initialize()
        elif method == "tools/list":
            result = await self.handle_list_tools(device_id)
        elif method == "tools/call":
            result = await self.handle_call_tool(device_id, params)
        elif method == "ping":
            result = {}
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }


# Global singleton
mcp_proxy = MCPProxy()
