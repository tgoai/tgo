"""工具运行时的辅助方法."""

from __future__ import annotations

from builtins import ExceptionGroup
from functools import wraps
from typing import Any, Dict, List, Optional

import aiohttp
import json

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


async def create_workflow_tools(workflow_url: str, workflow_ids: List[str], project_id: Optional[str]) -> List[Function]:
    """根据工作流信息生成工作流执行工具."""

    if not project_id:
        raise ValueError("project_id is required to create workflow tools")

    if not workflow_ids:
        return []

    url = workflow_url.rstrip("/")
    batch_endpoint = f"{url}/v1/workflows/batch"
    params = {
        "project_id": str(project_id),
        "workflow_ids": workflow_ids
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(batch_endpoint, params=params) as response:
            response.raise_for_status()
            workflows_data = await response.json()

    tools = []
    for workflow_data in workflows_data:
        w_id = workflow_data.get("id")
        name = workflow_data.get("name") or f"workflow_{w_id}"
        description = workflow_data.get("description")
        
        tool_description = f"Execute the '{name}' workflow."
        if description:
            tool_description = f"{tool_description} Workflow description: {description}"

        # Build safe tool name
        short_id = (w_id.replace("-", "")[:8]) if w_id else "unknown"
        tool_name = f"workflow_{short_id}".lower()

        # Parse input parameters for better tool schema
        input_params = workflow_data.get("input_parameters") or []
        inputs_properties = {}
        required_inputs = []
        for param in input_params:
            p_name = param.get("name")
            p_type = param.get("type") or "string"
            p_desc = param.get("description") or ""
            
            # Map workflow types to JSON Schema types
            js_type = p_type
            if js_type == "number":
                js_type = "number" # Could be number or integer in JSON schema
            
            inputs_properties[p_name] = {
                "type": js_type,
                "description": p_desc,
            }
            if param.get("required", True):
                required_inputs.append(p_name)

        inputs_schema = {
            "type": "object",
            "properties": inputs_properties,
            "description": "Input variables for the workflow.",
        }
        if required_inputs:
            inputs_schema["required"] = required_inputs

        def make_execute_func(wf_id: str):
            async def execute_workflow(inputs: Optional[Dict[str, Any]] = None) -> str:
                execute_endpoint = f"{url}/v1/workflows/{wf_id}/execute"
                exec_params = {"project_id": str(project_id)}
                payload = {"inputs": inputs or {}, "stream": False, "async": False}
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            execute_endpoint,
                            params=exec_params,
                            json=payload,
                        ) as exec_response:
                            exec_response.raise_for_status()
                            data = await exec_response.json()
                            return json.dumps(data, ensure_ascii=False)
                except Exception as exc:  # noqa: BLE001
                    return f"<error>{exc}</error>"
            return execute_workflow

        tools.append(
            Function(
                name=tool_name,
                description=tool_description,
                parameters={
                    "type": "object",
                    "properties": {
                        "inputs": inputs_schema
                    },
                    "required": ["inputs"] if required_inputs else [],
                },
                entrypoint=make_execute_func(w_id),
                skip_entrypoint_processing=True,
            )
        )
    
    return tools


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


def create_plugin_tool(
    plugin_id: str,
    tool_name: str,
    title: str,
    description: Optional[str],
    parameters: Optional[Dict[str, Any]],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Function:
    """根据插件信息生成插件工具包装."""
    from app.services.api_service import api_service_client

    async def plugin_tool_entrypoint(**tool_args: Any) -> Any:
        context = {
            "visitor_id": user_id,
            "session_id": session_id,
            "agent_id": agent_id,
        }
        try:
            result = await api_service_client.execute_plugin_tool(
                plugin_id=plugin_id,
                tool_name=tool_name,
                arguments=tool_args,
                context=context,
            )
            if result.get("success"):
                return result.get("content", "工具执行成功")
            else:
                return f"<error>{result.get('error', '工具执行失败')}</error>"
        except Exception as e:
            return f"<error>插件工具执行失败: {str(e)}</error>"

    return Function(
        name=tool_name,
        description=description or title,
        parameters=parameters or {"type": "object", "properties": {}},
        entrypoint=plugin_tool_entrypoint,
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
