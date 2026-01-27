"""Device management API endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.schemas.device import (
    BindCodeResponse,
    DeviceCreateRequest,
    DeviceResponse,
    DeviceListResponse,
    DeviceUpdateRequest,
)
from app.services.device_service import DeviceService

router = APIRouter()


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    project_id: UUID = Query(..., description="Project ID"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """List all devices for a project."""
    service = DeviceService(db)
    devices, total = await service.list_devices(
        project_id=project_id,
        device_type=device_type,
        status=status,
        skip=skip,
        limit=limit,
    )
    return DeviceListResponse(devices=devices, total=total)


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific device by ID."""
    service = DeviceService(db)
    device = await service.get_device(device_id=device_id, project_id=project_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/bind-code", response_model=BindCodeResponse)
async def generate_bind_code(
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Generate a new bind code for device registration."""
    service = DeviceService(db)
    bind_code, expires_at = await service.generate_bind_code(project_id=project_id)
    return BindCodeResponse(bind_code=bind_code, expires_at=expires_at)


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: UUID,
    request: DeviceUpdateRequest,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a device."""
    service = DeviceService(db)
    device = await service.update_device(
        device_id=device_id,
        project_id=project_id,
        update_data=request,
    )
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.delete("/{device_id}")
async def delete_device(
    device_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete (unbind) a device."""
    service = DeviceService(db)
    success = await service.delete_device(device_id=device_id, project_id=project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"success": True, "message": "Device deleted successfully"}


@router.post("/{device_id}/disconnect")
async def disconnect_device(
    device_id: UUID,
    project_id: UUID = Query(..., description="Project ID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Force disconnect a device."""
    from app.services.device_manager import device_manager

    service = DeviceService(db)
    device = await service.get_device(device_id=device_id, project_id=project_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    await device_manager.disconnect_device(str(device_id))
    return {"success": True, "message": "Device disconnected"}
