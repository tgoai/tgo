"""Remote Agents API endpoints - Manage Remote Agent registrations.

This module provides APIs for managing remote agents (agents running on
external AgentOS instances) that can be used by AI teams.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
import httpx

from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.models import Staff
from app.core.config import settings

logger = get_logger("api.remote_agents")
router = APIRouter()


class RemoteAgentInfo(BaseModel):
    """Remote Agent information."""
    
    agent_id: str = Field(description="Agent ID in the remote AgentOS")
    name: str = Field(description="Agent name")
    type: str = Field(default="computer_use", description="Agent type")
    base_url: str = Field(description="AgentOS base URL")
    description: Optional[str] = Field(default=None, description="Agent description")
    status: str = Field(default="available", description="Agent status")
    
    # Computer Use specific
    supports_device_control: bool = Field(default=False)
    available_tools: Optional[List[str]] = Field(default=None)


class RemoteAgentConfig(BaseModel):
    """Configuration for a Remote Agent."""
    
    agent_id: str
    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    tools: Optional[List[str]] = None
    model: Optional[str] = None


class RemoteAgentRegisterRequest(BaseModel):
    """Request to register a custom remote agent."""
    
    base_url: str = Field(description="AgentOS base URL")
    agent_id: str = Field(description="Agent ID to register")
    display_name: Optional[str] = Field(default=None, description="Custom display name")
    description: Optional[str] = Field(default=None, description="Custom description")


async def _fetch_remote_agent_info(
    base_url: str,
    agent_id: str,
) -> Optional[RemoteAgentConfig]:
    """Fetch agent configuration from remote AgentOS.
    
    Args:
        base_url: AgentOS base URL.
        agent_id: Agent ID to fetch.
        
    Returns:
        Agent configuration or None if not found.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to get agent info from AgentOS
            # Note: The actual endpoint depends on Agno AgentOS implementation
            response = await client.get(
                f"{base_url}/v1/agents/{agent_id}",
            )
            
            if response.status_code == 200:
                data = response.json()
                return RemoteAgentConfig(
                    agent_id=data.get("id", agent_id),
                    name=data.get("name", agent_id),
                    description=data.get("description"),
                    instructions=data.get("instructions"),
                    tools=data.get("tools"),
                    model=data.get("model"),
                )
            
            # If the endpoint doesn't exist, try health check
            health = await client.get(f"{base_url}/health")
            if health.status_code == 200:
                # AgentOS is up, but specific agent endpoint not available
                return RemoteAgentConfig(
                    agent_id=agent_id,
                    name=agent_id,
                    description="Remote agent (details not available)",
                )
                
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching agent info from {base_url}")
    except httpx.RequestError as e:
        logger.warning(f"Error fetching agent info from {base_url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching agent info: {e}")
    
    return None


@router.get("", response_model=Dict[str, Any])
async def list_remote_agents(
    current_user: Staff = Depends(get_current_active_user),
):
    """List available remote agents.
    
    Returns a list of known remote agents including:
    - Built-in Computer Use Agent from tgo-device-control
    - Custom registered agents
    """
    agents: List[RemoteAgentInfo] = []
    
    # Add built-in Computer Use Agent
    computer_use_agent = RemoteAgentInfo(
        agent_id=settings.DEVICE_CONTROL_AGENT_ID,
        name="Computer Use Agent",
        type="computer_use",
        base_url=settings.DEVICE_CONTROL_AGENTOS_URL,
        description=(
            "AI Agent specialized in controlling user devices to complete tasks. "
            "Capable of taking screenshots, clicking, typing, scrolling, and "
            "other GUI interactions."
        ),
        status="available",
        supports_device_control=True,
        available_tools=[
            "computer_screenshot",
            "computer_click",
            "computer_double_click",
            "computer_type",
            "computer_hotkey",
            "computer_key_press",
            "computer_scroll",
            "computer_mouse_move",
            "computer_drag",
            "computer_get_screen_size",
            "list_connected_devices",
        ],
    )
    
    # Check if the service is actually available
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.DEVICE_CONTROL_AGENTOS_URL}/health"
            )
            if response.status_code != 200:
                computer_use_agent.status = "unavailable"
    except Exception:
        computer_use_agent.status = "unavailable"
    
    agents.append(computer_use_agent)
    
    # TODO: Add custom registered agents from database
    
    return {
        "items": [agent.model_dump() for agent in agents],
        "total": len(agents),
    }


@router.get("/{agent_id}", response_model=RemoteAgentInfo)
async def get_remote_agent(
    agent_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Get information about a specific remote agent."""
    
    # Check if it's the built-in Computer Use Agent
    if agent_id == settings.DEVICE_CONTROL_AGENT_ID:
        status = "unavailable"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.DEVICE_CONTROL_AGENTOS_URL}/health"
                )
                if response.status_code == 200:
                    status = "available"
        except Exception:
            pass
        
        return RemoteAgentInfo(
            agent_id=settings.DEVICE_CONTROL_AGENT_ID,
            name="Computer Use Agent",
            type="computer_use",
            base_url=settings.DEVICE_CONTROL_AGENTOS_URL,
            description=(
                "AI Agent specialized in controlling user devices to complete tasks."
            ),
            status=status,
            supports_device_control=True,
            available_tools=[
                "computer_screenshot",
                "computer_click",
                "computer_double_click",
                "computer_type",
                "computer_hotkey",
                "computer_key_press",
                "computer_scroll",
                "computer_mouse_move",
                "computer_drag",
                "computer_get_screen_size",
                "list_connected_devices",
            ],
        )
    
    # TODO: Look up custom registered agents
    raise HTTPException(status_code=404, detail="Remote agent not found")


@router.get("/{agent_id}/config", response_model=RemoteAgentConfig)
async def get_remote_agent_config(
    agent_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Get configuration of a remote agent from its AgentOS.
    
    This fetches the agent's configuration directly from the remote
    AgentOS server.
    """
    # Determine base URL
    if agent_id == settings.DEVICE_CONTROL_AGENT_ID:
        base_url = settings.DEVICE_CONTROL_AGENTOS_URL
    else:
        # TODO: Look up custom registered agents for base_url
        raise HTTPException(status_code=404, detail="Remote agent not found")
    
    # Fetch from remote
    config = await _fetch_remote_agent_info(base_url, agent_id)
    
    if config is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch agent configuration from remote AgentOS"
        )
    
    return config


@router.post("", response_model=RemoteAgentInfo)
async def register_remote_agent(
    request: RemoteAgentRegisterRequest,
    current_user: Staff = Depends(get_current_active_user),
):
    """Register a custom remote agent.
    
    This allows registering agents from external AgentOS instances
    to be used by AI teams.
    """
    # Validate the remote agent exists
    config = await _fetch_remote_agent_info(request.base_url, request.agent_id)
    
    if config is None:
        raise HTTPException(
            status_code=400,
            detail="Could not connect to remote AgentOS or agent not found"
        )
    
    # TODO: Save to database for persistence
    
    return RemoteAgentInfo(
        agent_id=request.agent_id,
        name=request.display_name or config.name,
        type="custom",
        base_url=request.base_url,
        description=request.description or config.description,
        status="available",
        supports_device_control=False,
    )


@router.delete("/{agent_id}")
async def unregister_remote_agent(
    agent_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Unregister a custom remote agent.
    
    Note: Built-in agents (like Computer Use Agent) cannot be unregistered.
    """
    # Check if it's a built-in agent
    if agent_id == settings.DEVICE_CONTROL_AGENT_ID:
        raise HTTPException(
            status_code=400,
            detail="Cannot unregister built-in agents"
        )
    
    # TODO: Delete from database
    
    return {"success": True}


@router.post("/{agent_id}/test")
async def test_remote_agent(
    agent_id: str,
    message: str = Body(..., embed=True),
    current_user: Staff = Depends(get_current_active_user),
):
    """Test a remote agent by sending a simple message.
    
    This can be used to verify connectivity and basic functionality.
    """
    # Determine base URL
    if agent_id == settings.DEVICE_CONTROL_AGENT_ID:
        base_url = settings.DEVICE_CONTROL_AGENTOS_URL
    else:
        # TODO: Look up custom registered agents
        raise HTTPException(status_code=404, detail="Remote agent not found")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Send a test message to the agent
            response = await client.post(
                f"{base_url}/v1/agents/{agent_id}/runs",
                json={
                    "message": message,
                    "stream": False,
                },
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "response": response.json(),
                }
            else:
                return {
                    "success": False,
                    "error": f"Agent returned status {response.status_code}",
                    "details": response.text,
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timeout",
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "error": f"Connection error: {str(e)}",
        }
