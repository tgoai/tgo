"""Agent-level tool to track/update user sentiment/state information."""

from __future__ import annotations

from typing import Any, Optional

from agno.tools import Function

from .base import EventClient, ToolContext


def _parse_scale(val: Any) -> int:
    """Parse and validate a 0-5 scale value.

    Raises:
        ValueError: If value is not a valid integer in range 0-5
    """
    s = str(val).strip()
    try:
        iv = int(s)
    except ValueError:
        # Try parsing as float and converting
        f = float(s)
        if not f.is_integer():
            raise ValueError("Not an integer")
        iv = int(f)

    if not 0 <= iv <= 5:
        raise ValueError("Value out of range 0-5")
    return iv


def create_user_sentiment_tool(
    *,
    agent_id: str,
    session_id: str | None,
    user_id: str | None,
    project_id: str | None = None,
    request_id: str | None = None,
) -> Function:
    """Create an agent-level tool that updates user sentiment/state."""
    ctx = ToolContext(agent_id, session_id, user_id, project_id, request_id)
    client = EventClient(ctx)

    error_messages = {
        "not_configured": "抱歉，当前无法为您更新用户状态，我们已记录该问题并会尽快处理。请稍后再试或直接联系客服。",
        "api_error": "抱歉，用户状态更新未能成功提交。请稍后重试或联系技术支持。",
        "http_error": "抱歉，网络异常导致用户状态更新未能提交。请稍后重试或联系技术支持。",
        "unexpected_error": "抱歉，出现异常，暂时无法为您更新用户状态。请稍后重试或联系技术支持。",
    }

    async def update_user_sentiment(
        *,
        satisfaction: Optional[str] = None,
        emotion: Optional[str] = None,
        intent: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Update user sentiment/state via user_sentiment.update event."""
        # Parse and validate scale values
        provided: dict[str, Any] = {}

        if satisfaction not in (None, ""):
            try:
                provided["satisfaction"] = _parse_scale(satisfaction)
            except (ValueError, TypeError):
                return "满意度和情绪的数值必须在0-5之间，0表示未知。"

        if emotion not in (None, ""):
            try:
                provided["emotion"] = _parse_scale(emotion)
            except (ValueError, TypeError):
                return "满意度和情绪的数值必须在0-5之间，0表示未知。"

        if intent not in (None, ""):
            provided["intent"] = intent

        if not provided:
            return "请至少提供一个需要更新的用户状态字段，例如满意度、情绪或意图。"

        result = await client.post_event(
            "user_sentiment.update",
            {"sentiment": provided, "metadata": metadata},
            error_messages=error_messages,
        )

        if not result.success:
            return result.message

        updated_keys = ", ".join(provided.keys())
        return f"已记录用户状态更新：{updated_keys}。"

    return Function(
        name="update_user_sentiment",
        description=(
            "当你在对话中识别到用户满意度、情绪或意图发生变化时，调用此工具以记录/更新用户状态。"
            "可跟踪的信息包括：满意度（0-5数值，0表示未知，数值越高表示越满意）、情绪（0-5数值，0表示未知，数值越高表示情绪越积极）、"
            "意图（如 purchase/inquiry/complaint/support）；字段均为可选，支持部分更新。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "satisfaction": {"type": "integer", "minimum": 0, "maximum": 5, "description": "满意度，0-5数值（0=未知，1=非常不满意，5=非常满意）"},
                "emotion": {"type": "integer", "minimum": 0, "maximum": 5, "description": "情绪，0-5数值（0=未知，1=非常消极，5=非常积极）"},
                "intent": {"type": "string", "description": "意图（可选）"},
                "metadata": {"type": "object", "description": "其他上下文字段（可选）"},
            },
            "required": [],
        },
        entrypoint=update_user_sentiment,
        skip_entrypoint_processing=True,
    )
