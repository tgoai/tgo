"""MCP Server - Provides MCP tool interface for AI agents."""

from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging import get_logger
from app.schemas.mcp import MCPToolDefinition
from app.services.device_manager import device_manager

logger = get_logger("services.mcp_server")


# Tool definitions
COMPUTER_TOOLS = [
    MCPToolDefinition(
        name="computer_screenshot",
        description="Capture a screenshot of the device screen. Returns the screenshot URL.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to capture screenshot from",
                },
                "region": {
                    "type": "object",
                    "description": "Optional region to capture (x, y, width, height)",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                },
            },
            "required": ["device_id"],
        },
    ),
    MCPToolDefinition(
        name="computer_mouse_click",
        description="Perform a mouse click at the specified coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to perform click on",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                    "description": "Mouse button to click",
                },
            },
            "required": ["device_id", "x", "y"],
        },
    ),
    MCPToolDefinition(
        name="computer_mouse_double_click",
        description="Perform a mouse double-click at the specified coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to perform double-click on",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate",
                },
            },
            "required": ["device_id", "x", "y"],
        },
    ),
    MCPToolDefinition(
        name="computer_mouse_move",
        description="Move the mouse cursor to the specified coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate",
                },
            },
            "required": ["device_id", "x", "y"],
        },
    ),
    MCPToolDefinition(
        name="computer_mouse_drag",
        description="Drag the mouse from start to end coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
                "start_x": {
                    "type": "integer",
                    "description": "Start X coordinate",
                },
                "start_y": {
                    "type": "integer",
                    "description": "Start Y coordinate",
                },
                "end_x": {
                    "type": "integer",
                    "description": "End X coordinate",
                },
                "end_y": {
                    "type": "integer",
                    "description": "End Y coordinate",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                    "description": "Mouse button to use for dragging",
                },
            },
            "required": ["device_id", "start_x", "start_y", "end_x", "end_y"],
        },
    ),
    MCPToolDefinition(
        name="computer_keyboard_type",
        description="Type text using the keyboard.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to type on",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["device_id", "text"],
        },
    ),
    MCPToolDefinition(
        name="computer_keyboard_hotkey",
        description="Press a keyboard hotkey combination (e.g., Ctrl+C, Cmd+V).",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keys to press together (e.g., ['ctrl', 'c'])",
                },
            },
            "required": ["device_id", "keys"],
        },
    ),
    MCPToolDefinition(
        name="computer_keyboard_press",
        description="Press a single key.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
                "key": {
                    "type": "string",
                    "description": "Key to press (e.g., 'enter', 'tab', 'escape')",
                },
            },
            "required": ["device_id", "key"],
        },
    ),
    MCPToolDefinition(
        name="computer_scroll",
        description="Scroll at the specified coordinates.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
                "x": {
                    "type": "integer",
                    "description": "X coordinate to scroll at",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate to scroll at",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right"],
                    "description": "Scroll direction",
                },
                "amount": {
                    "type": "integer",
                    "default": 3,
                    "description": "Scroll amount (number of scroll units)",
                },
            },
            "required": ["device_id", "x", "y", "direction"],
        },
    ),
    MCPToolDefinition(
        name="computer_get_screen_size",
        description="Get the screen size of the device.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
            },
            "required": ["device_id"],
        },
    ),
    MCPToolDefinition(
        name="computer_get_cursor_position",
        description="Get the current cursor position.",
        inputSchema={
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID",
                },
            },
            "required": ["device_id"],
        },
    ),
]


class MCPServer:
    """MCP Server implementation for device control tools."""

    def __init__(self):
        self.tools = {tool.name: tool for tool in COMPUTER_TOOLS}

    def get_tool_definitions(
        self,
        project_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> List[MCPToolDefinition]:
        """Get available tool definitions."""
        return list(self.tools.values())

    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize method."""
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

    def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/list method."""
        return {
            "tools": [tool.model_dump() for tool in self.tools.values()],
        }

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP tools/call method."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Unknown tool: {tool_name}",
                    }
                ],
                "isError": True,
            }

        try:
            result = await self.execute_tool(
                tool_name=tool_name,
                arguments=arguments,
                project_id=arguments.get("project_id"),
                device_id=arguments.get("device_id"),
            )
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: {str(e)}",
                    }
                ],
                "isError": True,
            }

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        project_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a tool on a device."""
        # Get device ID from arguments if not provided
        device_id = device_id or arguments.get("device_id")

        if not device_id:
            return {
                "content": [{"type": "text", "text": "Error: device_id is required"}],
                "isError": True,
            }

        # Get device connection
        connection = device_manager.get_device(device_id, project_id)
        if not connection:
            return {
                "content": [
                    {"type": "text", "text": f"Error: Device {device_id} is not connected"}
                ],
                "isError": True,
            }

        # Map tool name to device method
        method_mapping = {
            "computer_screenshot": "screenshot",
            "computer_mouse_click": "mouse_click",
            "computer_mouse_double_click": "mouse_double_click",
            "computer_mouse_move": "mouse_move",
            "computer_mouse_drag": "mouse_drag",
            "computer_keyboard_type": "keyboard_type",
            "computer_keyboard_hotkey": "keyboard_hotkey",
            "computer_keyboard_press": "keyboard_press",
            "computer_scroll": "scroll",
            "computer_get_screen_size": "get_screen_size",
            "computer_get_cursor_position": "get_cursor_position",
        }

        device_method = method_mapping.get(tool_name)
        if not device_method:
            return {
                "content": [{"type": "text", "text": f"Error: Unknown tool {tool_name}"}],
                "isError": True,
            }

        # Remove device_id from arguments (already used)
        tool_args = {k: v for k, v in arguments.items() if k != "device_id"}

        # Send request to device
        result = await connection.send_request(device_method, tool_args)

        if result is None:
            return {
                "content": [{"type": "text", "text": "Error: Device request timed out"}],
                "isError": True,
            }

        # Format result
        if isinstance(result, dict):
            if result.get("error"):
                return {
                    "content": [{"type": "text", "text": f"Error: {result['error']}"}],
                    "isError": True,
                }

            # For screenshot, include image URL
            if tool_name == "computer_screenshot" and result.get("screenshot_url"):
                return {
                    "content": [
                        {
                            "type": "image",
                            "data": result.get("screenshot_base64", ""),
                            "mimeType": "image/png",
                        },
                        {
                            "type": "text",
                            "text": f"Screenshot captured: {result['screenshot_url']}",
                        },
                    ],
                }

            return {
                "content": [{"type": "text", "text": str(result)}],
            }

        return {
            "content": [{"type": "text", "text": str(result)}],
        }
