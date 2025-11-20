"""System information endpoints."""

import os
import sys
from datetime import datetime

from fastapi import APIRouter

from app.__init__ import __version__
from app.core.config import settings
from app.schemas.system import SystemInfoResponse

router = APIRouter()


@router.get("/info", response_model=SystemInfoResponse, tags=["System"])
async def get_system_info() -> SystemInfoResponse:
    """Return basic system version and environment information.

    This endpoint is intentionally unauthenticated so that external systems
    can quickly inspect the running version/environment for diagnostics.
    """

    # Prefer explicit environment variable overrides when provided
    app_version = os.getenv("APP_VERSION", __version__)
    git_commit = os.getenv("GIT_COMMIT")
    build_time = os.getenv("BUILD_TIME")

    python_version = sys.version.split(" (")[0]

    return SystemInfoResponse(
        version=app_version,
        environment=settings.ENVIRONMENT,
        api_version=settings.API_V1_STR.lstrip("/"),
        python_version=python_version,
        build_time=build_time,
        git_commit=git_commit,
    )

