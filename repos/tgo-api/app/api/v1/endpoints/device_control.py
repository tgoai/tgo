"""Device Control API endpoints - Proxies to tgo-device-control service."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import httpx

from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.core.database import get_db
from app.services.device_control_client import device_control_client
from app.models import Staff, ProjectAIConfig

logger = get_logger("api.device_control")
router = APIRouter()


# Request/Response schemas for device debug chat
class DeviceDebugChatRequest(BaseModel):
    """Request schema for device debug chat."""
    device_id: str = Field(..., description="ID of the device to control")
    message: str = Field(..., description="User message/task to execute")
    model: Optional[str] = Field(None, description="Optional LLM model to use")
    max_iterations: Optional[int] = Field(None, description="Optional max iterations")
    system_prompt: Optional[str] = Field(None, description="Optional custom system prompt")


def _handle_service_error(e: Exception, context: str):
    """Helper to handle errors from device control service."""
    if isinstance(e, HTTPException):
        raise e

    if isinstance(e, httpx.HTTPStatusError):
        if 400 <= e.response.status_code < 500:
            try:
                detail = e.response.json().get("detail", e.response.text)
            except Exception:
                detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        logger.error(
            f"Device control service error ({e.response.status_code}) during {context}: {e.response.text}"
        )
        raise HTTPException(status_code=502, detail="Device control service error")

    if isinstance(e, httpx.RequestError):
        logger.error(f"Device control service connection error during {context}: {e}")
        raise HTTPException(
            status_code=502, detail="Device control service unavailable"
        )

    logger.error(f"Unexpected error during {context}: {e}")
    raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/devices")
async def list_devices(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: Staff = Depends(get_current_active_user),
):
    """List all devices for the current project."""
    try:
        return await device_control_client.list_devices(
            project_id=str(current_user.project_id),
            device_type=device_type,
            status=status,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        _handle_service_error(e, "list_devices")


@router.get("/devices/{device_id}")
async def get_device(
    device_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Get a specific device by ID."""
    try:
        result = await device_control_client.get_device(
            device_id=device_id,
            project_id=str(current_user.project_id),
        )
        if not result:
            raise HTTPException(status_code=404, detail="Device not found")
        return result
    except Exception as e:
        _handle_service_error(e, "get_device")


@router.post("/devices/bind-code")
async def generate_bind_code(
    current_user: Staff = Depends(get_current_active_user),
):
    """Generate a new bind code for device registration."""
    try:
        return await device_control_client.generate_bind_code(
            project_id=str(current_user.project_id),
        )
    except Exception as e:
        _handle_service_error(e, "generate_bind_code")


class DeviceUpdateRequest(BaseModel):
    """Request schema for updating a device."""
    device_name: Optional[str] = Field(None, description="Device name")
    ai_provider_id: Optional[str] = Field(None, description="AI Provider ID for this device")
    model: Optional[str] = Field(None, description="LLM model identifier for this device")


@router.patch("/devices/{device_id}")
async def update_device(
    device_id: str,
    request: DeviceUpdateRequest,
    current_user: Staff = Depends(get_current_active_user),
):
    """Update a device."""
    try:
        data = request.model_dump(exclude_unset=True)

        result = await device_control_client.update_device(
            device_id=device_id,
            project_id=str(current_user.project_id),
            data=data,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Device not found")
        return result
    except Exception as e:
        _handle_service_error(e, "update_device")


@router.delete("/devices/{device_id}")
async def delete_device(
    device_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Delete (unbind) a device."""
    try:
        success = await device_control_client.delete_device(
            device_id=device_id,
            project_id=str(current_user.project_id),
        )
        if not success:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"success": True}
    except Exception as e:
        _handle_service_error(e, "delete_device")


@router.post("/devices/{device_id}/disconnect")
async def disconnect_device(
    device_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Force disconnect a device."""
    try:
        success = await device_control_client.disconnect_device(
            device_id=device_id,
            project_id=str(current_user.project_id),
        )
        if not success:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"success": True}
    except Exception as e:
        _handle_service_error(e, "disconnect_device")


# Device Debug Chat Endpoints

@router.post("/chat")
async def device_debug_chat(
    request: DeviceDebugChatRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
):
    """Start a device debug chat session with streaming response.
    
    This endpoint allows users to control a device using natural language.
    The AI agent will interpret the message and execute appropriate actions
    on the device, streaming back progress updates and results.
    
    Returns an SSE stream with events:
    - started: Agent started processing
    - tools_loaded: Available tools loaded from device
    - thinking: AI is analyzing/deciding
    - tool_call: Executing a tool on the device
    - tool_result: Result from tool execution (may include screenshot)
    - completed: Task completed successfully
    - error: An error occurred
    """
    project_id = str(current_user.project_id)

    # Verify device belongs to current user's project
    try:
        device = await device_control_client.get_device(
            device_id=request.device_id,
            project_id=project_id,
        )
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
    except HTTPException:
        raise
    except Exception as e:
        _handle_service_error(e, "device_debug_chat_verify")

    # Determine model configuration
    # Priority: 1. Device-specific model, 2. Global device control model
    provider_id: Optional[str] = None
    model: Optional[str] = request.model  # Allow override from request

    # Check device-specific model
    if device.get("ai_provider_id") and device.get("model"):
        provider_id = device.get("ai_provider_id")
        model = model or device.get("model")
    else:
        # Query global device control model config
        config = (
            db.query(ProjectAIConfig)
            .filter(
                ProjectAIConfig.project_id == current_user.project_id,
                ProjectAIConfig.deleted_at.is_(None),
            )
            .first()
        )
        if config and config.device_control_provider_id and config.device_control_model:
            provider_id = str(config.device_control_provider_id)
            model = model or config.device_control_model

    # Validate that we have model configuration
    if not provider_id or not model:
        raise HTTPException(
            status_code=400,
            detail="Device control model not configured. Please configure a model in AI → Device Control settings.",
        )

    async def event_generator():
        """Generate SSE events from device control agent."""
        try:
            async for line in device_control_client.run_agent_stream(
                device_id=request.device_id,
                task=request.message,
                provider_id=provider_id,
                model=model,
                project_id=project_id,
                max_iterations=request.max_iterations,
                system_prompt=request.system_prompt,
            ):
                # Forward SSE events directly
                if line.startswith("data:"):
                    yield f"{line}\n\n"
                elif line.strip():
                    yield f"data: {line}\n\n"
        except httpx.HTTPStatusError as e:
            error_data = f'{{"event_type": "error", "error": "Service error: {e.response.status_code}"}}'
            yield f"data: {error_data}\n\n"
        except httpx.RequestError as e:
            error_data = f'{{"event_type": "error", "error": "Connection error: {str(e)}"}}'
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.exception(f"Device debug chat error: {e}")
            error_data = f'{{"event_type": "error", "error": "Internal error: {str(e)}"}}'
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/connected-devices")
async def list_connected_devices(
    current_user: Staff = Depends(get_current_active_user),
):
    """List all connected devices available for agent control.
    
    Returns devices that are currently connected via TCP and can receive
    commands from the AI agent.
    """
    try:
        result = await device_control_client.list_connected_devices()
        
        # Filter devices by project_id
        project_id = str(current_user.project_id)
        devices = await device_control_client.list_devices(project_id=project_id)
        device_ids = {d["id"] for d in devices.get("devices", [])}
        
        # Only return connected devices that belong to the user's project
        connected = result.get("devices", [])
        filtered = [d for d in connected if d.get("device_id") in device_ids]
        
        return {
            "devices": filtered,
            "count": len(filtered),
        }
    except Exception as e:
        _handle_service_error(e, "list_connected_devices")


@router.get("/devices/{device_id}/tools")
async def get_device_tools(
    device_id: str,
    current_user: Staff = Depends(get_current_active_user),
):
    """Get available tools from a connected device.
    
    Returns the list of MCP tools available on the device for AI agent control.
    """
    # Verify device belongs to current user's project
    try:
        device = await device_control_client.get_device(
            device_id=device_id,
            project_id=str(current_user.project_id),
        )
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
    except HTTPException:
        raise
    except Exception as e:
        _handle_service_error(e, "get_device_tools_verify")

    try:
        result = await device_control_client.get_device_tools(device_id=device_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Device not connected or tools unavailable"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        _handle_service_error(e, "get_device_tools")
