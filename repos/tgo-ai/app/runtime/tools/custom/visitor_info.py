"""Team-level tool to collect and update visitor information."""

from __future__ import annotations

from typing import Any, Optional

import json

import httpx
from agno.tools import Function

from .base import DEFAULT_TIMEOUT, EventClient, ToolContext

# Fields that can be updated for visitor info
VISITOR_INFO_FIELDS = (
    "email", "wechat", "phone", "name", "sex",
    "age", "company", "position", "address", "birthday",
)


def create_visitor_info_tool(
    *,
    team_id: str,
    session_id: str | None,
    user_id: str | None,
    project_id: str | None = None,
) -> list[Function]:
    """Create a list of tools for managing visitor information."""
    ctx = ToolContext(team_id, session_id, user_id, project_id)
    client = EventClient(ctx)

    error_messages = {
        "not_configured": "抱歉，当前无法处理访客信息，我们已记录该问题并会尽快处理。请稍后再试或直接联系客服。",
        "api_error": "抱歉，请求失败。请稍后重试或联系技术支持。",
        "http_error": "抱歉，网络异常。请稍后重试或联系技术支持。",
        "unexpected_error": "抱歉，出现异常。请稍后重试或联系技术支持。",
    }

    async def get_visitor_info() -> str:
        """获取当前访客的详细资料，包括基本信息、标签、AI 画像及最近活动。"""
        if not client.is_configured:
            return error_messages["not_configured"]

        visitor_id = ctx.visitor_id
        if not visitor_id:
            return "无法确定当前访客 ID，请确保访客已初始化。"

        if not ctx.project_id:
            return "配置错误：未提供项目 ID。"

        # Use the base URL from client
        base_url = client._base_url.rstrip("/")
        url = f"{base_url}/internal/visitors/{visitor_id}"
        params = {"project_id": ctx.project_id}

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as http_client:
                resp = await http_client.get(url, params=params)
                if resp.status_code == 404:
                    return f"未找到访客 (ID: {visitor_id}) 的资料。"
                resp.raise_for_status()
                data = resp.json()
                return json.dumps(data, ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"{error_messages['http_error']} (Detail: {str(exc)})"
        except Exception as exc:
            return f"{error_messages['unexpected_error']} (Detail: {str(exc)})"

    async def update_visitor_info(
        *,
        email: Optional[str] = None,
        wechat: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        sex: Optional[str] = None,
        age: Optional[str] = None,
        company: Optional[str] = None,
        position: Optional[str] = None,
        address: Optional[str] = None,
        birthday: Optional[str] = None,
        extra_info: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """Update visitor information via visitor_info.update event."""
        # Collect provided fields
        local_vars = locals()
        provided = {k: local_vars[k] for k in VISITOR_INFO_FIELDS if local_vars.get(k) not in (None, "")}

        if not provided:
            return "请至少提供一个需要更新的访客信息字段，例如邮箱、电话、微信、姓名等。"

        # Build visitor data
        visitor_data = dict(provided)
        if extra_info:
            visitor_data["extra_info"] = extra_info

        result = await client.post_event(
            "visitor_info.update",
            {"visitor": visitor_data, "metadata": metadata},
            error_messages=error_messages,
        )

        if not result.success:
            return result.message

        updated_keys = ", ".join(provided.keys())
        return f"已提交访客信息更新：{updated_keys}。感谢配合！"

    return [
        Function(
            name="get_visitor_info",
            description="获取当前访客的详细背景资料，包括姓名、联系方式、公司职位、标签画像及最近 10 条活动记录。",
            entrypoint=get_visitor_info,
        ),
        Function(
            name="update_visitor_info",
            description=(
                "当访客提供联系方式或个人信息时，调用此工具以记录或更新访客资料。"
                "可收集的信息包括：邮箱、微信、电话、姓名、性别、公司、职位、地址、生日、备注等；"
                "所有字段均为可选，支持部分更新。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "邮箱（可选）"},
                    "wechat": {"type": "string", "description": "微信号（可选）"},
                    "phone": {"type": "string", "description": "手机号（可选）"},
                    "name": {"type": "string", "description": "姓名（可选）"},
                    "sex": {"type": "string", "description": "性别（可选）"},
                    "age": {"type": "string", "description": "年龄（可选）"},
                    "company": {"type": "string", "description": "公司（可选）"},
                    "position": {"type": "string", "description": "职位（可选）"},
                    "address": {"type": "string", "description": "地址（可选）"},
                    "birthday": {"type": "string", "description": "生日（可选）"},
                    "extra_info": {"type": "object", "description": "扩展信息：存储其他未预定义的访客信息，如 Telegram、偏好等（可选）"},
                    "metadata": {"type": "object", "description": "其他上下文字段（可选）"},
                },
                "required": [],
            },
            entrypoint=update_visitor_info,
            skip_entrypoint_processing=True,
        ),
    ]
