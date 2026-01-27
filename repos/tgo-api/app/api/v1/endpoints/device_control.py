"""Device Control API endpoints - Proxies to tgo-device-control service."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
import httpx

from app.core.logging import get_logger
from app.core.security import get_current_active_user
from app.services.device_control_client import device_control_client
from app.models import Staff

logger = get_logger("api.device_control")
router = APIRouter()


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


@router.patch("/devices/{device_id}")
async def update_device(
    device_id: str,
    device_name: Optional[str] = None,
    current_user: Staff = Depends(get_current_active_user),
):
    """Update a device."""
    try:
        data = {}
        if device_name is not None:
            data["device_name"] = device_name

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
