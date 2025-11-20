"""System information schemas."""

from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class SystemInfoResponse(BaseSchema):
    """Response schema for system information endpoint."""

    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Current runtime environment")
    api_version: str = Field(..., description="API version (e.g., v1)")
    python_version: str = Field(..., description="Python runtime version")
    build_time: Optional[str] = Field(
        None,
        description="Build time in ISO8601 format or similar, if available",
    )
    git_commit: Optional[str] = Field(
        None,
        description="Git commit hash for the running build, if available",
    )

