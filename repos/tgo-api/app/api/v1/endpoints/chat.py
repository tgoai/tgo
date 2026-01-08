"""Chat endpoints for messaging and AI completion."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import re
import secrets
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_active_user, verify_token, require_permission
from app.models import (
    ChannelMember,
    ChatFile,
    Platform,
    SessionStatus,
    Staff,
    Visitor,
    VisitorSession,
)
from app.schemas import ChatFileUploadResponse, StaffSendPlatformMessageRequest
from app.schemas.chat import (
    ChatCompletionRequest,
    StaffTeamChatRequest,
    StaffTeamChatResponse,
    OpenAIChatCompletionChunk,
    OpenAIChatCompletionChunkChoice,
    OpenAIChatCompletionChoice,
    OpenAIChatCompletionDelta,
    OpenAIChatCompletionRequest,
    OpenAIChatCompletionResponse,
    OpenAIChatCompletionUsage,
    OpenAIChatMessage,
)
from app.services import chat_service
from app.services.file_service import sanitize_filename, get_safe_ascii_filename
from app.services.chat_service import get_or_create_visitor
from app.services.transfer_service import transfer_to_staff
from app.models import AssignmentSource
from app.services.ai_client import AIServiceClient
from app.services.wukongim_client import wukongim_client
from app.utils.const import CHANNEL_TYPE_CUSTOMER_SERVICE, MEMBER_TYPE_STAFF
from app.utils.encoding import build_visitor_channel_id, parse_visitor_channel_id


router = APIRouter()


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/completion",
    summary="流式聊天完成接口",
    tags=["Chat"],
    description="""
## 概述
访客聊天接口，支持 Server-Sent Events (SSE) 流式响应和非流式 JSON 响应。

## 认证方式
通过请求体中的 `api_key` 字段传递平台 API Key。

## 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| api_key | string | ✅ | 平台 API Key |
| message | string | ✅ | 用户消息内容 |
| from_uid | string | ✅ | 平台用户唯一标识 |
| extra | object | ❌ | 额外数据（会随消息转发） |
| timeout_seconds | int | ❌ | 超时时间（默认120秒） |
| channel_id | string | ❌ | 自定义频道ID |
| channel_type | int | ❌ | 频道类型（默认251=客服） |
| system_message | string | ❌ | AI系统提示词 |
| expected_output | string | ❌ | 期望的输出格式描述 |
| wukongim_only | bool | ❌ | 是否仅发送到WuKongIM不返回流（默认false） |
| stream | bool | ❌ | 是否使用流式响应（默认true）。false返回完整JSON |

## 响应模式

### 1. 流式响应（stream=true，默认）
返回 `text/event-stream` 格式的 SSE 流。

### 2. 非流式响应（stream=false）
返回 JSON 格式的完整响应：
```json
{
  "success": true,
  "message": "AI回复的完整内容...",
  "visitor_id": "访客UUID"
}
```

## SSE 响应事件类型（仅 stream=true 时）

### 成功事件
| event_type | 说明 | data 结构 |
|------------|------|-----------|
| `team_run_started` | AI开始处理 | `{}` |
| `team_run_content` | AI输出内容块 | `{"content": "文本块"}` |
| `team_run_completed` | AI处理完成 | `{}` |
| `workflow_completed` | AI处理完成 | `{}` |
| `accepted` | 请求已接受（wukongim_only=true时） | `{"message": "Request accepted..."}` |

### 错误/状态事件
| event_type | 说明 | data 结构 |
|------------|------|-----------|
| `error` | 发生错误 | `{"message": "错误信息", "visitor_id": "..."}` |
| `queued` | 访客已加入等待队列（无可用客服） | `{"message": "...", "visitor_id": "...", "queue_position": 1}` |
| `ai_disabled` | AI已禁用 | `{"message": "AI responses are disabled..."}` |
| `assist_mode` | AI处于辅助模式（人工优先） | `{"message": "Human service requested, AI is in assist mode"}` |
| `workflow_failed` | AI工作流执行失败 | `{"message": "错误详情"}` |

## 错误场景

### 1. 无效的 API Key
返回 HTTP 401:
```json
{"detail": "Invalid platform API key"}
```

### 2. 平台未关联项目
返回 HTTP 400:
```json
{"detail": "Platform not associated with any project"}
```

### 3. 客服分配失败

**stream=true（SSE）:**
```
data: {"event_type": "error", "data": {"success": false, "event_type": "error", "message": "...", "visitor_id": "..."}}
```

**stream=false（JSON）:**
```json
{"success": false, "event_type": "error", "message": "Transfer failed: ...", "visitor_id": "..."}
```

### 4. 无可用客服（已加入队列）

**stream=true（SSE）:**
```
data: {"event_type": "queued", "data": {"success": false, "message": "...", "visitor_id": "...", "queue_position": 1}}
```

**stream=false（JSON）:**
```json
{"success": false, "event_type": "queued", "message": "Added to waiting queue at position 1", "visitor_id": "...", "queue_position": 1}
```

### 5. 无分配客服

**stream=true（SSE）:**
```
data: {"event_type": "error", "data": {"message": "No staff assigned to this visitor", "visitor_id": "..."}}
```

**stream=false（HTTP 503）:**
```json
{"detail": {"success": false, "event_type": "error", "message": "No staff assigned to this visitor", "visitor_id": "..."}}
```

### 6. AI已禁用

**stream=true（SSE）:**
```
data: {"event_type": "ai_disabled", "data": {"message": "AI responses are disabled..."}}
```

**stream=false（HTTP 403）:**
```json
{"detail": {"success": false, "event_type": "ai_disabled", "message": "AI responses are disabled..."}}
```

### 7. AI服务错误

**stream=true（SSE）:**
```
data: {"event_type": "error", "data": {"message": "AI service error: ..."}}
```

**stream=false（HTTP 500）:**
```json
{"detail": "AI service error: ..."}
```

## SSE 响应格式示例
```
data: {"event_type": "team_run_started", "data": {}}

data: {"event_type": "team_run_content", "data": {"content": "你好"}}

data: {"event_type": "team_run_content", "data": {"content": "，有什么"}}

data: {"event_type": "team_run_content", "data": {"content": "可以帮助您的？"}}

data: {"event_type": "workflow_completed", "data": {}}
```

## 前端使用示例
```javascript
const eventSource = new EventSource('/api/v1/chat/completion', {
  method: 'POST',
  body: JSON.stringify({
    api_key: 'your-api-key',
    message: '你好',
    from_uid: 'user123'
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.event_type) {
    case 'team_run_content':
      // 追加内容到界面
      appendText(data.data.content);
      break;
    case 'workflow_completed':
      // 完成处理
      eventSource.close();
      break;
    case 'error':
    case 'queued':
      // 处理错误或排队状态
      handleError(data.data);
      eventSource.close();
      break;
  }
};
```
""",
    responses={
        200: {
            "description": "成功响应（流式或JSON）",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"event_type": "team_run_content", "data": {"content": "你好"}}\n\n'
                },
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "你好，有什么可以帮助您的？",
                        "visitor_id": "550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            }
        },
        401: {"description": "无效的 API Key"},
        400: {"description": "平台未关联项目"},
        500: {"description": "AI服务错误（stream=false时）"},
        503: {"description": "无可用客服"},
    }
)
async def chat_completion(req: ChatCompletionRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    """流式聊天完成接口 - 详细说明请查看接口描述。"""
    # 1) Validate Platform API key and get project
    platform, project = chat_service.validate_platform_and_project(req.api_key, db)

    # 2) Get or create visitor (handles status reset if CLOSED)
    visitor, visitor_changed = await get_or_create_visitor(
        db=db,
        platform=platform,
        platform_open_id=req.from_uid,
        nickname=req.visitor_name,
        avatar_url=req.visitor_avatar,
    )

    if visitor_changed:
        # Notify visitor profile updated - need to build channel_id first
        channel_id_for_update = build_visitor_channel_id(visitor.id)
        await wukongim_client.send_visitor_profile_updated(
            visitor_id=str(visitor.id),
            channel_id=channel_id_for_update,
            channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
        )

    # 3) Prepare correlation and session IDs
    if req.channel_id:
        channel_id_enc = req.channel_id
    else:
        channel_id_enc = build_visitor_channel_id(visitor.id)

    channel_type = req.channel_type if req.channel_type is not None else CHANNEL_TYPE_CUSTOMER_SERVICE
    session_id = f"{channel_id_enc}@{channel_type}"

    # 3.1) Resolve relative image/file URLs if present
    if req.msg_type in {2, 3} and req.message.startswith("/"):
        base_url = settings.API_BASE_URL.rstrip("/")
        req.message = f"{base_url}{req.message}"

    # 3.2) Forward a copy of user message to WuKongIM (best-effort)
    if req.forward_user_message_to_wukongim:
        await chat_service.send_user_message_to_wukongim(
            from_uid=f"{visitor.id}-vtr",
            channel_id=channel_id_enc,
            channel_type=channel_type,
            content=req.message,
            msg_type=req.msg_type,
            extra=req.extra,
        )

    # 3.5) If visitor is unassigned, try to assign staff
    assigned_staff_id = None
    if visitor.is_unassigned:
        transfer_result = await transfer_to_staff(
            db=db,
            visitor_id=visitor.id,
            project_id=project.id,
            source=AssignmentSource.RULE,
            visitor_message=req.message,
            add_to_queue_if_no_staff=True,
            ai_disabled=visitor.ai_disabled,
        )
        
        # Return error response if transfer failed
        if not transfer_result.success:
            error_data = {
                "success": False,
                "event_type": "error",
                "message": transfer_result.message,
                "visitor_id": str(visitor.id),
            }
            if req.stream is False:
                return error_data
            async def transfer_error_gen():
                yield chat_service.sse_format({"event_type": "error", "data": error_data})
            return StreamingResponse(transfer_error_gen(), media_type="text/event-stream")
        
        # Check if staff was assigned
        if not transfer_result.assigned_staff_id:
            queued_data = {
                "success": False,
                "event_type": "queued",
                "message": transfer_result.message,
                "visitor_id": str(visitor.id),
                "queue_position": transfer_result.queue_position,
            }
            if req.stream is False:
                return queued_data
            async def no_staff_gen():
                yield chat_service.sse_format({"event_type": "queued", "data": queued_data})
            return StreamingResponse(no_staff_gen(), media_type="text/event-stream")
        
        assigned_staff_id = transfer_result.assigned_staff_id
        
        # Notify visitor profile updated on successful transfer
        await wukongim_client.send_visitor_profile_updated(
            visitor_id=str(visitor.id),
            channel_id=channel_id_enc,
            channel_type=channel_type,
        )

    # 4) Prepare from_uid for WuKongIM forwarding (must have assigned staff)
    if assigned_staff_id:
        wukongim_from_uid = f"{assigned_staff_id}-staff"
    else:
        # Check if visitor has an open session with assigned staff
        open_session = db.query(VisitorSession).filter(
            VisitorSession.visitor_id == visitor.id,
            VisitorSession.status == SessionStatus.OPEN.value,
            VisitorSession.staff_id.isnot(None),
        ).first()
        
        if open_session and open_session.staff_id:
            wukongim_from_uid = f"{open_session.staff_id}-staff"
        else:
            # No staff assigned - return error
            error_data = {
                "success": False,
                "event_type": "error",
                "message": "No staff assigned to this visitor",
                "visitor_id": str(visitor.id),
            }
            if req.stream is False:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=error_data
                )
            async def no_staff_error_gen():
                yield chat_service.sse_format({"event_type": "error", "data": error_data})
            return StreamingResponse(no_staff_error_gen(), media_type="text/event-stream")

    # 5) Check AI disabled status (removed auto-recovery logic - should only be triggered by explicit staff action or platform setting change)
    # 5.1) Check AI disabled status
    ai_disabled = chat_service.is_ai_disabled(platform, visitor)
    
    # 6) If AI is disabled, return appropriate response
    if ai_disabled:
        # Check if this is specifically assist mode (visitor not explicitly disabled)
        is_assist_mode = (
            getattr(visitor, "ai_disabled", None) is None
            and getattr(platform, "ai_mode", None) == "assist"
        )
        event_type = "assist_mode" if is_assist_mode else "ai_disabled"
        message = (
            "Human service requested, AI is in assist mode (requires staff response)" 
            if is_assist_mode 
            else "AI responses are disabled for this visitor/platform (check platform settings)"
        )
        
        error_data = {
            "success": False,
            "event_type": event_type,
            "message": message,
        }
        if req.stream is False:
            return error_data
        async def disabled_gen():
            yield chat_service.sse_format({"event_type": event_type, "data": error_data})
        return StreamingResponse(disabled_gen(), media_type="text/event-stream")

    # 7) AI is enabled: directly call AI service and stream response
    team_id = str(project.default_team_id) if project.default_team_id else "default"
    response_client_msg_no = f"ai_{uuid4().hex}"

    # Update visitor last message stats
    visitor.is_last_message_from_ai = True
    visitor.is_last_message_from_visitor = False
    visitor.last_client_msg_no = response_client_msg_no
    db.add(visitor)
    db.commit()

    # Prepare agent_ids from platform
    platform_agent_ids = [str(aid) for aid in platform.agent_ids] if platform.agent_ids else None

    # 8) If wukongim_only=True, start background processing and wait for team_run_started
    if req.wukongim_only:
        # Create an event to signal when AI processing has started
        started_event = asyncio.Event()
        
        # Start background task with the event
        asyncio.create_task(chat_service.run_background_ai_interaction(
            project_id=str(project.id),
            visitor_id=str(visitor.id),
            message=req.message,
            channel_id=channel_id_enc,
            channel_type=channel_type,
            client_msg_no=response_client_msg_no,
            from_uid=wukongim_from_uid,
            session_id=session_id,
            team_id=team_id,
            system_message=req.system_message,
            expected_output=req.expected_output,
            agent_ids=platform_agent_ids,
            started_event=started_event,
        ))
        
        # Wait for team_run_started event (with timeout)
        try:
            await asyncio.wait_for(started_event.wait(), timeout=req.timeout_seconds or 30)
        except asyncio.TimeoutError:
            error_data = {
                "success": False,
                "event_type": "error",
                "message": "AI processing start timeout",
                "visitor_id": str(visitor.id),
            }
            if req.stream is False:
                return error_data
            async def timeout_gen():
                yield chat_service.sse_format({"event_type": "error", "data": error_data})
            return StreamingResponse(timeout_gen(), media_type="text/event-stream")
        
        accepted_data = {
            "success": True,
            "event_type": "accepted",
            "message": "Request accepted, AI processing started",
            "visitor_id": str(visitor.id),
        }
        if req.stream is False:
            return accepted_data
        async def accepted_gen():
            yield chat_service.sse_format({"event_type": "accepted", "data": accepted_data})
        return StreamingResponse(accepted_gen(), media_type="text/event-stream")

    # 9) Check stream mode
    if req.stream is False:
        result = await chat_service.handle_ai_response_non_stream(
            project_id=str(project.id),
            visitor_id=str(visitor.id),
            message=req.message,
            channel_id=channel_id_enc,
            channel_type=channel_type,
            client_msg_no=response_client_msg_no,
            from_uid=wukongim_from_uid,
            session_id=session_id,
            team_id=team_id,
            system_message=req.system_message,
            expected_output=req.expected_output,
            agent_ids=platform_agent_ids,
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "AI processing failed")
            )
            
        return {
            "success": True,
            "message": result["content"],
            "visitor_id": str(visitor.id),
        }

    # 10) Streaming mode: stream response to client
    async def ai_event_generator() -> Any:
        async for event_payload in chat_service.process_ai_stream_to_wukongim(
            project_id=str(project.id),
            visitor_id=str(visitor.id),
            message=req.message,
            channel_id=channel_id_enc,
            channel_type=channel_type,
            client_msg_no=response_client_msg_no,
            from_uid=wukongim_from_uid,
            session_id=session_id,
            team_id=team_id,
            system_message=req.system_message,
            expected_output=req.expected_output,
            agent_ids=platform_agent_ids,
        ):
            yield chat_service.sse_format(event_payload)

    return StreamingResponse(ai_event_generator(), media_type="text/event-stream")


@router.post(
    "/messages/send",
    tags=["Chat"],
    summary="Send message via platform service",
    description=(
        "Forward a staff-authenticated outbound message to the Platform Service "
        "(`/v1/messages/send`). This endpoint enriches the payload with the platform API key "
        "and staff identifier and returns the Platform Service response."
    ),
)
async def staff_send_platform_message(
    req: StaffSendPlatformMessageRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("chat:send")),
) -> Response:
    """Send message via platform service. Requires chat:send permission."""
    if req.channel_type != CHANNEL_TYPE_CUSTOMER_SERVICE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only customer service channels (type 251) are supported",
        )

    try:
        visitor_uuid = parse_visitor_channel_id(req.channel_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel_id format")

    membership = (
        db.query(ChannelMember)
        .filter(
            ChannelMember.channel_id == req.channel_id,
            ChannelMember.channel_type == req.channel_type,
            ChannelMember.member_id == current_user.id,
            ChannelMember.member_type == MEMBER_TYPE_STAFF,
            ChannelMember.deleted_at.is_(None),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff not assigned to this channel")

    visitor = (
        db.query(Visitor)
        .options(joinedload(Visitor.platform))
        .filter(
            Visitor.id == visitor_uuid,
            Visitor.project_id == current_user.project_id,
            Visitor.deleted_at.is_(None),
        )
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    platform = visitor.platform
    if not platform or platform.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visitor platform is unavailable")
    if not platform.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Visitor platform is disabled")
    if not platform.api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Platform API key is missing")
    if platform.project_id != current_user.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for visitor platform")

    target_url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/v1/messages/send"
    outbound_payload: Dict[str, Any] = {
        "platform_api_key": platform.api_key,
        "from_uid": f"{current_user.id}-staff",
        "platform_open_id": visitor.platform_open_id,
        "channel_id": req.channel_id,
        "channel_type": req.channel_type,
        "payload": req.payload,
        "client_msg_no": req.client_msg_no or f"staff_{uuid4().hex}",
    }

    headers = {"Content-Type": "application/json"}
    if settings.PLATFORM_SERVICE_API_KEY:
        headers["Authorization"] = f"Bearer {settings.PLATFORM_SERVICE_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=settings.PLATFORM_SERVICE_TIMEOUT) as client:
            resp = await client.post(target_url, json=outbound_payload, headers=headers)
    except httpx.TimeoutException:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Platform Service timeout")
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Platform Service request error: {exc}",
        )

    hop_by_hop = {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade", "content-length",
    }
    passthrough_headers = {k: v for k, v in resp.headers.items() if k.lower() not in hop_by_hop}
    media_type = resp.headers.get("content-type")
    return Response(content=resp.content, status_code=resp.status_code, headers=passthrough_headers, media_type=media_type)


@router.post("/upload", response_model=ChatFileUploadResponse, tags=["Chat"])
async def chat_file_upload(
    file: UploadFile = File(...),
    channel_id: str = Form(...),
    channel_type: int = Form(...),
    platform_api_key: Optional[str] = Form(None),
    x_platform_api_key: Optional[str] = Header(None, alias="X-Platform-API-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Upload a file for a chat channel with dual authentication support."""
    # 1) Authenticate: JWT staff or platform_api_key
    plat_key = platform_api_key or x_platform_api_key
    current_user, platform = chat_service.authenticate_staff_or_platform(db, credentials, plat_key)

    if not current_user and not platform:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Determine project context
    if current_user:
        project_id = current_user.project_id
        uploaded_by = current_user.username
    else:
        assert platform is not None
        project_id = platform.project_id
        uploaded_by = "visitor"

    # 2) Access validation by channel
    if channel_type == CHANNEL_TYPE_CUSTOMER_SERVICE:
        try:
            visitor_uuid = parse_visitor_channel_id(channel_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel_id format")

        visitor = (
            db.query(Visitor)
            .filter(Visitor.id == visitor_uuid, Visitor.deleted_at.is_(None))
            .first()
        )
        if not visitor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

        if platform:
            if visitor.platform_id != platform.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform not authorized for channel")
        else:
            if visitor.project_id != project_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to channel")

    elif channel_type == 1:
        if channel_id.endswith("-staff"):
            if not current_user:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform cannot upload to staff channel")
            staff_id_str = channel_id[:-6]
            try:
                if UUID(staff_id_str) != current_user.id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to staff channel")
            except Exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid staff channel_id")
        else:
            try:
                vis_uuid = UUID(channel_id)
            except Exception:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visitor channel_id")
            visitor = db.query(Visitor).filter(Visitor.id == vis_uuid, Visitor.deleted_at.is_(None)).first()
            if not visitor or visitor.project_id != project_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to visitor channel")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported channel_type")

    # 3) Validate file type/size
    allowed_exts = set(settings.ALLOWED_UPLOAD_EXTENSIONS or [])
    original_name = file.filename or "upload.bin"
    sanitized_name = sanitize_filename(original_name)
    ext = sanitized_name.rsplit(".", 1)[-1].lower() if "." in sanitized_name else ""

    mime = file.content_type or mimetypes.guess_type(sanitized_name)[0] or "application/octet-stream"

    if allowed_exts:
        if not ext or ext not in allowed_exts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed")
    else:
        if settings.ALLOWED_FILE_TYPES and mime not in set(settings.ALLOWED_FILE_TYPES):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MIME type not allowed")

    max_bytes = int(settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024 if settings.MAX_UPLOAD_SIZE_MB else int(settings.MAX_FILE_SIZE)

    # 4) Build storage path
    ts_ms = int(time.time() * 1000)
    rand = secrets.token_hex(4)
    fname = f"{ts_ms}_{rand}_{sanitized_name}"

    date_dir = time.strftime("%Y-%m-%d")
    rel_path = f"chat/{project_id}/{channel_type}/{channel_id}/{date_dir}/{fname}"
    base_dir = Path(settings.UPLOAD_BASE_DIR).resolve()
    dest_path = base_dir / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 5) Save file in chunks
    total = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    try:
                        out.flush()
                        out.close()
                    finally:
                        try:
                            os.unlink(dest_path)
                        except Exception:
                            pass
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        try:
            if dest_path.exists():
                os.unlink(dest_path)
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"File storage failed: {e}")

    # 6) Persist metadata
    chat_file = ChatFile(
        project_id=project_id,
        channel_id=channel_id,
        channel_type=channel_type,
        file_name=original_name,
        file_path=rel_path,
        file_size=total,
        file_type=mime,
        uploaded_by_staff_id=(current_user.id if current_user else None),
        uploaded_by_platform_id=(platform.id if platform else None),
    )
    db.add(chat_file)
    db.commit()
    db.refresh(chat_file)

    # 7) Build response
    return ChatFileUploadResponse(
        file_id=str(chat_file.id),
        file_name=original_name,
        file_size=total,
        file_type=mime,
        file_url=f"/v1/chat/files/{chat_file.id}",
        channel_id=channel_id,
        channel_type=channel_type,
        uploaded_at=chat_file.created_at,
        uploaded_by=uploaded_by,
    )


@router.get("/files/{file_id}", tags=["Chat"])
async def get_chat_file(
    file_id: UUID,
    platform_api_key: Optional[str] = None,
    x_platform_api_key: Optional[str] = Header(None, alias="X-Platform-API-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Serve an uploaded chat file by ID.

    - Public access allowed by default
    - If auth is provided (JWT or platform API key), validate access to the channel
    """
    # 1) Lookup file metadata
    chat_file = (
        db.query(ChatFile)
        .filter(ChatFile.id == file_id, ChatFile.deleted_at.is_(None))
        .first()
    )
    if not chat_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # 2) Optional auth/access validation
    plat_key = platform_api_key or x_platform_api_key
    current_user, platform = chat_service.authenticate_staff_or_platform(db, credentials, plat_key)

    if current_user and chat_file.project_id != current_user.project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to file")

    if platform and not current_user:
        if chat_file.channel_type == CHANNEL_TYPE_CUSTOMER_SERVICE:
            try:
                visitor_uuid = parse_visitor_channel_id(chat_file.channel_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file channel encoding")
            visitor = (
                db.query(Visitor)
                .filter(Visitor.id == visitor_uuid, Visitor.deleted_at.is_(None))
                .first()
            )
            if not visitor:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")
            if visitor.platform_id != platform.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform not authorized for file")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform cannot access this file")

    # If provided but invalid platform key
    if plat_key and not platform and not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform_api_key")

    # 3) Build path and return FileResponse
    base_dir = Path(settings.UPLOAD_BASE_DIR).resolve()
    file_path = (base_dir / chat_file.file_path).resolve()
    try:
        file_path.relative_to(base_dir)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid file path")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing from storage")

    # Build headers
    ascii_name = get_safe_ascii_filename(chat_file.file_name, str(chat_file.id))
    quoted_safe_name = quote(chat_file.file_name or file_path.name, safe="")

    headers = {
        "Content-Disposition": f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted_safe_name}",
        "Content-Length": str(chat_file.file_size or file_path.stat().st_size),
    }

    return FileResponse(
        path=str(file_path),
        media_type=chat_file.file_type or "application/octet-stream",
        headers=headers,
    )


@router.post(
    "/completions",
    summary="OpenAI-compatible chat completion",
    tags=["Chat"],
    description="""
    OpenAI ChatGPT API-compatible chat completion endpoint.

    This endpoint provides a fully compatible interface with OpenAI's ChatGPT API,
    allowing seamless integration with existing OpenAI client libraries and tools.

    **Authentication**: Use Platform API Key via `X-Platform-API-Key` header.

    **Request Format**: Compatible with OpenAI's chat completion request format.
    See: https://platform.openai.com/docs/api-reference/chat/create

    **Response Format**: Compatible with OpenAI's chat completion response format.
    See: https://platform.openai.com/docs/api-reference/chat/object

    **Streaming Support**: Set `stream=true` to receive Server-Sent Events (SSE).
    See: https://platform.openai.com/docs/api-reference/chat/streaming
    """,
)
async def chat_completion_openai_compatible(
    req: OpenAIChatCompletionRequest,
    x_platform_api_key: str = Header(..., alias="X-Platform-API-Key"),
    db: Session = Depends(get_db),
):
    """OpenAI-compatible chat completion endpoint."""
    # 1) Validate Platform API key and get project
    platform, project = chat_service.validate_platform_and_project(x_platform_api_key, db)

    # 2) Extract messages from OpenAI format
    user_message, system_message, platform_open_id = chat_service.extract_messages_from_openai_format(
        req.messages, req.user
    )

    # 3) Get or create visitor (handles status reset if CLOSED)
    visitor, visitor_changed = await get_or_create_visitor(
        db=db,
        platform=platform,
        platform_open_id=platform_open_id,
        nickname=req.user,
    )
    
    if visitor_changed:
        # Notify visitor profile updated - need to build channel_id first
        channel_id_for_update = build_visitor_channel_id(visitor.id)
        await wukongim_client.send_visitor_profile_updated(
            visitor_id=str(visitor.id),
            channel_id=channel_id_for_update,
            channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
        )

    # 4) Prepare correlation and session IDs
    client_msg_no = f"openai_{uuid4().hex}"
    channel_id_enc = build_visitor_channel_id(visitor.id)
    channel_type = CHANNEL_TYPE_CUSTOMER_SERVICE
    session_id = f"{channel_id_enc}@{channel_type}"

    # 4.2) Forward a copy of user message to WuKongIM (best-effort)
    await chat_service.send_user_message_to_wukongim(
        from_uid=f"{visitor.id}-vtr",
        channel_id=channel_id_enc,
        channel_type=channel_type,
        content=user_message,
        extra=None,
    )

    # 5) If visitor is unassigned, try to assign staff
    assigned_staff_id = None
    if visitor.is_unassigned:
        transfer_result = await transfer_to_staff(
            db=db,
            visitor_id=visitor.id,
            project_id=project.id,
            source=AssignmentSource.RULE,
            visitor_message=user_message,
            add_to_queue_if_no_staff=True,
            ai_disabled=visitor.ai_disabled,
        )
        
        if not transfer_result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transfer failed: {transfer_result.message}"
            )
        
        # Check if staff was assigned
        if not transfer_result.assigned_staff_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No staff available. {transfer_result.message}"
            )
        
        assigned_staff_id = transfer_result.assigned_staff_id
        
        # Notify visitor profile updated on successful transfer
        await wukongim_client.send_visitor_profile_updated(
            visitor_id=str(visitor.id),
            channel_id=channel_id_enc,
            channel_type=channel_type,
        )

    # 6) Prepare from_uid for WuKongIM forwarding (must have assigned staff)
    if assigned_staff_id:
        wukongim_from_uid = f"{assigned_staff_id}-staff"
    else:
        # Check if visitor has an open session with assigned staff
        open_session = db.query(VisitorSession).filter(
            VisitorSession.visitor_id == visitor.id,
            VisitorSession.status == SessionStatus.OPEN.value,
            VisitorSession.staff_id.isnot(None),
        ).first()
        
        if open_session and open_session.staff_id:
            wukongim_from_uid = f"{open_session.staff_id}-staff"
        else:
            # No staff assigned - return error
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No staff assigned to this visitor"
            )

    # 7) Check AI disabled status
    ai_disabled = chat_service.is_ai_disabled(platform, visitor)
    
    if ai_disabled:
        # Check if this is specifically assist mode (visitor not explicitly disabled)
        is_assist_mode = (
            getattr(visitor, "ai_disabled", None) is None
            and getattr(platform, "ai_mode", None) == "assist"
        )
        status_code = status.HTTP_202_ACCEPTED if is_assist_mode else status.HTTP_403_FORBIDDEN
        detail = (
            "Human service requested, AI is in assist mode (requires staff response)" 
            if is_assist_mode 
            else "AI responses are disabled for this visitor/platform (check platform settings)"
        )
        raise HTTPException(
            status_code=status_code,
            detail=detail
        )

    # 8) Call AI service directly
    team_id = str(project.default_team_id) if project.default_team_id else "default"
    response_client_msg_no = f"ai_{uuid4().hex}"

    # Update visitor last message stats
    visitor.is_last_message_from_ai = True
    visitor.is_last_message_from_visitor = False
    visitor.last_client_msg_no = response_client_msg_no
    db.add(visitor)
    db.commit()
    
    # Prepare agent_ids from platform
    platform_agent_ids = [str(aid) for aid in platform.agent_ids] if platform.agent_ids else None

    # 9) Generate completion ID and timestamp
    completion_id = f"chatcmpl-{uuid4().hex[:24]}"
    created_timestamp = int(time.time())
    model_name = "tgo-ai"

    # 10) Handle streaming vs non-streaming response
    if req.stream:
        async def openai_stream_generator():
            try:
                async for event_payload in chat_service.process_ai_stream_to_wukongim(
                    project_id=str(project.id),
                    visitor_id=str(visitor.id),
                    message=user_message,
                    channel_id=channel_id_enc,
                    channel_type=channel_type,
                    client_msg_no=response_client_msg_no,
                    from_uid=wukongim_from_uid,
                    session_id=session_id,
                    team_id=team_id,
                    system_message=system_message,
                    agent_ids=platform_agent_ids,
                ):
                    event_type = event_payload.get("event_type")
                    data = event_payload.get("data") or {}

                    if event_type == "team_run_content":
                        chunk_text = data.get("content")
                        if chunk_text:
                            chunk = OpenAIChatCompletionChunk(
                                id=completion_id,
                                created=created_timestamp,
                                model=model_name,
                                choices=[
                                    OpenAIChatCompletionChunkChoice(
                                        index=0,
                                        delta=OpenAIChatCompletionDelta(content=chunk_text),
                                        finish_reason=None,
                                    )
                                ],
                            )
                            yield f"data: {chunk.model_dump_json()}\n\n"
                    elif event_type in ("workflow_completed", "team_run_completed"):
                        final_chunk = OpenAIChatCompletionChunk(
                            id=completion_id,
                            created=created_timestamp,
                            model=model_name,
                            choices=[
                                OpenAIChatCompletionChunkChoice(
                                    index=0,
                                    delta=OpenAIChatCompletionDelta(),
                                    finish_reason="stop",
                                )
                            ],
                        )
                        yield f"data: {final_chunk.model_dump_json()}\n\n"
                        yield "data: [DONE]\n\n"
                        break

            except Exception as e:
                error_chunk = {"error": {"message": str(e), "type": "server_error"}}
                yield f"data: {json.dumps(error_chunk)}\n\n"

        return StreamingResponse(
            openai_stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    # 11) Non-streaming response - collect all content
    result = await chat_service.handle_ai_response_non_stream(
        project_id=str(project.id),
        visitor_id=str(visitor.id),
        message=user_message,
        channel_id=channel_id_enc,
        channel_type=channel_type,
        client_msg_no=response_client_msg_no,
        from_uid=wukongim_from_uid,
        session_id=session_id,
        team_id=team_id,
        system_message=system_message,
        agent_ids=platform_agent_ids,
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "AI processing failed")
        )

    # 12) Estimate token usage and build response
    prompt_tokens, completion_tokens, total_tokens = chat_service.estimate_token_usage(
        req.messages, result["content"]
    )

    return chat_service.build_openai_completion_response(
        completion_id=completion_id,
        created_timestamp=created_timestamp,
        model=model_name,
        completion_text=result["content"],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens
    )


@router.post(
    "/team",
    response_model=StaffTeamChatResponse,
    summary="Staff chat with AI team or agent",
    tags=["Chat"],
    description="""
    Staff-to-team/agent chat endpoint.

    This endpoint allows authenticated staff members to chat with AI teams or agents.
    The AI response is delivered via WuKongIM to the client.

    **Authentication**: JWT token required (staff authentication).

    **Request**: Either `team_id` or `agent_id` must be provided (exactly one).

    **Channel Format**:
    - If `team_id` is provided: channel_id = `{team_id}-team`
    - If `agent_id` is provided: channel_id = `{agent_id}-agent`

    **Response Delivery**: AI response is sent via WuKongIM, not returned in this endpoint.
    This endpoint returns success/failure status after initiating AI processing.
    """,
)
async def staff_team_chat(
    req: StaffTeamChatRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("chat:send")),
) -> StaffTeamChatResponse:
    """Staff chat with AI team or agent. Requires chat:send permission.

    - Auth: JWT token (staff authentication)
    - Behavior: Directly calls AI service and forwards response to WuKongIM
    - Output: Success/failure status (AI response delivered via WuKongIM)
    """
    # 1) Get project info
    project = current_user.project
    if not project or not project.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff is not linked to a valid project"
        )

    # 2) Build channel identifiers based on team_id or agent_id
    if req.team_id:
        channel_id = f"{req.team_id}-team"
        target_team_id = str(req.team_id)
        target_agent_id = None
    else:
        channel_id = f"{req.agent_id}-agent"
        target_team_id = str(project.default_team_id) if project.default_team_id else None
        target_agent_id = str(req.agent_id)

    channel_type = 1  # Personal channel type

    # 3) Prepare correlation and session IDs
    client_msg_no = f"staff_team_{uuid4().hex}"
    session_id = f"{channel_id}@{channel_type}"

    # 4) Build from_uid for staff
    staff_uid = f"{current_user.id}-staff"

    # 4.1) Forward a copy of staff message to WuKongIM (best-effort)
    await chat_service.send_user_message_to_wukongim(
        from_uid=staff_uid,
        channel_id=channel_id,
        channel_type=channel_type,
        content=req.message,
        extra=None,
    )

    # 5) Directly call AI service and forward to WuKongIM in background
    # AI result sender should be team/agent (not current staff)
    ai_sender_uid = channel_id
    
    asyncio.create_task(chat_service.run_background_ai_interaction(
        project_id=str(current_user.project_id),
        visitor_id=staff_uid,
        message=req.message,
        channel_id=staff_uid,
        channel_type=channel_type,
        client_msg_no=client_msg_no,
        from_uid=ai_sender_uid,
        session_id=session_id,
        team_id=target_team_id,
        system_message=req.system_message,
        expected_output=req.expected_output,
        agent_id=target_agent_id,
        agent_ids=None,
    ))

    # 6) Return success response immediately
    return StaffTeamChatResponse(
        success=True,
        message="Request accepted, processing in background",
        client_msg_no=client_msg_no,
    )


# ============================================================================
# Helper Functions (Internal)
# ============================================================================
