"""Error response schemas."""

import uuid
from typing import Any, Dict, Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class ErrorDetail(BaseSchema):
    """Error detail information."""

    code: str = Field(description="Error code", examples=["AGENT_NOT_FOUND"])
    message: str = Field(
        description="Human-readable error message",
        examples=["The specified agent was not found"],
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error context and details",
        examples=[{"agent_id": "123e4567-e89b-12d3-a456-426614174000"}],
    )


class Error(BaseSchema):
    """Standard error response format."""

    error: ErrorDetail = Field(description="Error information")
    request_id: uuid.UUID = Field(
        description="Unique request identifier for tracking"
    )
