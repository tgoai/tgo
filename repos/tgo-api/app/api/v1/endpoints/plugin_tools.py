"""Plugin Tools proxy endpoints - Proxies to tgo-plugin-runtime service."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.services.plugin_runtime_client import plugin_runtime_client
from app.models.visitor import Visitor
from app.schemas.plugin import (
    ToolExecuteRequest,
    ToolExecuteResponse,
    VisitorInfo,
)

logger = get_logger("api.plugin_tools")
router = APIRouter()


def _get_visitor_info(db_visitor: Visitor, language: Optional[str] = None) -> VisitorInfo:
    """Helper to create VisitorInfo with prioritized name logic."""
    name = db_visitor.name
    if not name:
        is_zh = language and language.lower().startswith("zh")
        if is_zh and db_visitor.nickname_zh:
            name = db_visitor.nickname_zh
        else:
            name = db_visitor.nickname or f"Visitor {str(db_visitor.id)[:4]}"

    return VisitorInfo(
        id=str(db_visitor.id),
        platform_open_id=db_visitor.platform_open_id,
        name=name,
        email=db_visitor.email,
        phone=db_visitor.phone_number,
        avatar=db_visitor.avatar_url,
        metadata=db_visitor.custom_attributes or {}
    )


@router.post("/execute/{plugin_id}/{tool_name}", response_model=ToolExecuteResponse)
async def execute_plugin_tool(
    plugin_id: str,
    tool_name: str,
    request: ToolExecuteRequest,
    db: Session = Depends(get_db)
) -> ToolExecuteResponse:
    """
    Proxy an MCP tool execution request to tgo-plugin-runtime.
    
    Called by tgo-ai when an agent uses a plugin-provided tool.
    """
    # Enrich visitor info if visitor_id is provided
    visitor_info = None
    if request.context.visitor_id:
        try:
            db_visitor = db.query(Visitor).filter(Visitor.id == request.context.visitor_id).first()
            if db_visitor:
                visitor_info = _get_visitor_info(db_visitor, request.context.language)
        except Exception as e:
            logger.warning(f"Failed to fetch visitor info for tool execution: {e}")

    # Build request for plugin-runtime (enriched with visitor data)
    request_data = {
        "arguments": request.arguments,
        "context": {
            "visitor_id": request.context.visitor_id,
            "session_id": request.context.session_id,
            "agent_id": request.context.agent_id,
            "language": request.context.language,
        },
    }
    
    # Add enriched visitor info
    if visitor_info:
        request_data["context"]["visitor"] = visitor_info.model_dump(exclude_none=True)

    try:
        result = await plugin_runtime_client.execute_tool(plugin_id, tool_name, request_data)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plugin not found: {plugin_id}"
            )
        return ToolExecuteResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute plugin tool: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Plugin runtime service unavailable"
        )
