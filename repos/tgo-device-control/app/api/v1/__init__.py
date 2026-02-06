"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1 import devices, mcp

router = APIRouter()

router.include_router(devices.router, prefix="/devices", tags=["devices"])
router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
