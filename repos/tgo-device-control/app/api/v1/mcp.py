"""MCP (Model Context Protocol) endpoints for AI agent tool access."""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.logging import get_logger
from app.schemas.mcp import (
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolDefinition,
    MCPToolsListResponse,
)
from app.services.mcp_server import MCPServer

router = APIRouter()
logger = get_logger(__name__)


@router.get("/tools", response_model=MCPToolsListResponse)
async def list_tools(
    project_id: UUID,
    device_id: Optional[UUID] = None,
):
    """List available MCP tools for device control."""
    mcp_server = MCPServer()
    tools = mcp_server.get_tool_definitions(
        project_id=str(project_id),
        device_id=str(device_id) if device_id else None,
    )
    return MCPToolsListResponse(tools=tools)


@router.post("/tools/call", response_model=MCPToolCallResponse)
async def call_tool(
    request: MCPToolCallRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Execute an MCP tool call."""
    mcp_server = MCPServer()

    try:
        result = await mcp_server.execute_tool(
            tool_name=request.name,
            arguments=request.arguments,
            project_id=str(request.project_id),
            device_id=str(request.device_id) if request.device_id else None,
        )
        return MCPToolCallResponse(
            success=True,
            content=result.get("content"),
            error=None,
        )
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return MCPToolCallResponse(
            success=False,
            content=None,
            error=str(e),
        )


@router.post("/")
async def mcp_endpoint(request: Request):
    """
    Streamable HTTP MCP endpoint.
    
    This endpoint implements the MCP protocol over HTTP for AI agents
    to interact with device control tools.
    """
    mcp_server = MCPServer()

    try:
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        # Handle different MCP methods
        if method == "initialize":
            result = mcp_server.handle_initialize(params)
        elif method == "tools/list":
            result = mcp_server.handle_tools_list(params)
        elif method == "tools/call":
            result = await mcp_server.handle_tools_call(params)
        elif method == "ping":
            result = {}
        else:
            return Response(
                content=json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                }),
                media_type="application/json",
            )

        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }),
            media_type="application/json",
        )

    except json.JSONDecodeError:
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                },
            }),
            media_type="application/json",
            status_code=400,
        )
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        return Response(
            content=json.dumps({
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in dir() else None,
                "error": {
                    "code": -32603,
                    "message": str(e),
                },
            }),
            media_type="application/json",
            status_code=500,
        )
