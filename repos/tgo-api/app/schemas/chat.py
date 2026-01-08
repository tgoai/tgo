"""Chat-related request/response schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.base import BaseSchema


class StaffSendPlatformMessageRequest(BaseSchema):
    """Payload for staff-triggered outbound platform messages."""

    channel_id: str = Field(..., description="WuKongIM channel identifier (e.g., {visitor_id}-vtr)")
    channel_type: int = Field(
        ...,
        description="WuKongIM channel type (customer service chat uses 251)",
        example=251,
    )
    payload: Dict[str, Any] = Field(..., description="Platform message payload (matches Platform Service contract)")
    client_msg_no: Optional[str] = Field(
        None,
        description="Optional client-supplied idempotency key; generated when omitted",
    )


class ChatFileUploadResponse(BaseSchema):
    """Response for chat file upload."""

    file_id: str = Field(..., description="UUID of the uploaded file record")
    file_name: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    file_url: str = Field(..., description="URL to access the file (e.g., /v1/chat/files/{file_id})")
    channel_id: str = Field(..., description="Channel identifier")
    channel_type: int = Field(..., description="Channel type code")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    uploaded_by: Optional[str] = Field(None, description="Staff username or 'visitor'")


class ChatCompletionRequest(BaseSchema):
    """流式聊天请求参数。"""

    api_key: str = Field(
        ...,
        description="平台 API Key，用于验证请求来源",
        examples=["pk_live_xxxxxxxxxxxx"]
    )
    message: str = Field(
        ...,
        description="用户发送的消息内容",
        examples=["你好，请问有什么可以帮助您的？"]
    )
    from_uid: str = Field(
        ...,
        description="平台用户唯一标识，用于识别访客身份",
        examples=["user_12345", "wx_openid_xxx"]
    )
    extra: Optional[Dict[str, Any]] = Field(
        None,
        description="额外数据，会随消息一起转发到 WuKongIM",
        examples=[{"source": "web", "page": "/product/123"}]
    )
    visitor_name: Optional[str] = Field(
        None,
        description="访客昵称/姓名"
    )
    visitor_avatar: Optional[str] = Field(
        None,
        description="访客头像URL"
    )
    msg_type: Optional[int] = Field(
        1,
        description="消息类型：1-文本，2-图片，3-文件，4-语音，5-视频",
        examples=[1, 2]
    )
    forward_user_message_to_wukongim: bool = Field(
        default=True,
        description="是否将用户消息同时转发一份到 WuKongIM（默认开启）",
        examples=[True],
    )
    timeout_seconds: Optional[int] = Field(
        120,
        ge=10,
        le=300,
        description="SSE 流超时时间（秒），默认120秒，范围10-300"
    )
    channel_id: Optional[str] = Field(
        None,
        description="自定义频道ID，不填则自动生成（格式: {visitor_id}-vtr 的编码形式）"
    )
    channel_type: Optional[int] = Field(
        None,
        description="频道类型，默认251（客服频道）"
    )
    system_message: Optional[str] = Field(
        None,
        description="AI系统提示词，用于指导AI的回复风格和行为",
        examples=["你是一个专业的客服助手，请用简洁友好的语气回复用户问题。"]
    )
    expected_output: Optional[str] = Field(
        None,
        description="期望的输出格式描述，帮助AI生成符合要求的响应",
        examples=["请用JSON格式回复，包含answer和confidence字段"]
    )
    wukongim_only: bool = Field(
        False,
        description="是否仅发送到WuKongIM而不返回流响应给客户端。设为true时，接口会立即返回accepted事件，AI处理在后台进行"
    )
    stream: Optional[bool] = Field(
        True,
        description="是否使用流式响应。true（默认）返回SSE流，false返回完整JSON响应"
    )


class StaffTeamChatRequest(BaseSchema):
    """Request payload for staff-to-team/agent chat.

    Notes:
    - Either team_id or agent_id must be provided (exactly one)
    - If team_id is provided, channel_id will be {team_id}-team
    - If agent_id is provided, channel_id will be {agent_id}-agent
    - Response is delivered via WuKongIM
    """
    team_id: Optional[UUID] = Field(None, description="AI Team ID to chat with")
    agent_id: Optional[UUID] = Field(None, description="AI Agent ID to chat with")
    message: str = Field(..., description="Message content to send")
    system_message: Optional[str] = Field(
        None, description="System message/prompt to guide the AI"
    )
    expected_output: Optional[str] = Field(
        None, description="Expected output format or description for the AI"
    )
    timeout_seconds: Optional[int] = Field(
        120, ge=1, le=600, description="Timeout in seconds for AI response"
    )

    @model_validator(mode="after")
    def validate_team_or_agent(self) -> "StaffTeamChatRequest":
        """Ensure exactly one of team_id or agent_id is provided."""
        if self.team_id is None and self.agent_id is None:
            raise ValueError("Either team_id or agent_id must be provided")
        if self.team_id is not None and self.agent_id is not None:
            raise ValueError("Only one of team_id or agent_id should be provided, not both")
        return self


class StaffTeamChatResponse(BaseSchema):
    """Response payload for staff-to-team/agent chat."""
    success: bool = Field(..., description="Whether the chat completed successfully")
    message: str = Field(..., description="Status message")
    client_msg_no: str = Field(..., description="Message correlation ID for tracking")


# OpenAI-compatible Chat Completion schemas

class OpenAIChatMessage(BaseSchema):
    """OpenAI-compatible chat message."""

    role: Literal["system", "user", "assistant", "function"] = Field(
        ...,
        description="The role of the message author"
    )
    content: str = Field(..., description="The content of the message")
    name: Optional[str] = Field(None, description="The name of the author of this message")


class OpenAIChatCompletionRequest(BaseSchema):
    """Simplified chat completion request.

    Only includes essential fields: messages, stream, and user.
    """

    messages: List[OpenAIChatMessage] = Field(
        ...,
        description="A list of messages comprising the conversation so far"
    )
    stream: Optional[bool] = Field(
        default=False,
        description="Whether to stream partial message deltas"
    )
    user: Optional[str] = Field(
        None,
        description="Unique identifier representing your end-user"
    )


class OpenAIChatCompletionChoice(BaseSchema):
    """OpenAI-compatible chat completion choice."""

    index: int = Field(..., description="The index of this choice")
    message: OpenAIChatMessage = Field(..., description="The generated message")
    finish_reason: Optional[str] = Field(
        None,
        description="Reason the model stopped generating tokens (stop, length, content_filter, null)"
    )


class OpenAIChatCompletionUsage(BaseSchema):
    """OpenAI-compatible token usage statistics."""

    prompt_tokens: int = Field(..., description="Number of tokens in the prompt")
    completion_tokens: int = Field(..., description="Number of tokens in the completion")
    total_tokens: int = Field(..., description="Total tokens used")


class OpenAIChatCompletionResponse(BaseSchema):
    """OpenAI-compatible chat completion response.

    This schema is compatible with OpenAI's ChatGPT API format.
    See: https://platform.openai.com/docs/api-reference/chat/object
    """

    id: str = Field(..., description="Unique identifier for the chat completion")
    object: Literal["chat.completion"] = Field(
        default="chat.completion",
        description="Object type, always 'chat.completion'"
    )
    created: int = Field(..., description="Unix timestamp of when the completion was created")
    model: str = Field(..., description="The model used for completion")
    choices: List[OpenAIChatCompletionChoice] = Field(
        ...,
        description="List of completion choices"
    )
    usage: OpenAIChatCompletionUsage = Field(..., description="Token usage statistics")


# OpenAI-compatible streaming response schemas

class OpenAIChatCompletionDelta(BaseSchema):
    """OpenAI-compatible delta object for streaming responses."""

    role: Optional[Literal["system", "user", "assistant", "function"]] = Field(
        None,
        description="The role of the message author (only in first chunk)"
    )
    content: Optional[str] = Field(None, description="The content delta")


class OpenAIChatCompletionChunkChoice(BaseSchema):
    """OpenAI-compatible choice object for streaming responses."""

    index: int = Field(..., description="The index of this choice")
    delta: OpenAIChatCompletionDelta = Field(..., description="The delta content")
    finish_reason: Optional[str] = Field(
        None,
        description="Reason the model stopped generating tokens (stop, length, content_filter, null)"
    )


class OpenAIChatCompletionChunk(BaseSchema):
    """OpenAI-compatible streaming chunk response.

    This schema is compatible with OpenAI's ChatGPT API streaming format.
    See: https://platform.openai.com/docs/api-reference/chat/streaming
    """

    id: str = Field(..., description="Unique identifier for the chat completion")
    object: Literal["chat.completion.chunk"] = Field(
        default="chat.completion.chunk",
        description="Object type, always 'chat.completion.chunk'"
    )
    created: int = Field(..., description="Unix timestamp of when the completion was created")
    model: str = Field(..., description="The model used for completion")
    choices: List[OpenAIChatCompletionChunkChoice] = Field(
        ...,
        description="List of completion choices with delta content"
    )
