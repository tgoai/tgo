"""Health check endpoint."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.db.base import SessionLocal

router = APIRouter()
logger = logging.getLogger(__name__)


class DependencyStatus(BaseModel):
    """Status of a single dependency."""

    name: str
    status: str  # "healthy", "unhealthy", "unknown"
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str  # "healthy", "degraded", "unhealthy"
    service: str
    version: str
    dependencies: list[DependencyStatus]
    active_workers: int


async def check_database() -> DependencyStatus:
    """Check PostgreSQL database connectivity."""
    import time

    start = time.time()
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            return DependencyStatus(
                name="postgresql",
                status="healthy",
                latency_ms=round(latency, 2),
            )
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.error(f"Database health check failed: {e}")
        return DependencyStatus(
            name="postgresql",
            status="unhealthy",
            latency_ms=round(latency, 2),
            error=str(e),
        )


async def check_tgo_api() -> DependencyStatus:
    """Check TGO API connectivity."""
    import time
    import httpx
    from app.core.config import settings

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.api_url}/health")
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                return DependencyStatus(
                    name="tgo-api",
                    status="healthy",
                    latency_ms=round(latency, 2),
                )
            else:
                return DependencyStatus(
                    name="tgo-api",
                    status="unhealthy",
                    latency_ms=round(latency, 2),
                    error=f"HTTP {response.status_code}",
                )
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.warning(f"TGO API health check failed: {e}")
        return DependencyStatus(
            name="tgo-api",
            status="unhealthy",
            latency_ms=round(latency, 2),
            error=str(e),
        )


async def check_tgo_platform() -> DependencyStatus:
    """Check TGO Platform connectivity."""
    import time
    import httpx
    from app.core.config import settings

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.platform_url}/health")
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                return DependencyStatus(
                    name="tgo-platform",
                    status="healthy",
                    latency_ms=round(latency, 2),
                )
            else:
                return DependencyStatus(
                    name="tgo-platform",
                    status="unhealthy",
                    latency_ms=round(latency, 2),
                    error=f"HTTP {response.status_code}",
                )
    except Exception as e:
        latency = (time.time() - start) * 1000
        logger.warning(f"TGO Platform health check failed: {e}")
        return DependencyStatus(
            name="tgo-platform",
            status="unhealthy",
            latency_ms=round(latency, 2),
            error=str(e),
        )


@router.get("/health")
async def health_check() -> dict:
    """Simple health check endpoint for load balancers."""
    return {"status": "healthy", "service": "tgo-vision-agent"}


@router.get("/v1/health", response_model=HealthResponse)
async def health_check_v1() -> HealthResponse:
    """Detailed health check endpoint with dependency status."""
    from app.workers.worker_manager import get_worker_manager

    # Check dependencies concurrently
    import asyncio
    db_status, api_status, platform_status = await asyncio.gather(
        check_database(),
        check_tgo_api(),
        check_tgo_platform(),
    )

    dependencies = [db_status, api_status, platform_status]

    # Get worker count
    worker_manager = get_worker_manager()
    active_workers = len(worker_manager.list_active_workers())

    # Determine overall status
    unhealthy_count = sum(1 for d in dependencies if d.status == "unhealthy")
    if unhealthy_count == 0:
        overall_status = "healthy"
    elif db_status.status == "unhealthy":
        # Database is critical
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        service="tgo-vision-agent",
        version="v1",
        dependencies=dependencies,
        active_workers=active_workers,
    )


@router.get("/v1/health/ready")
async def readiness_check() -> dict:
    """Readiness check - verifies the service can handle requests.

    Returns 200 if ready, 503 if not ready.
    """
    from fastapi import HTTPException

    # Check database connectivity
    db_status = await check_database()
    if db_status.status == "unhealthy":
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "reason": "Database unavailable"},
        )

    return {"status": "ready", "service": "tgo-vision-agent"}


@router.get("/v1/health/live")
async def liveness_check() -> dict:
    """Liveness check - verifies the service is running.

    This is a simple check that always returns 200 if the service is up.
    """
    return {"status": "alive", "service": "tgo-vision-agent"}
