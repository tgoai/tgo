import json
import uuid
import httpx
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool, ToolType, ToolSourceType
from app.services.rag_service import rag_service_client
from app.services.api_service import api_service_client
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app.core.logging import get_logger

logger = get_logger(__name__)

class ToolExecutor:
    """Executor for dynamic tools referenced by IDs in Chat Completions API."""

    def __init__(self, db: AsyncSession, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id
        self._tool_registry: Dict[str, Dict[str, Any]] = {}
        self._context: Dict[str, Any] = {}

    def set_context(self, visitor_id: Optional[str] = None, session_id: Optional[str] = None, agent_id: Optional[str] = None, language: Optional[str] = None):
        """Set execution context for plugin tools."""
        self._context = {
            "visitor_id": visitor_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "language": language,
        }

    async def register_tools(
        self, 
        tool_ids: Optional[List[uuid.UUID]] = None, 
        collection_ids: Optional[List[str]] = None
    ):
        """Register tools to establish a mapping from tool_name to execution info."""
        if tool_ids:
            stmt = select(Tool).where(
                and_(
                    Tool.id.in_(tool_ids),
                    Tool.project_id == self.project_id,
                    Tool.deleted_at.is_(None),
                )
            )
            result = await self.db.execute(stmt)
            tools = result.scalars().all()
            for tool in tools:
                tool_type_str = "mcp" if tool.tool_type == ToolType.MCP else "function"
                if tool.tool_source_type == ToolSourceType.STORE:
                    tool_type_str = "store"
                elif tool.transport_type == "plugin":
                    tool_type_str = "plugin"
                elif tool.transport_type == "http_webhook":
                    tool_type_str = "http"
                
                self._tool_registry[tool.name] = {
                    "type": tool_type_str,
                    "id": str(tool.id),
                    "tool": tool
                }

        if collection_ids:
            for cid in collection_ids:
                # Same naming convention as in ChatService._create_rag_tool_definitions
                short_id = cid.replace("-", "")[:8]
                tool_name = f"rag_search_{short_id}"
                self._tool_registry[tool_name] = {
                    "type": "rag",
                    "id": cid
                }

    async def execute(self, tool_name: str, arguments: Any) -> str:
        """Execute a tool by name with provided arguments."""
        if tool_name not in self._tool_registry:
            return f"<error>Tool '{tool_name}' not found in registry</error>"

        info = self._tool_registry[tool_name]
        tool_type = info["type"]

        # Parse arguments if it's a string
        args = arguments
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError:
                return f"<error>Invalid JSON arguments for tool '{tool_name}'</error>"

        try:
            if tool_type == "rag":
                return await self._execute_rag(info["id"], args)
            elif tool_type == "store":
                return await self._execute_store(info["tool"], args)
            elif tool_type == "mcp":
                return await self._execute_mcp(info["tool"], args)
            elif tool_type == "plugin":
                return await self._execute_plugin(info["tool"], args)
            elif tool_type == "http":
                return await self._execute_http(info["tool"], args)
            elif tool_type == "function":
                # For now, we don't have a specific implementation for generic functions 
                # in the database that aren't MCP. 
                return f"<error>Tool '{tool_name}' is a generic function which is not yet implemented for direct execution</error>"
            else:
                return f"<error>Unsupported tool type: {tool_type}</error>"
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}", exc_info=True)
            return f"<error>{str(e)}</error>"

    async def _execute_rag(self, collection_id: str, args: Dict[str, Any]) -> str:
        query = args.get("query")
        if not query:
            return "<error>Missing 'query' argument for RAG search</error>"
        
        limit = args.get("limit", 10)
        try:
            results = await rag_service_client.search_documents(
                collection_id=collection_id,
                project_id=self.project_id,
                query=query,
                limit=limit
            )
        except Exception as e:
            return f"<error>RAG search failed: {str(e)}</error>"
        
        documents = results.get("results", [])
        if not documents:
            return "<documents />"

        serialized = [
            f'<document id="{doc.get("document_id", "unknown")}">{doc.get("content_preview", "")}</document>'
            for doc in documents
        ]
        return "<documents>" + "".join(serialized) + "</documents>"

    async def _execute_mcp(self, tool_model: Tool, args: Dict[str, Any]) -> str:
        if not tool_model.endpoint:
            return "<error>MCP tool missing endpoint</error>"
            
        # server_url should include /mcp if it's following the convention in AgentBuilder
        server_url = tool_model.endpoint.rstrip("/")
        if not server_url.endswith("/mcp") and (tool_model.transport_type or "http") == "http":
            server_url += "/mcp"

        try:
            async with streamablehttp_client(server_url) as streams:
                read_stream, write_stream, _ = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_model.name, arguments=args)
                    
                    if result.content:
                        texts = [c.text for c in result.content if hasattr(c, "text") and c.text]
                        if texts:
                            return "\n".join(texts)
                        return str(result.content)
                    return "Tool executed successfully with no content returned."
        except Exception as e:
            return f"<error>MCP execution failed: {str(e)}</error>"

    async def _execute_store(self, tool_model: Tool, args: Dict[str, Any]) -> str:
        """Execute a tool via the Store proxy."""
        store_tool_id = tool_model.store_resource_id
        if not store_tool_id:
            return "<error>Store tool missing store_resource_id</error>"

        try:
            # 1. 获取商店凭证
            credential = await api_service_client.get_store_credential(str(self.project_id))
            if not credential or not credential.get("api_key"):
                return "<error>Project not bound to Store. Please bind credentials first.</error>"
            
            api_key = credential["api_key"]
            
            # 2. 调用商店执行 API
            url = tool_model.endpoint
            if not url:
                 return "<error>Store tool missing endpoint</error>"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    json={
                        "method": tool_model.name,
                        "params": args
                    },
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 402:
                    return "<error>工具商店余额不足，请充值</error>"
                
                response.raise_for_status()
                
                result = response.json()
                # 商店返回的是原始 MCP 结果，我们需要提取内容
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list):
                        texts = [c.get("text") for c in content if isinstance(c, dict) and c.get("text")]
                        if texts:
                            return "\n".join(texts)
                    return str(content)
                return str(result)

        except Exception as e:
            logger.error(f"Store tool execution failed: {str(e)}", exc_info=True)
            return f"<error>Store execution failed: {str(e)}</error>"

    async def _execute_plugin(self, tool_model: Tool, args: Dict[str, Any]) -> str:
        """Execute a plugin tool via the core API service proxy."""
        plugin_id = tool_model.config.get("plugin_id")
        tool_name = tool_model.config.get("tool_name")
        
        if not plugin_id or not tool_name:
            return "<error>Plugin tool missing configuration (plugin_id or tool_name)</error>"

        try:
            result = await api_service_client.execute_plugin_tool(
                plugin_id=plugin_id,
                tool_name=tool_name,
                arguments=args,
                context=self._context,
            )
            
            if result.get("success"):
                return result.get("content", "工具执行成功")
            else:
                error_msg = result.get("error") or result.get("content") or "工具执行失败"
                return f"<error>{error_msg}</error>"
        except Exception as e:
            return f"<error>Plugin tool execution failed: {str(e)}</error>"

    async def _execute_http(self, tool_model: Tool, args: Dict[str, Any]) -> str:
        """Execute a custom HTTP webhook tool."""
        if not tool_model.endpoint:
            return "<error>HTTP tool missing endpoint</error>"

        config = tool_model.config or {}
        method = config.get("method", "POST").upper()
        headers = config.get("headers", {})
        
        # Ensure timeout is handled
        timeout = config.get("timeout", 30.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    response = await client.get(tool_model.endpoint, params=args, headers=headers)
                elif method == "POST":
                    response = await client.post(tool_model.endpoint, json=args, headers=headers)
                elif method == "PUT":
                    response = await client.put(tool_model.endpoint, json=args, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(tool_model.endpoint, params=args, headers=headers)
                elif method == "PATCH":
                    response = await client.patch(tool_model.endpoint, json=args, headers=headers)
                else:
                    return f"<error>Unsupported HTTP method: {method}</error>"

                response.raise_for_status()
                
                try:
                    return json.dumps(response.json(), ensure_ascii=False)
                except ValueError:
                    return response.text
        except httpx.HTTPStatusError as e:
            return f"<error>HTTP execution failed with status {e.response.status_code}: {e.response.text}</error>"
        except Exception as e:
            return f"<error>HTTP execution failed: {str(e)}</error>"
