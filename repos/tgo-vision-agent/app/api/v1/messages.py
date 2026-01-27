"""Message sending and receiving API endpoints."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.services.message_service import MessageService

router = APIRouter()
logger = logging.getLogger(__name__)


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""

    platform_id: UUID = Field(..., description="Platform ID from tgo-api")
    app_type: str = Field(..., description="Application type: wechat, douyin, xiaohongshu, etc.")
    contact_id: str = Field(..., description="Contact ID within the application")
    content: str = Field(..., description="Message content to send")
    message_type: str = Field(default="text", description="Message type: text, image, etc.")


class SendMessageResponse(BaseModel):
    """Response body for send message operation."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class MessageRecord(BaseModel):
    """A single message record."""

    id: UUID
    platform_id: UUID
    app_type: str
    contact_id: str
    contact_name: str
    message_content: str
    message_type: str
    direction: str  # inbound or outbound
    status: str
    created_at: str


class MessageListResponse(BaseModel):
    """Response body for listing messages."""

    messages: list[MessageRecord]
    total: int
    has_more: bool


@router.post("/messages/send", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    """Send a message to a contact via UI automation.

    This will:
    1. Navigate to the contact's chat
    2. Type and send the message
    3. Verify the message was sent successfully
    """
    service = MessageService(db)

    try:
        result = await service.send_message(
            platform_id=request.platform_id,
            app_type=request.app_type,
            contact_id=request.contact_id,
            content=request.content,
            message_type=request.message_type,
        )

        return SendMessageResponse(
            success=result.get("success", False),
            message_id=result.get("message_id"),
            error=result.get("error"),
        )
    except ValueError as e:
        return SendMessageResponse(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return SendMessageResponse(
            success=False,
            error=f"Failed to send message: {e}",
        )


@router.get("/messages", response_model=MessageListResponse)
async def list_messages(
    platform_id: UUID,
    app_type: Optional[str] = None,
    contact_id: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    """List messages from the inbox."""
    service = MessageService(db)

    messages, total = await service.list_messages(
        platform_id=platform_id,
        app_type=app_type,
        contact_id=contact_id,
        direction=direction,
        status=status,
        limit=limit,
        offset=offset,
    )

    return MessageListResponse(
        messages=[
            MessageRecord(
                id=msg.id,
                platform_id=msg.platform_id,
                app_type=msg.app_type,
                contact_id=msg.contact_id,
                contact_name=msg.contact_name,
                message_content=msg.message_content,
                message_type=msg.message_type,
                direction=msg.direction,
                status=msg.status,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages
        ],
        total=total,
        has_more=offset + limit < total,
    )


@router.get("/messages/{message_id}", response_model=MessageRecord)
async def get_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MessageRecord:
    """Get a specific message by ID."""
    service = MessageService(db)

    message = await service.get_message(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    return MessageRecord(
        id=message.id,
        platform_id=message.platform_id,
        app_type=message.app_type,
        contact_id=message.contact_id,
        contact_name=message.contact_name,
        message_content=message.message_content,
        message_type=message.message_type,
        direction=message.direction,
        status=message.status,
        created_at=message.created_at.isoformat(),
    )
