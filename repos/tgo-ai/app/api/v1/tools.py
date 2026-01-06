"""Tool query API endpoints (read-only)."""

import uuid
from datetime import datetime, timezone

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tool import Tool, ToolType
from app.models.project import Project
from app.schemas.tool import ToolResponse, ToolCreate, ToolUpdate
from app.core.logging import get_logger

logger = get_logger(__name__)

# Define router with prefix and tags as requested
router = APIRouter(prefix="/tools", tags=["tools"])


# ==================== Plugin Tool Registration ====================

class PluginToolCreate(BaseModel):
    """Schema for registering a plugin tool."""
    name: str = Field(..., description="Tool name (e.g., 'plugin:com.tgo.ticket:create_ticket')")
    description: Optional[str] = Field(None, description="Tool description")
    tool_type: str = Field(default="MCP", description="Tool type (usually MCP)")
    transport_type: str = Field(default="plugin", description="Transport type (plugin)")
    endpoint: Optional[str] = Field(None, description="Plugin endpoint (e.g., 'plugin://com.tgo.ticket')")
    config: Optional[Dict[str, Any]] = Field(None, description="Tool configuration")
    project_id: str = Field(..., description="Project ID to register the tool for.")


@router.get("", response_model=List[ToolResponse])
async def list_tools(
    project_id: uuid.UUID = Query(..., description="Project ID"),
    tool_type: Optional[ToolType] = Query(None, description="Filter by tool type"),
    include_deleted: bool = Query(False, description="Include soft-deleted tools"),
    db: AsyncSession = Depends(get_db),
) -> List[ToolResponse]:
    """List tools for the specified project with optional filters."""
    stmt = select(Tool).where(Tool.project_id == project_id)

    if not include_deleted:
        stmt = stmt.where(Tool.deleted_at.is_(None))

    if tool_type is not None:
        stmt = stmt.where(Tool.tool_type == tool_type)

    result = await db.execute(stmt)
    tools = result.scalars().all()
    return [ToolResponse.model_validate(tool) for tool in tools]


@router.post("", response_model=ToolResponse)
async def create_tool(
    tool_in: ToolCreate,
    db: AsyncSession = Depends(get_db),
) -> ToolResponse:
    """Create a new tool for the specified project."""
    tool = Tool(
        project_id=tool_in.project_id,
        name=tool_in.name,
        description=tool_in.description,
        tool_type=tool_in.tool_type,
        transport_type=tool_in.transport_type,
        endpoint=tool_in.endpoint,
        config=tool_in.config,
    )

    db.add(tool)
    await db.commit()
    await db.refresh(tool)

    return ToolResponse.model_validate(tool)


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: uuid.UUID,
    tool_in: ToolUpdate,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
) -> ToolResponse:
    """Update an existing tool for the specified project."""
    stmt = select(Tool).where(
        Tool.id == tool_id,
        Tool.project_id == project_id,
        Tool.deleted_at.is_(None),
    )

    result = await db.execute(stmt)
    tool = result.scalar_one_or_none()

    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    update_data = tool_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tool, field, value)

    await db.commit()
    await db.refresh(tool)

    return ToolResponse.model_validate(tool)



@router.delete("/{tool_id}", response_model=ToolResponse)
async def delete_tool(
    tool_id: uuid.UUID,
    project_id: uuid.UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_db),
) -> ToolResponse:
    """Soft-delete a tool by setting its deleted_at timestamp."""
    stmt = select(Tool).where(
        Tool.id == tool_id,
        Tool.project_id == project_id,
        Tool.deleted_at.is_(None),
    )

    result = await db.execute(stmt)
    tool = result.scalar_one_or_none()

    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")

    tool.deleted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(tool)

    return ToolResponse.model_validate(tool)


# ==================== Plugin Tool Registration (cross-project) ====================

@router.post("/plugin", status_code=201)
async def register_plugin_tool(
    tool_in: PluginToolCreate,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Register a plugin tool for a specific project.
    
    Called by tgo-plugin-runtime when a plugin connects and registers MCP tools.
    """
    project_id = tool_in.project_id
    
    # Check if tool already exists for this project
    existing_stmt = select(Tool).where(
        Tool.project_id == project_id,
        Tool.name == tool_in.name,
        Tool.deleted_at.is_(None),
    )
    existing_result = await db.execute(existing_stmt)
    existing_tool = existing_result.scalar_one_or_none()
    
    if existing_tool:
        # Update existing tool
        existing_tool.description = tool_in.description
        existing_tool.transport_type = tool_in.transport_type
        existing_tool.endpoint = tool_in.endpoint
        existing_tool.config = tool_in.config
    else:
        # Create new tool
        tool = Tool(
            project_id=project_id,
            name=tool_in.name,
            description=tool_in.description,
            tool_type=ToolType.MCP,
            transport_type=tool_in.transport_type,
            endpoint=tool_in.endpoint,
            config=tool_in.config,
        )
        db.add(tool)

    await db.commit()
    logger.info(f"Plugin tool '{tool_in.name}' synced to project {project_id}")
    
    return {"status": "ok", "project_id": str(project_id)}


@router.delete("/plugin/by-prefix", status_code=200)
async def delete_plugin_tools_by_prefix(
    prefix: str = Query(..., description="Tool name prefix (e.g., 'plugin:com.tgo.ticket:')"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Delete all plugin tools with names starting with the given prefix.
    
    Called by tgo-plugin-runtime when a plugin disconnects.
    """
    # Find all tools with the prefix
    stmt = select(Tool).where(
        Tool.name.startswith(prefix),
        Tool.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    tools = result.scalars().all()

    deleted_count = 0
    for tool in tools:
        tool.deleted_at = datetime.now(timezone.utc)
        deleted_count += 1

    await db.commit()
    logger.info(f"Deleted {deleted_count} plugin tools with prefix '{prefix}'")
    
    return {"status": "ok", "deleted_count": deleted_count}

