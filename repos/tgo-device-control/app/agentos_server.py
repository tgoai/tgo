"""Custom AgentOS-compatible Server for TGO Device Control.

This module implements a FastAPI server that is compatible with agno's RemoteAgent
while using the MCP Agent internally for intelligent device control.

The server exposes the same API endpoints as agno's AgentOS, allowing tgo-ai to
use RemoteAgent to communicate with this service without any modifications.

Usage:
    # Run as standalone server
    python -m app.agentos_server
    
    # Or import and use programmatically
    from app.agentos_server import app, serve
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.core.logging import setup_logging, get_logger
from app.schemas.agentos import (
    AgentConfig,
    AgentRunEvent,
    AgentRunEventType,
    AgentRunRequest,
    AgentRunResponse,
    AgentListResponse,
    ToolInfo,
)
from app.schemas.agent_events import AgentEvent, AgentEventType
from app.services.computer_use.mcp_agent import McpAgent
from app.services.tcp_connection_manager import tcp_connection_manager

# Setup logging
setup_logging()
logger = get_logger("agentos_server")


# Store for active runs (for cancellation support)
_active_runs: Dict[str, McpAgent] = {}


def _get_agent_config() -> AgentConfig:
    """Get the MCP Agent configuration.
    
    Returns:
        AgentConfig with agent details.
    """
    return AgentConfig(
        id="mcp-agent",
        name="MCP Tool Agent",
        description=(
            "AI Agent that uses connected devices as MCP remote tool providers. "
            "Capable of autonomous reasoning, tool calling, and task execution. "
            "Tools are dynamically loaded from the connected device."
        ),
        role="device_controller",
        model=settings.AGENT_MODEL,
        tools=None,  # Tools are loaded dynamically from device
        max_rounds=settings.AGENT_MAX_ITERATIONS,
        planning_model=settings.AGENT_MODEL,
        grounding_model=None,
        supports_streaming=True,
        supports_vision=True,
        supports_computer_use=True,
    )


async def _run_agent_streaming(
    message: str,
    device_id: str,
    run_id: str,
    max_rounds: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Run the agent and yield SSE-formatted events.
    
    Args:
        message: Task message to execute.
        device_id: Device ID to control.
        run_id: Run ID for tracking.
        max_rounds: Optional max rounds override.
        
    Yields:
        SSE-formatted event strings.
    """
    logger.info(f"Starting streaming agent run {run_id} for device {device_id}")
    
    # Create MCP agent
    agent = McpAgent(
        max_iterations=max_rounds or settings.AGENT_MAX_ITERATIONS,
    )
    
    # Store for cancellation
    _active_runs[run_id] = agent
    
    try:
        # Execute with streaming
        async for event in agent.run(
            task=message,
            device_id=device_id,
        ):
            # Convert AgentEvent to AgentRunEvent format for SSE
            yield _convert_to_agentos_event(event, run_id).to_sse_format()
            
    except Exception as e:
        logger.exception(f"Error in streaming agent run: {e}")
        error_event = AgentRunEvent(
            event_type=AgentRunEventType.ERROR,
            run_id=run_id,
            error=str(e),
            error_code="STREAM_ERROR",
        )
        yield error_event.to_sse_format()
        
    finally:
        # Cleanup
        if run_id in _active_runs:
            del _active_runs[run_id]
        logger.info(f"Agent run {run_id} completed")


def _convert_to_agentos_event(event: AgentEvent, run_id: str) -> AgentRunEvent:
    """Convert AgentEvent to AgentRunEvent format.
    
    Args:
        event: AgentEvent from MCP Agent.
        run_id: Run ID for tracking.
        
    Returns:
        AgentRunEvent compatible with agno.
    """
    # Map event types
    event_type_map = {
        AgentEventType.STARTED: AgentRunEventType.RUN_STARTED,
        AgentEventType.TOOLS_LOADED: AgentRunEventType.CONTENT,
        AgentEventType.THINKING: AgentRunEventType.PLANNING_COMPLETE,
        AgentEventType.TOOL_CALL: AgentRunEventType.ACTION_EXECUTED,
        AgentEventType.TOOL_RESULT: AgentRunEventType.ROUND_COMPLETE,
        AgentEventType.COMPLETED: AgentRunEventType.RUN_COMPLETE,
        AgentEventType.ERROR: AgentRunEventType.ERROR,
    }
    
    agentos_type = event_type_map.get(
        event.event_type, AgentRunEventType.CONTENT
    )
    
    return AgentRunEvent(
        event_type=agentos_type,
        run_id=run_id,
        content=event.content,
        reasoning=event.content if event.event_type == AgentEventType.THINKING else None,
        round_number=event.iteration,
        max_rounds=event.max_iterations,
        final_result=event.final_result,
        error=event.error,
        error_code=event.error_code,
    )


async def _run_agent_sync(
    message: str,
    device_id: str,
    run_id: str,
    max_rounds: Optional[int] = None,
) -> AgentRunResponse:
    """Run the agent synchronously and return final result.
    
    Args:
        message: Task message to execute.
        device_id: Device ID to control.
        run_id: Run ID for tracking.
        max_rounds: Optional max rounds override.
        
    Returns:
        AgentRunResponse with execution results.
    """
    logger.info(f"Starting sync agent run {run_id} for device {device_id}")
    
    started_at = datetime.utcnow()
    
    # Create MCP agent
    agent = McpAgent(
        max_iterations=max_rounds or settings.AGENT_MAX_ITERATIONS,
    )
    
    # Store for cancellation
    _active_runs[run_id] = agent
    
    # Track execution stats
    rounds_executed = 0
    actions_executed = 0
    final_result = None
    error_message = None
    task_completed = False
    
    try:
        # Execute task and collect events
        async for event in agent.run(
            task=message,
            device_id=device_id,
        ):
            if event.event_type == AgentEventType.THINKING:
                rounds_executed = event.iteration or rounds_executed
            elif event.event_type == AgentEventType.TOOL_CALL:
                actions_executed += 1
            elif event.event_type == AgentEventType.COMPLETED:
                final_result = event.final_result
                task_completed = True
            elif event.event_type == AgentEventType.ERROR:
                error_message = event.error
        
        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        
        return AgentRunResponse(
            run_id=run_id,
            status="completed" if task_completed else "failed",
            content=final_result or error_message or "Task execution finished",
            rounds_executed=rounds_executed,
            actions_executed=actions_executed,
            screenshots_taken=0,  # Not tracked in new implementation
            task_completed=task_completed,
            final_result=final_result,
            error=error_message,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )
        
    finally:
        # Cleanup
        if run_id in _active_runs:
            del _active_runs[run_id]
        logger.info(f"Agent run {run_id} completed")


# Supported agent IDs (mcp-agent is the new name, computer-use-agent for backward compatibility)
SUPPORTED_AGENT_IDS = {"mcp-agent", "computer-use-agent"}


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    logger.info("Starting Custom AgentOS Server...")
    yield
    logger.info("Shutting down Custom AgentOS Server...")
    # Clear active runs
    _active_runs.clear()


# Create FastAPI app
app = FastAPI(
    title="TGO Device Control - AgentOS",
    description=(
        "Custom AgentOS-compatible server for TGO Device Control. "
        "Provides Computer Use Agent capabilities via agno RemoteAgent protocol."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# AgentOS Compatible Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "service": "TGO Device Control - AgentOS",
        "version": "1.0.0",
        "description": "Custom AgentOS server for Computer Use Agent",
        "protocol": "agentos",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "tgo-device-control-agentos",
    }


@app.get("/agents")
async def list_agents() -> AgentListResponse:
    """List all available agents.
    
    Returns:
        AgentListResponse with list of agents.
    """
    return AgentListResponse(agents=[_get_agent_config()])


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentConfig:
    """Get agent configuration.
    
    This endpoint is called by RemoteAgent to fetch agent metadata.
    
    Args:
        agent_id: Agent ID to get configuration for.
        
    Returns:
        AgentConfig with agent details.
    """
    if agent_id not in SUPPORTED_AGENT_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available agents: {', '.join(SUPPORTED_AGENT_IDS)}"
        )
    
    return _get_agent_config()


@app.post("/agents/{agent_id}/runs")
async def run_agent(
    agent_id: str,
    request: Request,
    # Form fields (agno uses application/x-www-form-urlencoded)
    message: str = Form(..., description="User message/task"),
    stream: bool = Form(default=True, description="Enable streaming"),
    user_id: Optional[str] = Form(default=None, description="User ID"),
    session_id: Optional[str] = Form(default=None, description="Session ID"),
    # Custom parameters for Computer Use
    device_id: Optional[str] = Form(default=None, description="Device ID to control (fallback)"),
    max_rounds: Optional[int] = Form(default=None, description="Max rounds"),
    # Additional agno parameters
    session_state: Optional[str] = Form(default=None, description="Session state JSON"),
    metadata: Optional[str] = Form(default=None, description="Metadata JSON"),
    dependencies: Optional[str] = Form(default=None, description="Dependencies JSON"),
):
    """Run the agent with a task.
    
    This endpoint is called by RemoteAgent.arun() to execute tasks.
    Supports both streaming (SSE) and non-streaming responses.
    
    Device ID resolution priority:
        1. X-Device-ID HTTP header (recommended)
        2. device_id form parameter (fallback)
    
    Args:
        agent_id: Agent ID to run.
        message: Task message to execute.
        stream: Whether to stream the response.
        device_id: Optional device ID form parameter (fallback if header not provided).
        max_rounds: Optional max rounds override.
        
    Returns:
        SSE stream if stream=True, otherwise AgentRunResponse.
    """
    # Validate agent_id
    if agent_id not in SUPPORTED_AGENT_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found. Available agents: {', '.join(SUPPORTED_AGENT_IDS)}"
        )
    
    # Priority 1: Get device_id from X-Device-ID header
    _device_id = request.headers.get("X-Device-ID")
    
    # Priority 2: Fallback to form parameter
    if not _device_id:
        _device_id = device_id
    
    if not _device_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "device_id is required. Provide via X-Device-ID header "
                "or device_id form parameter."
            )
        )
    
    # Generate run_id
    run_id = str(uuid4())
    
    logger.info(
        f"Agent run request: agent={agent_id}, device={_device_id}, "
        f"stream={stream}, run_id={run_id}"
    )
    
    if stream:
        # Return SSE stream
        return EventSourceResponse(
            _run_agent_streaming(
                message=message,
                device_id=_device_id,
                run_id=run_id,
                max_rounds=max_rounds,
            ),
            media_type="text/event-stream",
        )
    else:
        # Return synchronous response
        return await _run_agent_sync(
            message=message,
            device_id=_device_id,
            run_id=run_id,
            max_rounds=max_rounds,
        )


@app.post("/agents/{agent_id}/runs/{run_id}/cancel")
async def cancel_run(agent_id: str, run_id: str):
    """Cancel a running agent execution.
    
    Args:
        agent_id: Agent ID.
        run_id: Run ID to cancel.
        
    Returns:
        Success status.
    """
    if run_id in _active_runs:
        # Remove from active runs (cancellation is handled by cleanup)
        del _active_runs[run_id]
        return {"success": True, "message": f"Run {run_id} cancelled"}
    else:
        return {"success": False, "message": f"Run {run_id} not found or already completed"}


# ============================================================================
# Additional Utility Endpoints
# ============================================================================

@app.get("/agents/{agent_id}/tools")
async def get_agent_tools(
    agent_id: str,
    device_id: Optional[str] = Query(None, description="Device ID to get tools from"),
):
    """Get list of tools available to the agent.
    
    Tools are dynamically loaded from connected devices. If device_id is provided,
    returns tools from that specific device. Otherwise returns a summary.
    
    Args:
        agent_id: Agent ID.
        device_id: Optional device ID to get tools from.
        
    Returns:
        List of tool definitions.
    """
    if agent_id not in SUPPORTED_AGENT_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found"
        )
    
    if device_id:
        # Get tools from specific device
        connection = tcp_connection_manager.get_connection(device_id)
        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"Device {device_id} is not connected"
            )
        
        # Fetch tools if not already loaded
        if not connection.tools:
            tools = await connection.list_tools()
            if tools is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to fetch tools from device"
                )
        
        return {
            "device_id": device_id,
            "tools": connection.tools,
            "count": len(connection.tools),
        }
    else:
        # Return summary of all connected devices and their tool counts
        connections = tcp_connection_manager.list_connections()
        return {
            "message": "Tools are loaded dynamically from connected devices",
            "connected_devices": [
                {
                    "device_id": conn.agent_id,
                    "name": conn.name,
                    "tools_count": len(conn.tools),
                }
                for conn in connections
            ],
            "hint": "Provide device_id query parameter to get tools from a specific device",
        }


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
        reload: Enable auto-reload for development.
    """
    import uvicorn
    
    _host = host or settings.AGENTOS_HOST
    _port = port or settings.AGENTOS_PORT
    _reload = reload or settings.is_development
    
    logger.info(f"Starting Custom AgentOS server on {_host}:{_port}")
    
    uvicorn.run(
        "app.agentos_server:app",
        host=_host,
        port=_port,
        reload=_reload,
    )


if __name__ == "__main__":
    serve()
