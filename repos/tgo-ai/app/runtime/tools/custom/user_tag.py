"""Agent-level tool to add tags to users."""

from __future__ import annotations

from typing import Any, Optional

from agno.tools import Function

from .base import EventClient, ToolContext


def create_user_tag_tool(
    *,
    agent_id: str,
    session_id: str | None,
    user_id: str | None,
    project_id: str | None = None,
    request_id: str | None = None,
) -> Function:
    """Create an agent-level tool that adds tags to users."""
    ctx = ToolContext(agent_id, session_id, user_id, project_id, request_id)
    client = EventClient(ctx)

    error_messages = {
        "not_configured": "抱歉，当前无法为用户添加标签，我们已记录该问题并会尽快处理。请稍后再试或直接联系客服。",
        "api_error": "抱歉，用户标签添加未能成功提交。请稍后重试或联系技术支持。",
        "http_error": "抱歉，网络异常导致用户标签添加未能提交。请稍后重试或联系技术支持。",
        "unexpected_error": "抱歉，出现异常，暂时无法为用户添加标签。请稍后重试或联系技术支持。",
    }

    async def add_user_tags(
        *,
        tags: list[dict[str, str]],
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Add tags to user via user_tag.add event.

        Args:
            tags: List of tag objects, each with 'name' (English, required) and 'name_zh' (Chinese, optional)
            metadata: Optional additional context
        """
        if not tags:
            return "请至少提供一个标签。"

        # Validate and normalize tags
        normalized_tags = []
        for tag in tags:
            if not isinstance(tag, dict):
                return "标签格式错误，每个标签应包含 name 字段。"

            name = tag.get("name", "").strip()
            if not name:
                return "标签的 name 字段不能为空。"

            normalized_tag = {"name": name}
            name_zh = tag.get("name_zh", "").strip()
            if name_zh:
                normalized_tag["name_zh"] = name_zh

            normalized_tags.append(normalized_tag)

        result = await client.post_event(
            "user_tag.add",
            {"tags": normalized_tags, "metadata": metadata or {"source": "ai_analysis"}},
            error_messages=error_messages,
        )

        if not result.success:
            return result.message

        tag_names = ", ".join(t["name"] for t in normalized_tags)
        return f"已为用户添加标签：{tag_names}。"

    return Function(
        name="add_user_tags",
        description=(
            "当你识别出用户具有某些特征或属于某个分类时，调用此工具为用户添加标签。"
            "标签用于用户分类和后续营销/服务策略。"
            "常见标签示例：VIP（重要客户）、High Intent（高意向）、Price Sensitive（价格敏感）、"
            "Tech Support（技术支持）、New User（新用户）、Returning（回访客户）等。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "description": "标签列表，每个标签包含 name（英文名，必填）和 name_zh（中文名，建议提供）",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "标签英文名（必填）"},
                            "name_zh": {"type": "string", "description": "标签中文名（建议提供）"},
                        },
                        "required": ["name"],
                    },
                },
                "metadata": {"type": "object", "description": "其他上下文字段（可选）"},
            },
            "required": ["tags"],
        },
        entrypoint=add_user_tags,
        skip_entrypoint_processing=True,
    )
