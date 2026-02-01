"""MCP Server - Provides MCP tool interface for AI agents."""

from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.logging import get_logger
from app.schemas.mcp import MCPToolDefinition
from app.services.tcp_connection_manager import tcp_connection_manager

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
        """Execute a tool on a device.
        
        This method uses the TCP connection manager to call tools directly
        on connected devices via the tools/call protocol.
        """
        # Get device ID from arguments if not provided
        device_id = device_id or arguments.get("device_id")

        if not device_id:
            return {
                "content": [{"type": "text", "text": "Error: device_id is required"}],
                "isError": True,
            }

        # Get device connection
        connection = tcp_connection_manager.get_connection(device_id)
        if not connection:
            return {
                "content": [
                    {"type": "text", "text": f"Error: Device {device_id} is not connected"}
                ],
                "isError": True,
            }

        # Map tool name to device tool name
        tool_mapping = {
            "computer_screenshot": "see",
            "computer_mouse_click": "click",
            "computer_mouse_double_click": "click",
            "computer_mouse_move": "move",
            "computer_mouse_drag": "drag",
            "computer_keyboard_type": "type",
            "computer_keyboard_hotkey": "hotkey",
            "computer_keyboard_press": "type",
            "computer_scroll": "scroll",
            "computer_get_screen_size": "get_screen_size",
            "computer_get_cursor_position": "get_cursor_position",
        }

        device_tool = tool_mapping.get(tool_name)
        if not device_tool:
            return {
                "content": [{"type": "text", "text": f"Error: Unknown tool {tool_name}"}],
                "isError": True,
            }

        # Transform arguments for device tool format
        tool_args = self._transform_arguments(tool_name, arguments)

        # Call tool on device via tools/call
        result = await connection.call_tool(device_tool, tool_args)

        if result is None:
            return {
                "content": [{"type": "text", "text": "Error: Device request timed out"}],
                "isError": True,
            }

        # Return result as-is (already in MCP format from device)
        return result

    def _transform_arguments(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Transform arguments from MCP server format to device tool format."""
        # Remove device_id from arguments (already used)
        args = {k: v for k, v in arguments.items() if k != "device_id"}

        # Special transformations based on tool
        if tool_name == "computer_mouse_click":
            # Convert x,y to coords format
            if "x" in args and "y" in args:
                args["coords"] = f"{args.pop('x')},{args.pop('y')}"
        elif tool_name == "computer_mouse_double_click":
            if "x" in args and "y" in args:
                args["coords"] = f"{args.pop('x')},{args.pop('y')}"
                args["double"] = True
        elif tool_name == "computer_mouse_drag":
            # Convert start/end coords
            if "start_x" in args and "start_y" in args:
                args["from"] = f"{args.pop('start_x')},{args.pop('start_y')}"
            if "end_x" in args and "end_y" in args:
                args["to"] = f"{args.pop('end_x')},{args.pop('end_y')}"
        elif tool_name == "computer_mouse_move":
            if "x" in args and "y" in args:
                args["coords"] = f"{args.pop('x')},{args.pop('y')}"
        elif tool_name == "computer_keyboard_press":
            # Convert key to text
            if "key" in args:
                args["text"] = args.pop("key")
        elif tool_name == "computer_scroll":
            # Convert x,y to coords
            if "x" in args and "y" in args:
                args["on"] = f"{args.pop('x')},{args.pop('y')}"
            if "amount" in args:
                args["ticks"] = args.pop("amount")

        return args
