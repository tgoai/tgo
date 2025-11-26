from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, status, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select


from app.db.base import get_db
from app.db.models import Platform

router = APIRouter()


SUPPORTED_PLATFORM_TYPES = {"email", "website", "wechat", "wecom"}

EMAIL_CONFIG_EXAMPLE = {
    "imap_host": "imap.qq.com",
    "imap_port": 993,
    "imap_username": "412145540@qq.com",
    "imap_password": "bgokziotncvtbjee",
    "imap_use_ssl": True,
    "mailbox": "INBOX",
    "poll_interval_seconds": 60
}

WECOM_CONFIG_EXAMPLE = {
    "corp_id": "ww568541fa62117139",
    "agent_id": "1000003",
    "app_secret": "A8qLzHwTBuNoJMYCVcOo6YFsHkjZL7nrCIrm-kRMN9w",
    "token": "123456",
    "encoding_aes_key": "",
    "processing_batch_size": 10,
    "max_retry_attempts": 3,
    "consumer_poll_interval_seconds": 5
}

WUKONGIM_CONFIG_EXAMPLE = {
    # Consumer-only settings
    "processing_batch_size": 10,
    "max_retry_attempts": 3,
    "consumer_poll_interval_seconds": 5
}



class PlatformCreateRequest(BaseModel):
    """Request body for creating a platform (POST /v1/platforms)."""

    id: uuid.UUID | None = Field(default=None, description="Optional platform UUID; auto-generated if omitted")
    project_id: uuid.UUID = Field(..., description="Project/Tenant UUID")
    name: Optional[str] = Field(default=None, max_length=100, description="Optional platform display name")
    type: str = Field(..., max_length=20, description="Platform type, e.g., 'email', 'wecom', 'website'")
    config: dict[str, Any] | None = Field(
        default=None,
        description="Platform configuration (JSON)",
        json_schema_extra={"examples": [EMAIL_CONFIG_EXAMPLE, WECOM_CONFIG_EXAMPLE, WUKONGIM_CONFIG_EXAMPLE]},
    )
    is_active: bool = Field(default=True, description="Whether platform is active")
    api_key: str | None = Field(default=None, max_length=255, description="Optional API key")


class PlatformResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None = None
    type: str
    config: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    api_key: str | None = None



# ---------- Standardized Error Helper ----------
from app.api.error_utils import error_response
from app.api.schemas import ErrorResponse



@router.post("/v1/platforms", response_model=PlatformResponse, status_code=status.HTTP_200_OK, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def upsert_platform(body: PlatformCreateRequest, db: AsyncSession = Depends(get_db)) -> PlatformResponse:
    """Create or update a platform (upsert) and return the record.

    Behavior:
    - If `body.id` is provided and a platform with that ID exists (not deleted), update it.
    - If `body.id` is provided but no platform exists, create a new platform with that ID.
    - If `body.id` is omitted, create a new platform with a generated UUID.

    Notes:
    - Accepts any platform type (normalized to lowercase).
    - Returns 200 OK for both create and update cases (backward compatible path).
    """
    try:
        # Normalize platform type to lowercase
        platform_type = (body.type or "").strip().lower()

        existing = None
        if body.id is not None:
            existing = await db.scalar(
                select(Platform).where(Platform.id == body.id, Platform.deleted_at.is_(None))
            )

        if existing:
            # Update existing record
            existing.project_id = body.project_id
            existing.name = body.name
            existing.type = platform_type
            existing.config = body.config
            existing.is_active = bool(body.is_active)
            existing.api_key = body.api_key

            await db.commit()
            await db.refresh(existing)
            return PlatformResponse.model_validate(existing)
        else:
            # Create new record
            new_id = body.id or uuid.uuid4()
            platform = Platform(
                id=new_id,
                project_id=body.project_id,
                name=body.name,
                type=platform_type,
                config=body.config,
                is_active=bool(body.is_active),
                api_key=body.api_key,
            )
            db.add(platform)
            await db.commit()
            await db.refresh(platform)
            return PlatformResponse.model_validate(platform)
    except SQLAlchemyError as e:
        logging.error("DB error upserting platform: %s", e)
        await db.rollback()
        return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, code="DATABASE_ERROR", message="An error occurred while processing your request")


class PlatformUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=20)
    config: dict[str, Any] | None = Field(default=None, description="Platform configuration (JSON)", json_schema_extra={"example": EMAIL_CONFIG_EXAMPLE})
    is_active: bool | None = None
    api_key: str | None = Field(default=None, max_length=255)


@router.patch("/v1/platforms/{platform_id}", response_model=PlatformResponse, status_code=status.HTTP_200_OK, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def update_platform(platform_id: uuid.UUID, body: PlatformUpdateRequest, db: AsyncSession = Depends(get_db)) -> PlatformResponse:
    try:
        stmt = select(Platform).where(Platform.id == platform_id, Platform.deleted_at.is_(None))
        platform = await db.scalar(stmt)
        if not platform:
            return error_response(
                status.HTTP_404_NOT_FOUND,
                code="PLATFORM_NOT_FOUND",
                message="Platform with the specified ID does not exist",
            )

        if body.type is not None:
            # Normalize platform type to lowercase
            ptype = (body.type or "").strip().lower()
            platform.type = ptype

        if body.name is not None:
            platform.name = body.name
        if body.config is not None:
            platform.config = body.config
        if body.is_active is not None:
            platform.is_active = body.is_active
        if body.api_key is not None:
            platform.api_key = body.api_key

        await db.commit()
        await db.refresh(platform)
        return PlatformResponse.model_validate(platform)
    except SQLAlchemyError:
        await db.rollback()
        return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, code="DATABASE_ERROR", message="An error occurred while processing your request")


@router.delete("/v1/platforms/{platform_id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def delete_platform(platform_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Response:
    try:
        stmt = select(Platform).where(Platform.id == platform_id, Platform.deleted_at.is_(None))
        platform = await db.scalar(stmt)
        if not platform:
            return error_response(
                status.HTTP_404_NOT_FOUND,
                code="PLATFORM_NOT_FOUND",
                message="Platform with the specified ID does not exist",
            )

        platform.deleted_at = datetime.now(timezone.utc)
        platform.is_active = False

        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SQLAlchemyError:
        await db.rollback()
        return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, code="DATABASE_ERROR", message="An error occurred while processing your request")


