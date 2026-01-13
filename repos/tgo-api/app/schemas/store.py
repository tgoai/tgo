from typing import Optional
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
