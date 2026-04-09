"""Pydantic schemas for API request/response validation."""

from app.schemas.agent import (
    AgentCreate,
    AgentResponse,
    AgentToolCreate,
    AgentUpdate,
    AgentWithDetails,
)
from app.schemas.base import PaginationMetadata
from app.schemas.collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
)
from app.schemas.error import Error, ErrorDetail

__all__ = [
    # Base schemas
    "PaginationMetadata",
    "Error",
    "ErrorDetail",
    # Agent schemas
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentWithDetails",
    "AgentToolCreate",
    # Collection schemas
    "CollectionCreate",
    "CollectionUpdate",
    "CollectionResponse",
]
