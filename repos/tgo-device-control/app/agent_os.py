"""AgentOS Entry Point for TGO Device Control Service.

This module creates and configures the custom AgentOS-compatible server that exposes
the MCP Tool Agent for remote execution via the Agno protocol.

It uses McpAgent which treats connected devices as MCP remote tool providers,
enabling autonomous reasoning and tool calling for device control.

Usage:
    # Run as standalone AgentOS server
    python -m app.agent_os
    
    # Or import and use programmatically
    from app.agent_os import app, serve
"""

from typing import Optional

from app.config import settings
from app.core.logging import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger("agent_os")


# ============================================================================
# Global App Instance
# ============================================================================

# This will hold the FastAPI app instance from the custom server
app = None


def _initialize():
    """Initialize the app."""
    global app
    
    if not settings.AGENTOS_ENABLED:
        logger.info("AgentOS is disabled (AGENTOS_ENABLED=False)")
        return
    
    # Use custom AgentOS server with McpAgent
    logger.info("Initializing Custom AgentOS mode (McpAgent)")
    from app.agentos_server import app as custom_app
    app = custom_app
    logger.info("Custom AgentOS initialized successfully")


# Initialize on import
_initialize()


# ============================================================================
# Server Entry Point
# ============================================================================

def serve(
    host: Optional[str] = None,
    port: Optional[int] = None,
    reload: bool = False,
) -> None:
    """Start the AgentOS server.
    
    Args:
        host: Host to bind to. Defaults to settings.AGENTOS_HOST.
        port: Port to bind to. Defaults to settings.AGENTOS_PORT.
        reload: Enable auto-reload for development. Defaults to False.
    """
    if app is None:
        raise RuntimeError(
            "AgentOS is not initialized. Check AGENTOS_ENABLED setting."
        )
    
    _host = host or settings.AGENTOS_HOST
    _port = port or settings.AGENTOS_PORT
    _reload = reload or settings.is_development
    
    logger.info(f"Starting AgentOS server on {_host}:{_port}")
    
    # Use uvicorn to run the custom server
    import uvicorn
    uvicorn.run(
        "app.agentos_server:app",
        host=_host,
        port=_port,
        reload=_reload,
    )


if __name__ == "__main__":
    serve()
