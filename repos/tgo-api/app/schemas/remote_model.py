from typing import List, Optional
from pydantic import Field
from app.schemas.base import BaseSchema

class RemoteModelInfo(BaseSchema):
    """Schema for a single remote model returned by provider API."""
    id: str = Field(..., description="Model identifier")
    name: Optional[str] = Field(None, description="Model display name")
    model_type: Optional[str] = Field(None, description="Model type (chat, embedding, etc.)")
    capabilities: Optional[dict] = Field(None, description="Model capabilities (e.g., vision)")

class RemoteModelListResponse(BaseSchema):
    """Schema for remote model list response."""
    provider: str = Field(..., description="Provider key")
    models: List[RemoteModelInfo] = Field(default_factory=list, description="List of available models")
    is_fallback: bool = Field(False, description="Whether these are fallback default models")
