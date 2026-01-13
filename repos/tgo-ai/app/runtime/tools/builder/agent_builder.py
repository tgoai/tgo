"""Agent builder with RAG and MCP integration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.models.internal import Agent as InternalAgent
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.memory import MemoryManager
from agno.db.postgres import PostgresDb
from agno.tools.mcp import MCPTools, MultiMCPTools
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.logging import get_logger
from app.config import settings
from app.runtime.core.exceptions import (
    InvalidConfigurationError,
    MCPAuthenticationError,
    MCPConnectionError,
    MCPToolError,
    MissingConfigurationError,
)
from app.runtime.tools.config import ToolsRuntimeSettings
from app.runtime.tools.models import (
    AgentConfig,
    AgentRunRequest,
    MCPConfig,
    RagConfig,
    WorkflowConfig,
)
from app.runtime.tools.token import get_mcp_access_token
from app.models.tool import Tool as ToolModel
from app.runtime.tools.utils import (
    create_agno_mcp_tool,
    create_rag_tool,
    create_workflow_tools,
    create_plugin_tool,
    create_http_tool,
    wrap_mcp_authenticate_tool,
)
from app.services.api_service import api_service_client

UNEDITABLE_SYSTEM_PROMPT = (
    "\nIf the tool throws an error requiring authentication, provide the user with a Markdown "
    "link to the authentication page and prompt them to authenticate."
)

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant that has access to a variety of tools."

# Flag to control UI template injection (can be configured per project/agent)
UI_TEMPLATES_ENABLED = True


class AgentBuilder:
    """Constructs Agno agents with optional RAG and MCP tooling."""

    def __init__(self, settings: ToolsRuntimeSettings) -> None:
        self._settings = settings
        self._logger = get_logger("runtime.tools.AgentBuilder")
        self._memory_db: Optional[PostgresDb] = None

    # ------------------------------------------------------------------
    # Public API
    async def build_agent(
        self,
        request: AgentRunRequest,
        internal_agent: Optional["InternalAgent"] = None,
    ) -> Agent:
        """Build an agent configured for the given request.

        Args:
            request: The agent run request containing configuration
            internal_agent: Optional internal agent model containing tool bindings
        """
        config = self._normalize_config(request.config)
        tools = await self._build_tools(
            config,
            request.session_id,
            request.user_id,
            internal_agent=internal_agent,
        )

        # Add UI template tools if enabled
        enable_ui_templates = getattr(config, 'enable_ui_templates', True) and UI_TEMPLATES_ENABLED
        if enable_ui_templates:
            ui_tools = self._build_ui_template_tools()
            tools.extend(ui_tools)

        model = self._initialize_model(config)
        instructions = self._compose_system_prompt(config.system_prompt, enable_ui_templates)
        enable_memory = request.enable_memory or bool(config.enable_memory)
        self._logger.debug(
            "Creating agent",
            tool_count=len(tools),
            model_name=config.model_name,
        )

        try:
            agent_kwargs: Dict[str, Any] = {
                "model": model,
                "tools": tools,
                "instructions": instructions,
                "additional_context": config.system_message,
                "expected_output": config.expected_output,
                "description": "Tools agent with MCP and RAG support",
                "markdown": config.markdown if config.markdown is not None else True,
                "add_datetime_to_context": config.add_datetime_to_context if config.add_datetime_to_context is not None else True,
                "add_location_to_context": config.add_location_to_context if config.add_location_to_context is not None else False,
                "timezone_identifier": config.timezone_identifier,
                "tool_call_limit": config.tool_call_limit,
                "telemetry": False,
                "debug_mode": True,
                "debug_level": 2
            }

            if request.session_id:
                agent_kwargs["session_id"] = request.session_id
            if request.user_id:
                agent_kwargs["user_id"] = request.user_id

            if enable_memory:
                memory_manager, memory_db = self._ensure_memory_backend(model)
                agent_kwargs.update(
                    db=memory_db,
                    memory_manager=memory_manager,
                    enable_agentic_memory=True,
                    enable_user_memories=True,
                    add_memories_to_context=True,
                    add_history_to_context = True,  # Automatically add the persisted session history to the context
                    num_history_runs=config.num_history_runs if config.num_history_runs is not None else 5, # Specify how many messages to add to the context
                )

            return Agent(**agent_kwargs)
        except Exception as exc:  # noqa: BLE001
            raise InvalidConfigurationError(
                "Failed to create Agent instance",
                tools_count=len(tools),
                error=str(exc),
            ) from exc

    # ------------------------------------------------------------------
    # Configuration helpers
    def _normalize_config(self, config: Optional[AgentConfig]) -> AgentConfig:
        """Apply runtime defaults to the incoming configuration."""
        merged = (config or AgentConfig()).model_copy(deep=True)

        base = self._settings.model
        if merged.model_name is None:
            merged.model_name = base.name
        if merged.temperature is None:
            merged.temperature = base.temperature
        if merged.max_tokens is None:
            merged.max_tokens = base.max_tokens
        if merged.system_prompt is None:
            merged.system_prompt = base.system_prompt

        return merged

    def _compose_system_prompt(
        self,
        configured_prompt: Optional[str],
        enable_ui_templates: bool = True,
    ) -> str:
        """Compose the final system prompt with optional UI template catalog.

        Args:
            configured_prompt: The base system prompt from configuration.
            enable_ui_templates: Whether to inject UI template catalog.

        Returns:
            Composed system prompt string.
        """
        prompt = configured_prompt or DEFAULT_SYSTEM_PROMPT

        # Inject UI template catalog if enabled
        if enable_ui_templates and UI_TEMPLATES_ENABLED:
            try:
                from app.ui_templates import generate_template_catalog
                ui_catalog = generate_template_catalog()
                if ui_catalog:
                    prompt = f"{prompt}\n\n{ui_catalog}"
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Failed to inject UI template catalog",
                    error=str(exc),
                )

        return f"{prompt}{UNEDITABLE_SYSTEM_PROMPT}"

    def resolve_model_instance(self, config: Optional[AgentConfig] = None) -> Any:
        """Public helper to obtain a model instance using runtime defaults."""

        normalized = self._normalize_config(config)
        return self._initialize_model(normalized)

    # ------------------------------------------------------------------
    # Tool preparation
    async def _build_tools(
        self,
        config: AgentConfig,
        session_id: Optional[str],
        user_id: Optional[str],
        internal_agent: Optional["InternalAgent"] = None,
    ) -> List[Any]:
        tools: List[Any] = []

        try:
            tools.extend(await self._build_rag_tools(config.rag))
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "RAG tool setup failed, continuing without RAG tools",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        try:
            tools.extend(await self._build_workflow_tools(config.workflow))
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Workflow tool setup failed, continuing without workflow tools",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Load MCP tools from internal_agent if provided, otherwise use config.mcp_config
        if internal_agent and internal_agent.tools:
            try:
                tools.extend(
                    await self._build_mcp_tools_from_agent(
                        internal_agent, 
                        session_id, 
                        user_id,
                        project_id=request.project_id
                    )
                )
            except (MCPConnectionError, MCPToolError, MCPAuthenticationError) as exc:
                self._logger.warning(
                    "MCP tool setup from agent failed, continuing without MCP tools",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Unexpected error during MCP tool setup from agent, continuing without MCP tools",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
        else:
            try:
                tools.extend(await self._build_mcp_tools(config.mcp_config, session_id, user_id))
            except (MCPConnectionError, MCPToolError, MCPAuthenticationError) as exc:
                self._logger.warning(
                    "MCP tool setup failed, continuing without MCP tools",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Unexpected error during MCP tool setup, continuing without MCP tools",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        return tools

    def _build_ui_template_tools(self) -> List[Any]:
        """Build UI template tools for structured data rendering.

        Returns:
            List of UI template tool functions.
        """
        try:
            from app.ui_templates.tools import get_ui_template, render_ui, list_ui_templates

            # Create function tools for the UI template operations
            tools = []

            # We use simple function wrappers that can be called by the LLM
            def ui_get_template(template_name: str) -> str:
                """获取指定 UI 模板的详细格式说明。当需要展示订单、产品、物流等结构化数据时使用。

                Args:
                    template_name: 模板名称 (order/product/product_list/logistics/price_comparison)
                """
                return get_ui_template(template_name)

            def ui_render(template_name: str, data: dict) -> str:
                """渲染 UI 模板，验证数据格式并返回格式化的 Markdown。

                Args:
                    template_name: 模板名称
                    data: 要渲染的数据字典
                """
                return render_ui(template_name, data)

            def ui_list_templates() -> str:
                """列出所有可用的 UI 模板及其简短描述。"""
                return list_ui_templates()

            tools.extend([ui_get_template, ui_render, ui_list_templates])

            self._logger.debug("UI template tools added", tool_count=len(tools))
            return tools

        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Failed to build UI template tools",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return []

    async def _build_rag_tools(self, rag_config: Optional[RagConfig]) -> List[Any]:
        if not rag_config or not rag_config.rag_url or not rag_config.collections:
            return []

        tools: List[Any] = []
        for collection in rag_config.collections:
            try:
                tool = await create_rag_tool(
                    rag_config.rag_url,
                    collection,
                    project_id=rag_config.project_id,
                )
                tools.append(tool)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Failed to create RAG tool for collection, skipping",
                    collection=collection,
                    rag_url=rag_config.rag_url,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
        return tools

    async def _build_workflow_tools(self, workflow_config: Optional[WorkflowConfig]) -> List[Any]:
        if not workflow_config or not workflow_config.workflow_url or not workflow_config.workflows:
            return []

        try:
            return await create_workflow_tools(
                workflow_config.workflow_url,
                workflow_config.workflows,
                project_id=workflow_config.project_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "Failed to create workflow tools, skipping",
                workflows=workflow_config.workflows,
                workflow_url=workflow_config.workflow_url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return []

    async def _build_mcp_tools(
        self,
        mcp_config: Optional[MCPConfig],
        session_id: Optional[str],
        user_id: Optional[str],
    ) -> List[Any]:
        if not mcp_config or not mcp_config.url:
            return []

        headers = await self._build_mcp_headers(mcp_config, session_id, user_id)
        server_url = mcp_config.url.rstrip("/") + "/mcp"
        requested_tools = set(mcp_config.tools or [])
        added_tool_names: set[str] = set()
        fetched_tools: List[Any] = []

        try:
            async with streamablehttp_client(server_url, headers=headers) as streams:
                read_stream, write_stream, _ = streams
                async with ClientSession(read_stream, write_stream) as session:
                    try:
                        await session.initialize()
                    except Exception as exc:  # noqa: BLE001
                        raise MCPConnectionError(
                            "Failed to initialize MCP session",
                            mcp_url=server_url,
                            error=str(exc),
                        ) from exc

                    cursor = None
                    while True:
                        try:
                            tool_list_page = await session.list_tools(cursor=cursor)
                        except Exception as exc:  # noqa: BLE001
                            raise MCPToolError(
                                "Failed to list MCP tools",
                                mcp_url=server_url,
                                cursor=cursor,
                                error=str(exc),
                            ) from exc
                        if not tool_list_page or not tool_list_page.tools:
                            break

                        for mcp_tool in tool_list_page.tools:
                            if requested_tools and mcp_tool.name not in requested_tools:
                                continue
                            if mcp_tool.name in added_tool_names:
                                continue

                            try:
                                agno_tool = create_agno_mcp_tool(
                                    mcp_tool,
                                    mcp_server_url=server_url,
                                    headers=headers,
                                )
                                if mcp_config.auth_required:
                                    agno_tool = wrap_mcp_authenticate_tool(agno_tool)
                                fetched_tools.append(agno_tool)
                                added_tool_names.add(mcp_tool.name)
                            except Exception as exc:  # noqa: BLE001
                                self._logger.warning(
                                    "Failed to convert MCP tool, skipping",
                                    tool_name=mcp_tool.name,
                                    mcp_url=server_url,
                                    error=str(exc),
                                    error_type=type(exc).__name__,
                                )

                        cursor = tool_list_page.nextCursor
                        if not cursor or (
                            requested_tools and len(added_tool_names) == len(requested_tools)
                        ):
                            break
        except MCPConnectionError:
            raise
        except MCPToolError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MCPToolError(
                "Unexpected error during MCP tool setup",
                mcp_url=server_url,
                error=str(exc),
            ) from exc

        self._logger.debug(
            "MCP tools setup completed",
            mcp_url=server_url,
            tools_fetched=len(fetched_tools),
            tools_requested=len(requested_tools) if requested_tools else "all",
        )

        return fetched_tools

    async def _build_mcp_tools_from_agent(
        self,
        internal_agent: "InternalAgent",
        session_id: Optional[str],
        user_id: Optional[str],
        project_id: Optional[str] = None,
    ) -> List[Any]:
        """Build MCP tools from InternalAgent.tools configuration.

        This method creates MCPTools instances for each MCP server configured in the agent's
        tool bindings. For stdio transport with multiple servers, it uses MultiMCPTools.
        For HTTP/SSE transports, it creates individual MCPTools instances.

        Note: Both MCPTools and MultiMCPTools load all tools from each MCP server, not just
        the ones bound to the agent. If you need to restrict which tools the agent can use,
        consider using tool permissions or other filtering mechanisms at the agent level.

        Args:
            internal_agent: Internal agent model containing tool bindings from database
            session_id: Optional session ID for MCP authentication headers (HTTP/SSE only)
            user_id: Optional user ID for MCP authentication headers (HTTP/SSE only)

        Returns:
            List of MCPTools/MultiMCPTools instances
        """
        from app.models.internal import AgentTool

        # Filter MCP and HTTP tools that are enabled
        mcp_tools = [
            tool for tool in internal_agent.tools
            if (tool.tool_type == "MCP" or tool.transport_type == "http_webhook") and tool.enabled
        ]

        if not mcp_tools:
            self._logger.debug("No enabled MCP or HTTP tools found in agent configuration")
            return []

        self._logger.debug(
            "Loading MCP and HTTP tools from agent configuration",
            agent_id=str(internal_agent.id) if internal_agent.id else "unknown",
            tool_count=len(mcp_tools),
        )

        # Group tools by endpoint and transport type
        tools_by_endpoint: Dict[str, List[AgentTool]] = {}
        plugin_tools: List[AgentTool] = []
        http_tools: List[AgentTool] = []
        for tool in mcp_tools:
            if tool.transport_type == "plugin":
                plugin_tools.append(tool)
                continue
            
            if tool.transport_type == "http_webhook":
                http_tools.append(tool)
                continue

            if not tool.endpoint:
                self._logger.warning(
                    "MCP tool missing endpoint, skipping",
                    tool_id=str(tool.tool_id),
                    tool_name=tool.tool_name,
                )
                continue

            endpoint = tool.endpoint
            if endpoint not in tools_by_endpoint:
                tools_by_endpoint[endpoint] = []
            tools_by_endpoint[endpoint].append(tool)

        # Build headers for authentication (used by HTTP/SSE transports)
        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id
        if user_id:
            headers["X-User-ID"] = user_id
        
        # Add Store API Key if applicable (Project-level key)
        if project_id:
            credential = await api_service_client.get_store_credential(project_id)
            if credential and credential.get("api_key"):
                headers["X-API-Key"] = credential["api_key"]
                self._logger.debug(f"Injected Store API Key for project {project_id}")
        
        # Fallback to global Store API Key if still not set
        if "X-API-Key" not in headers and settings.store_api_key:
            headers["X-API-Key"] = settings.store_api_key

        # Separate stdio commands from HTTP/SSE endpoints
        stdio_commands: List[str] = []
        mcp_tools_instances: List[Any] = []

        # Handle plugin-based tools
        for tool_binding in plugin_tools:
            try:
                # Load tool definition from tool.base_config (which contains the Tool model config)
                config = tool_binding.base_config or {}
                plugin_id = config.get("plugin_id")
                tool_name = config.get("tool_name")
                parameters_list = config.get("parameters", [])
                
                if not plugin_id or not tool_name:
                    self._logger.warning(f"Plugin tool missing configuration: {tool_binding.tool_name}")
                    continue

                # Convert parameters list to JSON Schema
                properties = {}
                required = []
                for p in parameters_list:
                    p_name = p.get("name")
                    p_type = p.get("type", "string")
                    p_desc = p.get("description", "")
                    p_required = p.get("required", False)
                    
                    prop = {"type": p_type, "description": p_desc}
                    if p_type == "enum" and "enum_values" in p:
                        prop["type"] = "string"
                        prop["enum"] = p["enum_values"]
                    elif p_type == "number":
                        prop["type"] = "number"
                    elif p_type == "boolean":
                        prop["type"] = "boolean"
                    
                    properties[p_name] = prop
                    if p_required:
                        required.append(p_name)
                
                parameters_schema = {
                    "type": "object",
                    "properties": properties,
                }
                if required:
                    parameters_schema["required"] = required

                plugin_tool_func = create_plugin_tool(
                    plugin_id=plugin_id,
                    tool_name=tool_name,
                    title=tool_binding.tool_name,
                    description=config.get("description"), # Note: description might be in base_config or tool model
                    parameters=parameters_schema,
                    session_id=session_id,
                    user_id=user_id,
                    agent_id=str(internal_agent.id),
                )
                mcp_tools_instances.append(plugin_tool_func)
                self._logger.debug(f"Added plugin tool: {tool_binding.tool_name} (plugin_id={plugin_id})")
            except Exception as exc:
                self._logger.warning(f"Failed to create plugin tool {tool_binding.tool_name}: {exc}")

        # Handle HTTP webhook tools
        for tool_binding in http_tools:
            try:
                # Load tool definition from tool.base_config (which contains the Tool model config)
                config = tool_binding.base_config or {}
                
                if not tool_binding.endpoint:
                    self._logger.warning(f"HTTP tool missing endpoint: {tool_binding.tool_name}")
                    continue

                http_tool_func = create_http_tool(
                    name=tool_binding.tool_name,
                    description=config.get("description") or tool_binding.tool_name,
                    endpoint=tool_binding.endpoint,
                    method=config.get("method", "POST"),
                    headers=config.get("headers"),
                    parameters=config.get("parameters"),
                    timeout=config.get("timeout", 30.0),
                )
                mcp_tools_instances.append(http_tool_func)
                self._logger.debug(f"Added HTTP tool: {tool_binding.tool_name} (endpoint={tool_binding.endpoint})")
            except Exception as exc:
                self._logger.warning(f"Failed to create HTTP tool {tool_binding.tool_name}: {exc}")

        if not tools_by_endpoint and not plugin_tools and not http_tools:
            self._logger.debug("No valid MCP endpoints, plugin tools, or HTTP tools found after filtering")
            return []

        for endpoint, endpoint_tools in tools_by_endpoint.items():
            try:
                # Get transport type (default to http)
                transport_type = endpoint_tools[0].transport_type or "http"

                if transport_type == "stdio":
                    # stdio transport: collect commands for MultiMCPTools
                    stdio_commands.append(endpoint)

                    self._logger.debug(
                        "Added stdio MCP server command",
                        command=endpoint,
                        tool_count=len(endpoint_tools),
                        tool_names=[tool.tool_name for tool in endpoint_tools],
                    )

                elif transport_type == "http":
                    # HTTP transport: create individual MCPTools instance
                    server_url = endpoint.rstrip("/")

                    # If we have custom headers (e.g. for ToolStore), we need to use 
                    # a custom tool wrapper because agno's MCPTools doesn't support headers
                    if headers:
                        for tool_model in endpoint_tools:
                            # Note: We need a Tool model object for create_agno_mcp_tool
                            # Assuming tool_model.base_config contains the original Tool info
                            base_config = tool_model.base_config or {}
                            
                            mcp_tool_obj = ToolModel(
                                id=tool_model.tool_id,
                                name=tool_model.tool_name,
                                description=tool_model.description or "",
                                inputSchema=base_config.get("inputSchema", {"type": "object", "properties": {}}),
                            )
                            
                            tool_func = create_agno_mcp_tool(
                                mcp_tool=mcp_tool_obj,
                                mcp_server_url=server_url,
                                headers=headers
                            )
                            mcp_tools_instances.append(tool_func)
                            
                        self._logger.debug(
                            "Created individual MCP tool functions with custom headers",
                            endpoint=endpoint,
                            tool_count=len(endpoint_tools),
                        )
                    else:
                        mcp_tools_instance = MCPTools(
                            transport="streamable-http",
                            url=server_url,
                        )
                        await mcp_tools_instance.connect()
                        mcp_tools_instances.append(mcp_tools_instance)

                        self._logger.debug(
                            "Created and connected HTTP MCPTools instance",
                            endpoint=endpoint,
                            server_url=server_url,
                            tool_count=len(endpoint_tools),
                            tool_names=[tool.tool_name for tool in endpoint_tools],
                        )

                elif transport_type == "sse":
                    # SSE transport: create individual MCPTools instance
                    server_url = endpoint.rstrip("/")

                    # If we have custom headers, we need individual tool functions
                    if headers:
                        for tool_model in endpoint_tools:
                            base_config = tool_model.base_config or {}
                            mcp_tool_obj = ToolModel(
                                id=tool_model.tool_id,
                                name=tool_model.tool_name,
                                description=tool_model.description or "",
                                inputSchema=base_config.get("inputSchema", {"type": "object", "properties": {}}),
                            )
                            # SSE support in create_agno_mcp_tool would be needed, 
                            # but currently it's hardcoded to streamablehttp_client
                            # For simplicity, we assume http for store
                            tool_func = create_agno_mcp_tool(
                                mcp_tool=mcp_tool_obj,
                                mcp_server_url=server_url,
                                headers=headers
                            )
                            mcp_tools_instances.append(tool_func)
                    else:
                        mcp_tools_instance = MCPTools(
                            transport="sse",
                            url=server_url,
                        )
                        await mcp_tools_instance.connect()
                        mcp_tools_instances.append(mcp_tools_instance)

                        self._logger.debug(
                            "Created and connected SSE MCPTools instance",
                            endpoint=endpoint,
                            server_url=server_url,
                            tool_count=len(endpoint_tools),
                            tool_names=[tool.tool_name for tool in endpoint_tools],
                        )

                else:
                    self._logger.warning(
                        "Unsupported MCP transport type, skipping endpoint",
                        endpoint=endpoint,
                        transport_type=transport_type,
                        tool_count=len(endpoint_tools),
                        supported_transports=["http", "stdio", "sse"],
                    )
                    continue

            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Failed to create MCPTools instance for endpoint, skipping",
                    endpoint=endpoint,
                    transport_type=transport_type,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        # Create MultiMCPTools for stdio commands if any
        if stdio_commands:
            try:
                multi_mcp_tools = MultiMCPTools(
                    stdio_commands,
                    allow_partial_failure=True,
                )

                await multi_mcp_tools.connect()
                mcp_tools_instances.append(multi_mcp_tools)

                self._logger.debug(
                    "Created and connected MultiMCPTools instance for stdio",
                    command_count=len(stdio_commands),
                    commands=stdio_commands,
                )

            except Exception as exc:  # noqa: BLE001
                self._logger.error(
                    "Failed to create MultiMCPTools instance for stdio commands",
                    commands=stdio_commands,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        self._logger.debug(
            "MCP tools setup from agent completed",
            agent_id=str(internal_agent.id) if internal_agent.id else "unknown",
            mcp_tools_instances_created=len(mcp_tools_instances),
            unique_endpoints=len(tools_by_endpoint),
        )

        return mcp_tools_instances

    def get_memory_backend(self, model: Any) -> tuple[MemoryManager, PostgresDb]:
        """Expose shared memory backend for external consumers (keyed by model)."""
        return self._ensure_memory_backend(model)


    def _ensure_memory_backend(self, model: Any) -> tuple[MemoryManager, PostgresDb]:
        """Always create a fresh MemoryManager for the provided model; reuse only the PostgresDb connection."""
        try:
            db = self._memory_db
            if db is None:
                db_url = settings.get_database_url(sync=True)
                self._logger.debug("Initializing Postgres memory backend", db_url=db_url)
                db = PostgresDb(db_url=db_url)
                self._memory_db = db

            # Create a new MemoryManager for each request to avoid stale model references
            memory_manager = MemoryManager(model=model, db=db)
            return memory_manager, db
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "Failed to initialize memory manager",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise InvalidConfigurationError(
                "Failed to initialize memory backend",
                error=str(exc),
            ) from exc

    async def _build_mcp_headers(
        self,
        mcp_config: MCPConfig,
        session_id: Optional[str],
        user_id: Optional[str],
    ) -> Optional[Dict[str, str]]:
        if not mcp_config.auth_required:
            return None

        supabase_token = self._settings.supabase.access_token
        if not supabase_token:
            self._logger.debug("No Supabase token available for MCP authentication")
            raise MCPAuthenticationError("Supabase access token is required for MCP authentication")

        try:
            tokens = await get_mcp_access_token(supabase_token, mcp_config.url)
        except Exception as exc:  # noqa: BLE001
            raise MCPAuthenticationError(
                "Failed to fetch MCP access token",
                mcp_url=mcp_config.url,
                session_id=session_id,
                user_id=user_id,
            ) from exc

        return {"Authorization": f"Bearer {tokens['access_token']}"}

    # ------------------------------------------------------------------
    # Model helpers
    def initialize_model(self, config: AgentConfig) -> Any:  # pragma: no cover - backwards compatibility
        return self._initialize_model(config)

    def _initialize_model(self, config: AgentConfig) -> Any:
        model_name = config.model_name or self._settings.model.name
        if not model_name:
            raise MissingConfigurationError(
                "Model name is required but not provided",
                config_key="model_name",
            )

        creds = config.provider_credentials
        if not creds:
            raise MissingConfigurationError(
                "LLM provider credentials are required",
                config_key="provider_credentials",
                model_name=model_name,
            )
        api_key = creds.api_key
        base_url = creds.api_base_url
        organization = creds.organization
        timeout = creds.timeout
        provider_kind = (creds.provider_kind or "").lower()

        if not api_key:
            raise MissingConfigurationError(
                f"Missing API key for model {model_name}",
                model_name=model_name,
                config_key="api_key",
            )

        if config.temperature is not None and not (0 <= config.temperature <= 2):
            raise InvalidConfigurationError(
                "Temperature must be between 0 and 2",
                temperature=config.temperature,
                valid_range="0-2",
            )

        if config.max_tokens is not None and config.max_tokens <= 0:
            raise InvalidConfigurationError(
                "max_tokens must be a positive integer",
                max_tokens=config.max_tokens,
            )

        # Provider is determined by credentials.provider_kind; do not parse from model_name
        if provider_kind in {"openai", "openai_compatible"}:
            openai_model = model_name
            try:
                kwargs: Dict[str, Any] = {
                    "id": openai_model,
                    "api_key": api_key,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "role_map": {
                        "system": "system",
                        "user": "user",
                        "assistant": "assistant",
                        "tool": "tool",
                        "model": "assistant",
                    },
                }
                if base_url:
                    kwargs["base_url"] = base_url
                if organization:
                    kwargs["organization"] = organization
                if timeout:
                    kwargs["timeout"] = timeout
                return OpenAIChat(**kwargs)
            except Exception as exc:  # noqa: BLE001
                raise InvalidConfigurationError(
                    "Failed to initialize OpenAI/OpenAI-compatible model",
                    model_name=model_name,
                    openai_model=openai_model,
                    error=str(exc),
                ) from exc

        if provider_kind == "anthropic":
            claude_model = model_name
            try:
                kwargs: Dict[str, Any] = {
                    "id": claude_model,
                    "api_key": api_key,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                }
                # Anthropic SDK typically doesn't take base_url; ignore if provided
                if timeout:
                    kwargs["timeout"] = timeout
                return Claude(**kwargs)
            except Exception as exc:  # noqa: BLE001
                raise InvalidConfigurationError(
                    "Failed to initialize Anthropic model",
                    model_name=model_name,
                    anthropic_model=claude_model,
                    error=str(exc),
                ) from exc

        if provider_kind == "google":
            gemini_model = model_name
            try:
                kwargs: Dict[str, Any] = {
                    "id": gemini_model,
                    "api_key": api_key,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                }
                # Google Gemini may support base_url via compatible endpoints; pass if provided
                if base_url:
                    kwargs["base_url"] = base_url
                if timeout:
                    kwargs["timeout"] = timeout
                return Gemini(**kwargs)
            except Exception as exc:  # noqa: BLE001
                raise InvalidConfigurationError(
                    "Failed to initialize Google Gemini model",
                    model_name=model_name,
                    gemini_model=gemini_model,
                    error=str(exc),
                ) from exc

        raise InvalidConfigurationError(
            "Unsupported or missing provider_kind in provider credentials",
            model_name=model_name,
            provider_kind=provider_kind,
            supported_providers=["openai", "openai_compatible", "anthropic", "google"],
        )
