"""Internal services router.

This router includes all internal endpoints that do not require authentication.
These endpoints are designed for inter-service communication within the internal network.
"""

from fastapi import APIRouter

from app.api.internal.endpoints import ai_events, users, store

internal_router = APIRouter()

# Include internal endpoints (no authentication required)
internal_router.include_router(
    ai_events.router,
    prefix="/ai/events",
    tags=["Internal AI Events"]
)

# New users endpoint
internal_router.include_router(
    users.router,
    prefix="/users",
    tags=["Internal Users"]
)

# Store endpoint
internal_router.include_router(
    store.router,
    prefix="/store",
    tags=["Internal Store"]
)
