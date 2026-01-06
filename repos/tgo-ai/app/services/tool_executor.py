import json
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool, ToolType
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
                if tool.transport_type == "plugin":
                    tool_type_str = "plugin"
                
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
            elif tool_type == "mcp":
                return await self._execute_mcp(info["tool"], args)
            elif tool_type == "plugin":
                return await self._execute_plugin(info["tool"], args)
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
