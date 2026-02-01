"""MCP Agent API endpoints.

This module provides API endpoints for running the MCP Agent
which uses connected devices as remote tool providers.
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.core.logging import get_logger
from app.schemas.agent_events import (
    AgentEvent,
    AgentEventType,
    AgentRunRequest,
    AgentRunResponse,
)
from app.services.computer_use.mcp_agent import McpAgent
from app.services.tcp_connection_manager import tcp_connection_manager

logger = get_logger("api.v1.agent")

router = APIRouter()


@router.get("/devices")
async def list_connected_devices():
    """List all connected devices available for agent control.

    Returns:
        List of connected device information.
    """
    connections = tcp_connection_manager.list_connections()

    devices = []
    for conn in connections:
        devices.append(
            {
                "device_id": conn.agent_id,
                "name": conn.name,
                "version": conn.version,
                "capabilities": conn.capabilities,
                "connected_at": conn.connected_at.isoformat(),
                "tools_count": len(conn.tools),
            }
        )

    return {
        "devices": devices,
        "count": len(devices),
    }


@router.get("/devices/{device_id}/tools")
async def get_device_tools(device_id: str):
    """Get available tools from a connected device.

    Args:
        device_id: ID of the device to get tools from.

    Returns:
        List of tool definitions from the device.
    """
    connection = tcp_connection_manager.get_connection(device_id)
    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Device {device_id} is not connected",
        )

    # Fetch tools if not already loaded
    if not connection.tools:
        tools = await connection.list_tools()
        if tools is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch tools from device",
            )

    return {
        "device_id": device_id,
        "tools": connection.tools,
        "count": len(connection.tools),
    }


@router.post("/run")
async def run_agent(request: AgentRunRequest):
    """Run the MCP Agent to complete a task on a device.

    This endpoint supports both streaming (SSE) and non-streaming responses.

    Args:
        request: Agent run request with task and device ID.

    Returns:
        SSE stream if stream=True, otherwise AgentRunResponse.
    """
    logger.info(
        f"Agent run request: device={request.device_id}, "
        f"stream={request.stream}, task={request.task[:50]}..."
    )

    # Verify device is connected
    connection = tcp_connection_manager.get_connection(request.device_id)
    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Device {request.device_id} is not connected",
        )

    # Create agent
    agent = McpAgent(
        model=request.model,
        max_iterations=request.max_iterations,
    )

    if request.stream:
        # Return SSE stream
        return EventSourceResponse(
            _run_agent_streaming(agent, request),
            media_type="text/event-stream",
        )
    else:
        # Return synchronous response
        return await _run_agent_sync(agent, request)


async def _run_agent_streaming(agent: McpAgent, request: AgentRunRequest):
    """Run agent and yield SSE events.

    Args:
        agent: McpAgent instance.
        request: Agent run request.

    Yields:
        SSE-formatted event strings.
    """
    async for event in agent.run(
        task=request.task,
        device_id=request.device_id,
    ):
        yield event.to_sse()


async def _run_agent_sync(
    agent: McpAgent,
    request: AgentRunRequest,
) -> AgentRunResponse:
    """Run agent synchronously and return final result.

    Args:
        agent: McpAgent instance.
        request: Agent run request.

    Returns:
        AgentRunResponse with execution results.
    """
    started_at = datetime.utcnow()
    run_id = str(uuid4())

    iterations = 0
    tool_calls = 0
    final_result = None
    error_msg = None
    error_code = None
    success = True

    async for event in agent.run(
        task=request.task,
        device_id=request.device_id,
    ):
        if event.event_type == AgentEventType.TOOL_CALL:
            tool_calls += 1
        elif event.event_type == AgentEventType.THINKING:
            iterations = event.iteration or iterations
        elif event.event_type == AgentEventType.COMPLETED:
            final_result = event.final_result
        elif event.event_type == AgentEventType.ERROR:
            success = False
            error_msg = event.error
            error_code = event.error_code

    completed_at = datetime.utcnow()
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    return AgentRunResponse(
        run_id=run_id,
        status="completed" if success else "failed",
        result=final_result or error_msg or "Task execution finished",
        iterations=iterations,
        tool_calls=tool_calls,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        success=success,
        error=error_msg,
        error_code=error_code,
    )


@router.get("/config")
async def get_agent_config():
    """Get current agent configuration.

    Returns:
        Current agent configuration settings.
    """
    return {
        "model": settings.AGENT_MODEL,
        "max_iterations": settings.AGENT_MAX_ITERATIONS,
        "has_custom_prompt": settings.AGENT_SYSTEM_PROMPT is not None,
    }
