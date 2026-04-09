"""Agent-level human handoff tool for requesting human support."""

from __future__ import annotations

from typing import Any, Optional

from agno.tools import Function

from .base import EventClient, ToolContext


def create_handoff_tool(
    *,
    agent_id: str,
    session_id: str | None,
    user_id: str | None,
    project_id: str | None = None,
    request_id: str | None = None,
) -> Function:
    """Create an agent-level tool that requests human support."""
    ctx = ToolContext(agent_id, session_id, user_id, project_id, request_id)
    client = EventClient(ctx)

    error_messages = {
        "not_configured": "抱歉，当前无法为您发起人工服务请求，我们已记录该问题并会尽快处理。请稍后再试或直接联系客服。",
        "api_error": "抱歉，人工服务请求未能成功提交。请稍后重试或联系技术支持。",
        "http_error": "抱歉，网络异常导致人工服务请求未能提交。请稍后重试或联系技术支持。",
        "unexpected_error": "抱歉，出现异常，暂时无法为您发起人工服务。请稍后重试或联系技术支持。",
    }

    async def request_human_support(
        *,
        reason: str,
        urgency: str = "normal",
        channel: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Request human support via manual_service.request event."""
        result = await client.post_event(
            "manual_service.request",
            {"reason": reason, "urgency": urgency, "channel": channel, "metadata": metadata},
            error_messages=error_messages,
        )

        if not result.success:
            return result.message

        return (
            f"[handoff_requested] agent={agent_id} session={session_id or ''} "
            f"urgency={urgency} reason={reason} (event sent)"
        )

    return Function(
        name="request_human_support",
        description=(
            "当用户明确要求人工或你判断需要人工介入时调用此工具，用于发起人工支持流程。"
            "请在参数中简要说明原因与紧急程度。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "触发人工介入的原因（必填）"},
                "urgency": {"type": "string", "description": "紧急程度：low|normal|high|urgent（默认 normal）"},
                "channel": {"type": "string", "description": "期望的人工渠道（如 phone/wechat/email/ticket 等，可选）"},
                "metadata": {"type": "object", "description": "其他上下文字段（可选）"},
            },
            "required": ["reason"],
        },
        entrypoint=request_human_support,
        skip_entrypoint_processing=True,
    )
