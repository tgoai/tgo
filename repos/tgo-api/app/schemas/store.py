from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import Field, ConfigDict
from app.schemas.base import BaseSchema

class StoreCredentialBase(BaseSchema):
    store_user_id: str
    store_email: str

class StoreCredentialBind(StoreCredentialBase):
    api_key: str
    refresh_token: Optional[str] = None

class StoreCredential(StoreCredentialBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime

class StoreInstallRequest(BaseSchema):
    resource_id: str  # id of tool or model

class StoreInstallResponse(BaseSchema):
    id: UUID
    name: str
    status: str

class StoreBindRequest(BaseSchema):
    access_token: str

class StoreModelProvider(BaseSchema):
    id: str
    name: str
    slug: str
    icon: Optional[str] = None

class StoreModelDetail(BaseSchema):
    id: str
    name: str
    title_zh: Optional[str] = None
    title_en: Optional[str] = None
    description_zh: Optional[str] = None
    description_en: Optional[str] = None
    model_type: str
    input_price: float
    output_price: float
    context_window: Optional[int] = None
    provider: StoreModelProvider
    config: Optional[dict] = Field(default_factory=dict)
    is_installed: Optional[bool] = False

class StoreAgentDetail(BaseSchema):
    id: str
    name: str
    title: Optional[str] = None
    title_zh: str
    title_en: Optional[str] = None
    description: Optional[str] = None
    description_zh: Optional[str] = None
    description_en: Optional[str] = None
    avatar_url: Optional[str] = None
    instruction: str
    instruction_zh: Optional[str] = None
    instruction_en: Optional[str] = None
    model_id: Optional[str] = None
    model: Optional[StoreModelDetail] = None
    default_config: Optional[dict] = Field(default_factory=dict)
    recommended_tools: Optional[list] = Field(default_factory=list)
    price: float
    price_usd: Optional[float] = 0.0
    price_cny: Optional[float] = 0.0
    is_installed: Optional[bool] = False

class StoreToolSummary(BaseSchema):
    id: str
    name: str
    title_zh: Optional[str] = None
    price_per_call: float = 0

class AgentDependencyCheckResponse(BaseSchema):
    agent: StoreAgentDetail
    missing_tools: List[StoreToolSummary]
    missing_model: Optional[StoreModelDetail] = None

class StoreInstallAgentRequest(BaseSchema):
    resource_id: str
    install_tool_ids: Optional[List[str]] = Field(default_factory=list)
    install_model: Optional[bool] = False
