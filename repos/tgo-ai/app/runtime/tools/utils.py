"""工具运行时的辅助方法."""

from __future__ import annotations

from builtins import ExceptionGroup
from functools import wraps
from typing import Any, Optional

import aiohttp

from agno.tools import Function
from mcp import ClientSession, McpError, Tool
from mcp.client.streamable_http import streamablehttp_client


async def create_rag_tool(rag_url: str, collection_id: str, project_id: Optional[str]) -> Function:
    """根据集合信息生成RAG查询工具."""

    if not project_id:
        raise ValueError("project_id is required to create RAG tools")

    url = rag_url.rstrip("/")
    collection_endpoint = f"{url}/v1/collections/{collection_id}"
    params = {"project_id": str(project_id)}

    async with aiohttp.ClientSession() as session:
        async with session.get(collection_endpoint, params=params) as response:
            response.raise_for_status()
            collection_data = await response.json()
    display_name = collection_data.get("display_name") or f"collection_{collection_id}"
    description = collection_data.get("description")
    tool_description = (
        f"Search documents within the '{display_name}' collection for results"
        " semantically similar to the query."
    )
    if description:
        tool_description = f"{tool_description} Collection description: {description}"

    # Build provider-safe tool name: letters, digits, _, ., -
    # We no longer use display_name in the tool name to avoid special character issues.
    short_id = (collection_id.replace("-", "")[:8]) if collection_id else "unknown"
    tool_name = f"rag_search_{short_id}".lower()
    async def search_collection(query: str) -> str:
        search_endpoint = f"{url}/v1/collections/{collection_id}/documents/search"
        payload = {"query": query, "limit": 10}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    search_endpoint,
                    params=params,
                    json=payload,
                ) as search_response:
                    search_response.raise_for_status()
                    data = await search_response.json()
        except Exception as exc:  # noqa: BLE001 - 需要返回错误信息
            return f"<error>{exc}</error>"

        documents = data.get("results", [])
        if not documents:
            return "<documents />"

        serialized = [
            f'<document id="{doc.get("document_id", "unknown")}">{doc.get("content_preview", "")}</document>'
            for doc in documents
        ]
        return "<documents>" + "".join(serialized) + "</documents>"

    return Function(
        name=tool_name,
        description=tool_description,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query to search the collection.",
                }
            },
            "required": ["query"],
        },
        entrypoint=search_collection,
        skip_entrypoint_processing=True,
    )


def create_agno_mcp_tool(
    mcp_tool: Tool,
    mcp_server_url: str,
    headers: Optional[dict[str, str]] = None,
) -> Function:
    """为Agno生成基于MCP协议的工具包装."""

    async def mcp_tool_entrypoint(**tool_args: Any) -> Any:
        async with streamablehttp_client(mcp_server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(mcp_tool.name, arguments=tool_args)
                if result.content and result.content[0].text:
                    return result.content[0].text
                return result

    return Function(
        name=mcp_tool.name,
        description=mcp_tool.description,
        parameters=mcp_tool.inputSchema,
        entrypoint=mcp_tool_entrypoint,
        skip_entrypoint_processing=True,
    )


def wrap_mcp_authenticate_tool(func: Function) -> Function:
    """捕获MCP鉴权异常并提示用户完成登录流程."""

    original = func.entrypoint

    @wraps(original)
    async def wrapped(**kwargs: Any) -> Any:
        try:
            return await original(**kwargs)
        except BaseException as exc:  # noqa: BLE001
            mcp_error = _find_first_mcp_error(exc)
            if not mcp_error:
                raise

            error_details = getattr(mcp_error, "error", None)
            if error_details and getattr(error_details, "code", None) == -32003:
                data = getattr(error_details, "data", {}) or {}
                message = data.get("message") or "Interaction required"
                if isinstance(message, dict):
                    message = message.get("text") or "Interaction required"
                url = data.get("url")
                if url:
                    message = f"{message} {url}"
                raise RuntimeError(message) from exc
            raise

    return Function.from_callable(wrapped, name=func.name, description=func.description)


def _find_first_mcp_error(exc: BaseException) -> Optional[McpError]:
    if isinstance(exc, McpError):
        return exc
    if isinstance(exc, ExceptionGroup):  # type: ignore[name-defined]
        for sub_exc in exc.exceptions:  # type: ignore[attr-defined]
            found = _find_first_mcp_error(sub_exc)
            if found:
                return found
    return None
