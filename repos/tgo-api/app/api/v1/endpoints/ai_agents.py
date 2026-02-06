"""AI Agents proxy endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse

from app.api.common_responses import CREATE_RESPONSES, CRUD_RESPONSES, LIST_RESPONSES, UPDATE_RESPONSES
from app.core.logging import get_logger
from app.core.security import get_authenticated_project
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.schemas.ai import (
    AgentCreateRequest,
    AgentListResponse,
    AgentResponse,
    AgentUpdateRequest,
    AgentWithDetailsResponse,
    ToggleEnabledRequest,
)
from app.models.ai_provider import AIProvider
from app.services.ai_client import ai_client
from app.services.device_control_client import device_control_client

logger = get_logger("endpoints.ai_agents")
router = APIRouter()


async def _enrich_agent_with_device(
    agent_data: Dict[str, Any],
    project_id: str,
) -> None:
    """Enrich a single agent dict with bound_device info from tgo-device-control.

    Mutates *agent_data* in-place by adding a ``bound_device`` key when the
    agent has a non-empty ``bound_device_id``.
    """
    device_id = agent_data.get("bound_device_id")
    if not device_id:
        return

    try:
        device = await device_control_client.get_device(
            device_id=str(device_id),
            project_id=project_id,
        )
        if device:
            agent_data["bound_device"] = device
    except Exception:
        logger.warning(
            "Failed to fetch bound device info",
            extra={"device_id": device_id, "project_id": project_id},
            exc_info=True,
        )


async def _enrich_agents_with_devices(
    agents: List[Dict[str, Any]],
    project_id: str,
) -> None:
    """Enrich a list of agent dicts with bound_device info."""
    for agent_data in agents:
        await _enrich_agent_with_device(agent_data, project_id)


@router.get(
    "",
    response_model=AgentListResponse,
    responses=LIST_RESPONSES,
    summary="List Agents",
    description="""
    Retrieve all AI agents for the authenticated project with filtering and pagination.
    
    Agents are AI entities that can be configured with specific models, instructions, and tools.
    All results are automatically scoped to the authenticated project.
    """,
)
async def list_agents(
    team_id: Optional[UUID] = Query(
        None, description="Filter by team ID"
    ),
    model: Optional[str] = Query(
        None, description="Filter by model name (e.g., gpt-4)"
    ),
    is_default: Optional[bool] = Query(
        None, description="Filter by default agent status"
    ),
    limit: int = Query(
        20, ge=1, le=100, description="Number of agents to return"
    ),
    offset: int = Query(
        0, ge=0, description="Number of agents to skip"
    ),
    project_and_api_key = Depends(get_authenticated_project),
    ) -> AgentListResponse:
    """List agents from AI service.

    Returns raw JSON to tolerate upstream schema changes while preserving docs.
    """
    project, _ = project_and_api_key
    logger.info(
        "Listing AI agents",
        extra={
            "team_id": str(team_id) if team_id else None,
            "model": model,
            "is_default": is_default,
            "limit": limit,
            "offset": offset,
        }
    )

    result = await ai_client.list_agents(
        project_id=str(project.id),
        team_id=str(team_id) if team_id else None,
        model=model,
        is_default=is_default,
        limit=limit,
        offset=offset,
    )

    # Enrich agents with bound device info from tgo-device-control
    if isinstance(result, dict) and isinstance(result.get("data"), list):
        await _enrich_agents_with_devices(result["data"], str(project.id))

    # Return raw JSON to avoid strict validation while keeping OpenAPI schema
    return JSONResponse(content=result)


@router.post(
    "",
    response_model=AgentResponse,
    responses=CREATE_RESPONSES,
    status_code=201,
    summary="Create Agent",
    description="""
    Create a new AI agent within the authenticated project.
    
    Agents can be configured with specific LLM models, system instructions, and tool bindings.
    Only one default agent is allowed per project. Agent is automatically scoped to the authenticated project.
    """,
)
async def create_agent(
    agent_data: AgentCreateRequest,
    project_and_api_key = Depends(get_authenticated_project),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Create agent in AI service."""
    project, _ = project_and_api_key
    
    logger.info(
        "Creating AI agent",
        extra={
            "agent_name": agent_data.name,
            "model": agent_data.model,
            "team_id": str(agent_data.team_id) if agent_data.team_id else None,
            "is_default": agent_data.is_default,
            "workflow_count": len(agent_data.workflows) if agent_data.workflows else 0,
            "bound_device_id": agent_data.bound_device_id,
        }
    )

    payload = agent_data.model_dump(exclude_none=True)
    # Normalize model to pure name (strip provider prefix if present)
    model_val = payload.get("model")
    if isinstance(model_val, str) and ":" in model_val:
        payload["model"] = model_val.split(":", 1)[1]

    # Map ai_provider_id -> llm_provider_id and validate ownership
    ai_provider_id = payload.pop("ai_provider_id", None)
    if ai_provider_id is not None:
        provider = db.query(AIProvider).filter(
            AIProvider.id == ai_provider_id,
            AIProvider.project_id == project.id,
            AIProvider.deleted_at.is_(None),
        ).first()
        if not provider:
            raise HTTPException(status_code=404, detail="AIProvider not found for current project")
        payload["llm_provider_id"] = str(ai_provider_id)

    # Use project's default team_id if not provided in request
    if "team_id" not in payload or payload.get("team_id") is None:
        if project.default_team_id:
            payload["team_id"] = project.default_team_id

    result = await ai_client.create_agent(
        project_id=str(project.id),
        agent_data=payload,
    )

    return AgentResponse.model_validate(result)


@router.get(
    "/{agent_id}",
    response_model=AgentWithDetailsResponse,
    responses=CRUD_RESPONSES,
    summary="Get Agent",
    description="""
    Retrieve detailed information about a specific AI agent including tool bindings
    and collection access if requested. Agent must belong to the authenticated project.
    """,
)
async def get_agent(
    agent_id: UUID,
    include_tools: bool = Query(
        True, description="Include tool bindings in the response"
    ),
    include_collections: bool = Query(
        False, description="Include collection bindings in the response"
    ),
    include_workflows: bool = Query(
        False, description="Include workflow bindings in the response"
    ),
    project_and_api_key = Depends(get_authenticated_project),
) -> AgentWithDetailsResponse:
    """Get agent from AI service with schema-validated response.

    Unknown extra fields from the AI service are safely ignored
    (configured via BaseSchema.extra="ignore").
    """
    logger.info(
        "Getting AI agent",
        extra={
            "agent_id": str(agent_id),
            "include_tools": include_tools,
            "include_collections": include_collections,
            "include_workflows": include_workflows,
        }
    )
    
    project, _ = project_and_api_key
    result = await ai_client.get_agent(
        project_id=str(project.id),
        agent_id=str(agent_id),
        include_tools=include_tools,
        include_collections=include_collections,
        include_workflows=include_workflows,
    )

    # Enrich with bound device info from tgo-device-control
    if isinstance(result, dict):
        await _enrich_agent_with_device(result, str(project.id))

    # Return raw JSON to avoid strict validation, while keeping docs via response_model
    return JSONResponse(content=result)


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    responses=UPDATE_RESPONSES,
    summary="Update Agent",
    description="""
    Update AI agent configuration, tools, or settings.
    
    You can modify agent name, instruction, model, team association, tool bindings,
    and default agent status. Agent must belong to the authenticated project.
    """,
)
async def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdateRequest,
    project_and_api_key = Depends(get_authenticated_project),
    db: Session = Depends(get_db),
) -> AgentResponse:
    """Update agent in AI service."""
    project, _ = project_and_api_key
    
    logger.info(
        "Updating AI agent",
        extra={
            "agent_id": str(agent_id),
            "agent_name": agent_data.name,
            "model": agent_data.model,
            "team_id": str(agent_data.team_id) if agent_data.team_id else None,
            "is_default": agent_data.is_default,
            "workflow_count": len(agent_data.workflows) if agent_data.workflows else 0,
            "bound_device_id": agent_data.bound_device_id,
        }
    )

    payload = agent_data.model_dump(exclude_none=True)
    # Normalize model to pure name (strip provider prefix if present)
    model_val = payload.get("model")
    if isinstance(model_val, str) and ":" in model_val:
        payload["model"] = model_val.split(":", 1)[1]

    # Map ai_provider_id -> llm_provider_id and validate ownership if provided
    ai_provider_id = payload.pop("ai_provider_id", None)
    if ai_provider_id is not None:
        provider = db.query(AIProvider).filter(
            AIProvider.id == ai_provider_id,
            AIProvider.project_id == project.id,
            AIProvider.deleted_at.is_(None),
        ).first()
        if not provider:
            raise HTTPException(status_code=404, detail="AIProvider not found for current project")
        payload["llm_provider_id"] = str(ai_provider_id)

    result = await ai_client.update_agent(
        project_id=str(project.id),
        agent_id=str(agent_id),
        agent_data=payload,
    )

    return AgentResponse.model_validate(result)


@router.delete(
    "/{agent_id}",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Delete Agent",
    description="""
    Soft delete an AI agent by its UUID. The agent will be marked as deleted but
    preserved for audit purposes. Agent must belong to the authenticated project.
    """,
)
async def delete_agent(
    agent_id: UUID,
    project_and_api_key = Depends(get_authenticated_project),
) -> None:
    """Delete agent from AI service."""
    logger.info(
        "Deleting AI agent",
        extra={"agent_id": str(agent_id)}
    )

    project, _ = project_and_api_key
    await ai_client.delete_agent(
        project_id=str(project.id),
        agent_id=str(agent_id),
    )


@router.patch(
    "/{agent_id}/tools/{tool_id}/enabled",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Set Agent Tool Enabled",
    description="""
    Enable or disable a specific tool binding for an agent.

    This allows you to toggle individual tool bindings without modifying the entire agent configuration.
    Agent and tool binding must belong to the authenticated project.
    """,
)
async def set_agent_tool_enabled(
    agent_id: UUID,
    tool_id: UUID,
    toggle_data: ToggleEnabledRequest,
    project_and_api_key = Depends(get_authenticated_project),
) -> None:
    """Enable or disable a specific tool binding for an agent."""
    logger.info(
        "Setting agent tool enabled state",
        extra={
            "agent_id": str(agent_id),
            "tool_id": str(tool_id),
            "enabled": toggle_data.enabled,
        }
    )

    project, _ = project_and_api_key
    await ai_client.set_agent_tool_enabled(
        project_id=str(project.id),
        agent_id=str(agent_id),
        tool_id=str(tool_id),
        enabled=toggle_data.enabled,
    )


@router.patch(
    "/{agent_id}/collections/{collection_id}/enabled",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Set Agent Collection Enabled",
    description="""
    Enable or disable a specific collection binding for an agent.

    This allows you to toggle individual collection bindings without modifying the entire agent configuration.
    Agent and collection binding must belong to the authenticated project.
    """,
)
async def set_agent_collection_enabled(
    agent_id: UUID,
    collection_id: str,
    toggle_data: ToggleEnabledRequest,
    project_and_api_key = Depends(get_authenticated_project),
) -> None:
    """Enable or disable a specific collection binding for an agent."""
    logger.info(
        "Setting agent collection enabled state",
        extra={
            "agent_id": str(agent_id),
            "collection_id": collection_id,
            "enabled": toggle_data.enabled,
        }
    )

    project, _ = project_and_api_key
    await ai_client.set_agent_collection_enabled(
        project_id=str(project.id),
        agent_id=str(agent_id),
        collection_id=collection_id,
        enabled=toggle_data.enabled,
    )


@router.patch(
    "/{agent_id}/workflows/{workflow_id}/enabled",
    responses=CRUD_RESPONSES,
    status_code=204,
    summary="Set Agent Workflow Enabled",
    description="""
    Enable or disable a specific workflow binding for an agent.

    This allows you to toggle individual workflow bindings without modifying the entire agent configuration.
    Agent and workflow binding must belong to the authenticated project.
    """,
)
async def set_agent_workflow_enabled(
    agent_id: UUID,
    workflow_id: str,
    toggle_data: ToggleEnabledRequest,
    project_and_api_key = Depends(get_authenticated_project),
) -> None:
    """Enable or disable a specific workflow binding for an agent."""
    logger.info(
        "Setting agent workflow enabled state",
        extra={
            "agent_id": str(agent_id),
            "workflow_id": workflow_id,
            "enabled": toggle_data.enabled,
        }
    )

    project, _ = project_and_api_key
    await ai_client.set_agent_workflow_enabled(
        project_id=str(project.id),
        agent_id=str(agent_id),
        workflow_id=workflow_id,
        enabled=toggle_data.enabled,
    )
