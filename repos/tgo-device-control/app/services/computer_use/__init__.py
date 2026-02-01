"""Computer Use Agent - MCP Tool Agent for device control via AI."""

from app.services.computer_use.mcp_agent import (
    McpAgent,
    create_mcp_agent,
    AGENT_SYSTEM_PROMPT,
)
from app.services.computer_use.instructions import (
    COMPUTER_USE_INSTRUCTIONS,
    COMPUTER_USE_INSTRUCTIONS_SHORT,
)

__all__ = [
    # MCP Agent
    "McpAgent",
    "create_mcp_agent",
    "AGENT_SYSTEM_PROMPT",
    # Instructions
    "COMPUTER_USE_INSTRUCTIONS",
    "COMPUTER_USE_INSTRUCTIONS_SHORT",
]
