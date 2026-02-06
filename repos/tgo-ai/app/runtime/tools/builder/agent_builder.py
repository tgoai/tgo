"""Agent builder with RAG and MCP integration."""

from __future__ import annotations

import asyncio
import json
import time
import traceback
import types
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

import httpx
from agno.agent import Agent, RemoteAgent
from agno.db.postgres import PostgresDb
from agno.memory import MemoryManager
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from agno.models.response import ToolExecution
from agno.run.agent import RunOutput, RunOutputEvent
from agno.tools import Toolkit
from agno.tools.function import Function
from agno.tools.mcp import MCPTools, MultiMCPTools
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import settings
from app.core.logging import get_logger
from app.models.internal import Agent as InternalAgent
from app.models.internal import AgentTool
from app.models.tool import Tool as ToolModel
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
from app.runtime.tools.utils import (
    create_agno_mcp_tool,
    create_http_tool,
    create_plugin_tool,
    create_rag_tool,
    create_workflow_tools,
    wrap_mcp_authenticate_tool,
)
from app.services.api_service import api_service_client
from app.ui_templates import generate_template_catalog
from app.ui_templates.tools import get_ui_template, list_ui_templates, render_ui

_logger = get_logger(__name__)


class StoreRemoteAgent(RemoteAgent):
    """
    Custom RemoteAgent that allows overriding id and name for Team coordination.
    
    支持本地工具绑定：
    - tools: 与本地 Agent 一致的工具属性
    - 内部透明执行：arun 内部自动处理工具执行循环，对调用者无感知
    """
    
    def __init__(self, *args, **kwargs):
        self._override_id = kwargs.pop("override_id", None)
        self._override_name = kwargs.pop("override_name", None)
        self._override_metadata = kwargs.pop("override_metadata", None)
        # Use pop to avoid TypeError in base class, but store it for our use
        self._api_key = kwargs.pop("api_key", None)
        # Some agno versions expect knowledge_filters on RemoteAgent
        self.knowledge_filters = kwargs.pop("knowledge_filters", None)
        
        # 新增：与本地 Agent 一致的工具属性，重命名为 local_tools 以避免与 RemoteAgent.tools 冲突
        self.local_tools: List[Union[Function, Callable]] = kwargs.pop("tools", [])
        self._tool_map: Dict[str, Function] = {}
        self._build_tool_map()
        
        super().__init__(*args, **kwargs)
    
    def _build_tool_map(self) -> None:
        """构建工具名称到工具对象的映射，支持 Toolkit 和普通 Function"""
        self._tool_map = {}
        for tool in self.local_tools:
            if isinstance(tool, Function):
                self._tool_map[tool.name] = tool
            elif isinstance(tool, Toolkit):
                # 如果是 Toolkit (如 MCPTools)，获取其内部所有工具
                # get_async_functions 返回合并了同步和异步工具的字典
                toolkit_tools = tool.get_async_functions()
                for name, func in toolkit_tools.items():
                    self._tool_map[name] = func
            elif callable(tool):
                # 如果是普通函数，包装成 Function
                name = getattr(tool, "__name__", str(tool))
                self._tool_map[name] = tool
        _logger.debug(f"Built tool map with {len(self._tool_map)} tools: {list(self._tool_map.keys())}")
    
    def _build_tools_schema(self) -> List[Dict[str, Any]]:
        """将本地工具转换为 JSON Schema 格式，发送给远程 Agent"""
        schemas = []
        for tool in self.local_tools:
            if isinstance(tool, Function):
                schemas.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.parameters or {"type": "object", "properties": {}},
                })
            elif callable(tool):
                # 简单处理普通函数
                name = getattr(tool, "__name__", str(tool))
                doc = getattr(tool, "__doc__", "") or ""
                schemas.append({
                    "name": name,
                    "description": doc,
                    "parameters": {"type": "object", "properties": {}},
                })
        return schemas
    
    def _has_pending_tool_calls(self, result: Any) -> bool:
        """检查结果中是否有需要外部执行的工具调用"""
        _logger.debug(f"Checking for pending tool calls in: {type(result)}")
        
        # 兼容字典格式
        tools = []
        if isinstance(result, dict):
            tools = result.get('tools', [])
        elif hasattr(result, 'tools'):
            tools = result.tools or []
            
        if not tools:
            _logger.debug("No tools attribute or empty tools list")
            return False
        
        for tool_exec in tools:
            # 兼容对象和字典
            if isinstance(tool_exec, dict):
                is_ext = tool_exec.get('external_execution_required', False)
                tool_name = tool_exec.get('tool_name', 'unknown')
            else:
                is_ext = hasattr(tool_exec, 'external_execution_required') and tool_exec.external_execution_required
                tool_name = getattr(tool_exec, 'tool_name', 'unknown')
                
            _logger.debug(f"Tool {tool_name}: external_execution_required={is_ext}")
            if is_ext:
                print(f"has_pending_tool_calls--> True (tool: {tool_name})")
                return True
        return False

    async def _execute_tools_locally(self, tool_calls: List[Union[ToolExecution, Dict[str, Any]]]) -> List[ToolExecution]:
        """
        本地执行工具，与本地 Agent 行为一致。
        执行后填充结果并清除 external_execution_required 标志。
        """
        updated_tool_calls: List[ToolExecution] = []

        print("_execute_tools_locally--->", tool_calls)
        
        for tc_raw in tool_calls:
            # 统一转换为 ToolExecution 对象进行处理
            if isinstance(tc_raw, dict):
                tc = ToolExecution(**tc_raw)
            else:
                tc = tc_raw
                
            if not (hasattr(tc, 'external_execution_required') and tc.external_execution_required):
                # 跳过已处理的工具，不添加到返回列表
                # 这是修复 400 错误的关键：避免将已处理的工具重复发送给 store-api
                _logger.debug(f"Skipping already processed tool: {getattr(tc, 'tool_name', 'unknown')}")
                continue
            
            tool_name = tc.tool_name
            tool_args = tc.tool_args or {}
            
            _logger.debug(f"Executing local tool: {tool_name} with args: {tool_args}")
            
            tool = self._tool_map.get(tool_name)
            if not tool:
                _logger.warning(f"Tool {tool_name} not found in local tools")
                tc.result = f"Error: Tool '{tool_name}' not found"
                tc.external_execution_required = False
                updated_tool_calls.append(tc)
                continue
            print("tool--->", tool)
            try:
                if isinstance(tool, Function):
                    # Function 对象
                    if tool.entrypoint:
                        if asyncio.iscoroutinefunction(tool.entrypoint):
                            result = await tool.entrypoint(**tool_args)
                        else:
                            result = tool.entrypoint(**tool_args)
                    else:
                        result = f"Tool {tool_name} has no entrypoint"
                elif callable(tool):
                    # 普通函数
                    if asyncio.iscoroutinefunction(tool):
                        result = await tool(**tool_args)
                    else:
                        result = tool(**tool_args)
                else:
                    result = f"Tool {tool_name} is not callable"
                print("tool-result--->", result)
                # 将结果转换为字符串
                if not isinstance(result, str):
                    try:
                        result = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception:
                        result = str(result)
                
                tc.result = result
                _logger.debug(f"Tool {tool_name} executed successfully: {result[:100]}...")
                
            except Exception as e:
                error_detail = traceback.format_exc()
                _logger.error(f"Error executing tool {tool_name}: {e}\n{error_detail}")
                
                # 特殊处理 ExceptionGroup (Python 3.11+) 以获取更详细的子错误
                error_msg = f"Error executing tool: {str(e)}"
                try:
                    # 检查是否是 ExceptionGroup
                    if hasattr(e, 'exceptions'):
                        sub_errors = [f"{type(ex).__name__}: {str(ex)}" for ex in e.exceptions]
                        error_msg += f" (Sub-errors: {', '.join(sub_errors)})"
                except Exception:
                    pass
                
                tc.result = error_msg
            
            tc.external_execution_required = False
            updated_tool_calls.append(tc)
        
        return updated_tool_calls

    @property
    def id(self) -> str:
        return self._override_id or self.agent_id

    @property
    def agentos_client(self):
        """Override to ensure headers are injected into the client."""
        # Use a private attribute to avoid recursion and handle the base class assignment
        client = getattr(self, "_store_agentos_client", None)
        if client is None:
            return None
            
        api_key = self._api_key
        if not api_key:
            api_key = settings.store_api_key
            
        if api_key:
            # Ensure headers are present in the client
            # Agno uses httpx internally, so client.headers should work
            if hasattr(client, "headers"):
                if client.headers is None:
                    client.headers = {}
                # Inject directly into client state
                client.headers["X-API-Key"] = api_key
                client.headers["Authorization"] = f"Bearer {api_key}"
            
            # For some agno versions, we might need to set it on the base client as well
            if hasattr(client, "client") and hasattr(client.client, "headers"):
                if client.client.headers is None:
                    client.client.headers = {}
                client.client.headers["X-API-Key"] = api_key
                client.client.headers["Authorization"] = f"Bearer {api_key}"
        return client

    @agentos_client.setter
    def agentos_client(self, value):
        self._store_agentos_client = value

    @property
    def name(self) -> Optional[str]:
        return self._override_name or super().name

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._override_metadata or {}

    def get_auth_headers(self, auth_token: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Public version of get_auth_headers used by some agno versions."""
        return self._get_auth_headers(auth_token)

    def _get_auth_headers(self, auth_token: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Call super to get existing headers if any
        headers = {}
        # RemoteAgent usually has _get_auth_headers or get_auth_headers
        try:
            # Try private first as it's more common in agno internal
            if hasattr(super(), "_get_auth_headers"):
                headers = super()._get_auth_headers(auth_token) or {}
            elif hasattr(super(), "get_auth_headers"):
                headers = super().get_auth_headers(auth_token) or {}
        except Exception:
            pass
            
        api_key = self._api_key or settings.store_api_key

        if api_key:
            headers["X-API-Key"] = api_key
            # Also set Bearer token if not already set, using the API key
            if "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {api_key}"
        
        return headers if headers else None

    @property
    def _agent_config(self) -> Optional[Any]:
        """Override to pass headers to the remote call."""
        current_time = time.time()

        # Check if cache is valid
        if self._cached_agent_config is not None:
            config, cached_at = self._cached_agent_config
            if current_time - cached_at < self.config_ttl:
                return config

        # Fetch fresh config with headers
        headers = self._get_auth_headers()
        try:
            config = self.agentos_client.get_agent(self.agent_id, headers=headers)
            self._cached_agent_config = (config, current_time)
            return config
        except Exception:
            return None

    @property
    def _config(self) -> Optional[Any]:
        """Override to pass headers to the remote call."""
        current_time = time.time()

        # Check if cache is valid
        if self._cached_config is not None:
            config, cached_at = self._cached_config
            if current_time - cached_at < self.config_ttl:
                return config

        # Fetch fresh config with headers
        headers = self._get_auth_headers()
        try:
            config = self.agentos_client.get_config(headers=headers)
            self._cached_config = (config, current_time)
            return config
        except Exception:
            return None

    async def get_agent_config(self) -> Any:
        """Override to pass headers."""
        headers = self._get_auth_headers()
        return await self.agentos_client.aget_agent(self.agent_id, headers=headers)

    async def refresh_config(self) -> Optional[Any]:
        """Override to pass headers."""
        headers = self._get_auth_headers()
        config = await self.agentos_client.aget_agent(self.agent_id, headers=headers)
        self._cached_agent_config = (config, time.time())
        return config

    def arun(
        self,
        input: Any,
        *,
        stream: Optional[bool] = None,
        **kwargs
    ) -> Union[RunOutput, AsyncIterator[RunOutputEvent]]:
        """
        运行远程 Agent，支持本地工具透明执行。
        
        如果绑定了本地工具：
        1. 将工具 schema 发送给远程 Agent
        2. 检查返回结果中是否有需要外部执行的工具
        3. 本地执行这些工具，然后调用 continue_run 继续
        4. 循环直到完成
        """
        _logger.info(f"StoreRemoteAgent.arun called with stream={stream}")
        # 如果有本地工具，注入工具 schema 到请求中
        if self.local_tools:
            tools_schema = self._build_tools_schema()
            # 显式序列化为 JSON 字符串数组，确保跨语言/跨服务调用格式标准
            kwargs["tools"] = json.dumps(tools_schema)
            _logger.debug(f"Injecting {len(tools_schema)} local tools to remote agent call")
        
        # 调用父类的 arun
        result = super().arun(input, stream=stream, **kwargs)
        
        # 处理流式和非流式情况
        if stream:
            # 流式输出 - 需要包装以处理工具执行
            return self._wrap_stream_with_tool_execution(result, **kwargs)
        else:
            # 非流式输出 - 包装协程以处理工具执行循环
            if asyncio.iscoroutine(result):
                return self._wrap_coro_with_tool_execution(result, **kwargs)
            return result
    
    async def _wrap_coro_with_tool_execution(self, coro, **kwargs) -> RunOutput:
        """包装协程，添加工具执行循环"""
        run_output = await coro
        
        # 映射 ID
        self._map_ids(run_output)
        
        # 如果没有本地工具，直接返回
        if not self.local_tools:
            return run_output
        
        # 工具执行循环
        max_iterations = 10  # 防止无限循环
        iteration = 0
        
        while self._has_pending_tool_calls(run_output) and iteration < max_iterations:
            iteration += 1
            _logger.debug(f"Tool execution loop iteration {iteration}")
            
            # 本地执行工具
            if hasattr(run_output, 'tools') and run_output.tools:
                updated_tools = await self._execute_tools_locally(run_output.tools)
                
                # 调用 continue_run 继续远程 Agent
                run_id = getattr(run_output, 'run_id', None)
                session_id = kwargs.get('session_id')
                
                if run_id:
                    _logger.debug(f"Calling acontinue_run with run_id={run_id}")
                    run_output = await self.acontinue_run(
                        run_id=run_id,
                        updated_tools=updated_tools,
                        session_id=session_id,
                        stream=False
                    )
                    self._map_ids(run_output)
                else:
                    _logger.warning("No run_id in response, cannot continue run")
                    break
        
        if iteration >= max_iterations:
            _logger.warning(f"Tool execution loop reached max iterations ({max_iterations})")
        
        return run_output
    
    async def _wrap_stream_with_tool_execution(self, stream_result, **kwargs) -> AsyncIterator[RunOutputEvent]:
        """包装流式结果，添加工具执行支持"""
        collected_output = None
        print("_wrap_stream_with_tool_execution-->")
        async for event in stream_result:
            # 映射 ID
            if hasattr(event, "agent_id") and self._override_id:
                event.agent_id = self._override_id
            if hasattr(event, "agent_name") and self._override_name:
                event.agent_name = self._override_name
            
            # 收集最终输出用于工具执行检查
            if hasattr(event, 'run_id'):
                collected_output = event
            
            yield event
        
        _logger.debug(f"Stream finished. collected_output type: {type(collected_output)}")
        
        # 流式输出完成后，检查是否需要工具执行
        print("collected_output-->", collected_output)
        if self.local_tools and collected_output and self._has_pending_tool_calls(collected_output):
            _logger.debug("Stream completed with pending tool calls, entering tool execution loop")
            
            max_iterations = 10
            iteration = 0
            
            while self._has_pending_tool_calls(collected_output) and iteration < max_iterations:
                iteration += 1
                
                # 本地执行工具
                if hasattr(collected_output, 'tools') and collected_output.tools:
                    updated_tools = await self._execute_tools_locally(collected_output.tools)
                    
                    run_id = getattr(collected_output, 'run_id', None)
                    session_id = kwargs.get('session_id')
                    
                    if run_id:
                        # 以流式方式继续
                        async for event in self.acontinue_run(
                            run_id=run_id,
                            updated_tools=updated_tools,
                            session_id=session_id,
                            stream=True
                        ):
                            if hasattr(event, "agent_id") and self._override_id:
                                event.agent_id = self._override_id
                            if hasattr(event, 'run_id'):
                                collected_output = event
                            yield event
                    else:
                        break
    
    def _map_ids(self, result: Any) -> None:
        """映射 ID 到覆盖值"""
        if self._override_id:
            if hasattr(result, "agent_id"):
                result.agent_id = self._override_id
            if hasattr(result, "agent_name"):
                result.agent_name = self.name


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
    ) -> Union[Agent, RemoteAgent]:
        """Build an agent configured for the given request.

        Args:
            request: The agent run request containing configuration
            internal_agent: Optional internal agent model containing tool bindings
        """
        # # 1. Handle Remote Store Agents
        # if internal_agent and getattr(internal_agent, "is_remote_store_agent", False):
        #     return await self._build_remote_store_agent(request, internal_agent)

        # 2. Handle Local Agents
        return await self._build_local_agent(request, internal_agent)

    async def _build_remote_store_agent(
        self,
        request: AgentRunRequest,
        internal_agent: "InternalAgent",
    ) -> StoreRemoteAgent:
        """Helper to construct a StoreRemoteAgent."""
        # 获取商店 API Key
        api_key = None
        if request.project_id:
            try:
                credential = await api_service_client.get_store_credential(request.project_id)
                if credential:
                    api_key = credential.get("api_key")
            except Exception as e:
                self._logger.warning("Failed to fetch store credential", error=str(e))

        if not api_key:
            api_key = settings.store_api_key

        # 为远程 Agent 加载本地工具
        local_tools = []
        if internal_agent.tools:
            try:
                local_tools = await self._build_mcp_tools_from_agent(
                    internal_agent,
                    request.session_id,
                    request.user_id,
                    project_id=request.project_id,
                )
            except Exception as e:
                self._logger.warning("Failed to build local tools for remote agent", error=str(e))

        self._logger.debug(
            "Creating RemoteAgent",
            agent_id=internal_agent.store_agent_id,
            base_url=internal_agent.remote_agent_url
        )
        return StoreRemoteAgent(
            base_url=internal_agent.remote_agent_url,
            agent_id=internal_agent.store_agent_id,
            timeout=60.0,
            override_id=str(internal_agent.id),
            override_name=internal_agent.name,
            api_key=api_key,
            tools=local_tools,
        )

    async def _build_local_agent(
        self,
        request: AgentRunRequest,
        internal_agent: Optional["InternalAgent"] = None,
    ) -> Agent:
        """Helper to construct a local Agno Agent."""
        config = self._normalize_config(request.config)
        tools = await self._build_tools(
            config,
            request.session_id,
            request.user_id,
            internal_agent=internal_agent,
            project_id=request.project_id,
        )

        # Add UI template tools if enabled
        enable_ui_templates = getattr(config, 'enable_ui_templates', True) and UI_TEMPLATES_ENABLED
        if enable_ui_templates:
            tools.extend(self._build_ui_template_tools())

        model = self._initialize_model(config)
        instructions = self._compose_system_prompt(config.system_prompt, enable_ui_templates)
        enable_memory = request.enable_memory or bool(config.enable_memory)

        self._logger.debug(
            "Creating local agent",
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
                    add_history_to_context=True,
                    num_history_runs=config.num_history_runs if config.num_history_runs is not None else 5,
                )

            return Agent(**agent_kwargs)
        except Exception as exc:
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

        # Map base defaults if not provided in merged config
        merged.model_name = merged.model_name or base.name
        merged.temperature = merged.temperature if merged.temperature is not None else base.temperature
        merged.max_tokens = merged.max_tokens if merged.max_tokens is not None else base.max_tokens
        merged.system_prompt = merged.system_prompt or base.system_prompt

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
        project_id: Optional[str] = None,
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
                        project_id=project_id
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

        # Build device MCP tools if agent has a bound device
        if internal_agent and getattr(internal_agent, "bound_device_id", None):
            try:
                device_tools = await self._build_device_mcp_tools(internal_agent)
                tools.extend(device_tools)
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "Device MCP tool setup failed, continuing without device tools",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    device_id=getattr(internal_agent, "bound_device_id", None),
                )

        return tools

    def _build_ui_template_tools(self) -> List[Any]:
        """Build UI template tools for structured data rendering.

        Returns:
            List of UI template tool functions.
        """
        try:
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
                    filters=rag_config.filters,
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

    async def _fetch_mcp_tools_from_endpoint(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        requested_tools: Optional[set[str]] = None,
    ) -> List[Function]:
        """
        从 MCP 网关获取工具定义并创建 Function 对象。
        
        此方法通过 REST API 从 store-api 的 MCP 网关动态获取工具的真实定义，
        包括准确的 inputSchema，而不是依赖数据库中可能过时的静态配置。
        
        Args:
            endpoint: MCP 服务器地址（如 http://store-api/api/v1/mcp/{tool_id}/http）
            headers: 请求头（如认证信息）
            requested_tools: 指定要获取的工具名称集合，None 表示获取全部
        
        Returns:
            Function 对象列表
        """
        tools: List[Function] = []
        server_url = endpoint.rstrip("/")
        
        # 将 /http 端点转换为 /tools 端点
        # http://store-api/api/v1/mcp/{tool_id}/http -> http://store-api/api/v1/mcp/{tool_id}/tools
        if server_url.endswith("/http"):
            tools_url = server_url[:-5] + "/tools"
        elif server_url.endswith("/sse"):
            tools_url = server_url[:-4] + "/tools"
        else:
            tools_url = server_url + "/tools"
        
        try:
            self._logger.info(
                "Fetching MCP tools from gateway",
                endpoint=endpoint,
                tools_url=tools_url,
                requested_tools=list(requested_tools) if requested_tools else None,
                header_keys=list(headers.keys()) if headers else None,
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(tools_url, headers=headers)
                self._logger.info(
                    "MCP gateway response received",
                    tools_url=tools_url,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type"),
                )
                response.raise_for_status()
                
                data = response.json()
                print("data-->", data)
                self._logger.debug(
                    "MCP gateway response parsed",
                    tools_url=tools_url,
                    response_keys=list(data.keys()) if isinstance(data, dict) else None,
                    tool_count=len(data.get("tools", [])) if isinstance(data, dict) else None,
                )
                tool_list = data.get("tools", [])
                
                for tool_def in tool_list:
                    tool_name = tool_def.get("name")
                    
                    # 如果指定了工具列表，只获取指定的工具
                    if requested_tools and tool_name not in requested_tools:
                        continue
                    
                    # 创建一个类似 MCP Tool 的对象
                    mcp_tool = types.SimpleNamespace(
                        name=tool_name,
                        description=tool_def.get("description", ""),
                        inputSchema=tool_def.get("inputSchema", {"type": "object", "properties": {}}),
                    )
                    
                    tool_func = create_agno_mcp_tool(
                        mcp_tool,
                        mcp_server_url=server_url,
                        headers=headers,
                    )
                    tools.append(tool_func)
                    
                self._logger.debug(
                    "Successfully fetched tool definitions from MCP gateway",
                    tools_url=tools_url,
                    tool_count=len(tools),
                )
                            
        except httpx.HTTPStatusError as e:
            response_text = ""
            try:
                response_text = e.response.text
            except Exception:
                response_text = ""
            if response_text and len(response_text) > 1000:
                response_text = response_text[:1000] + "...(truncated)"
            self._logger.warning(
                "MCP gateway returned error status",
                endpoint=endpoint,
                tools_url=tools_url,
                status_code=e.response.status_code,
                response_text=response_text,
            )
        except Exception as e:
            print(f"[ERROR] Failed to fetch MCP tools from endpoint: {e!r}")
            print(f"[ERROR] endpoint={endpoint}, tools_url={tools_url}")
            print(f"[ERROR] requested_tools={list(requested_tools) if requested_tools else None}")
            print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
            self._logger.warning(
                f"Failed to fetch MCP tools from endpoint, tools will not be available. error={e!r}",
                endpoint=endpoint,
                tools_url=tools_url,
                requested_tools=list(requested_tools) if requested_tools else None,
                error_type=type(e).__name__,
            )
        
        return tools

    async def _build_mcp_tools_from_agent(
        self,
        internal_agent: "InternalAgent",
        session_id: Optional[str],
        user_id: Optional[str],
        project_id: Optional[str] = None,
    ) -> List[Any]:
        """Build MCP tools from InternalAgent.tools configuration."""
        # 1. Filter and group tools
        enabled_tools = [
            t for t in internal_agent.tools 
            if (t.tool_type == "MCP" or t.transport_type == "http_webhook") and t.enabled
        ]
        if not enabled_tools:
            return []

        self._logger.debug("Loading tools from agent", agent_id=str(internal_agent.id), count=len(enabled_tools))

        # 2. Group by type/endpoint
        tools_by_endpoint: Dict[str, List[AgentTool]] = {}
        plugin_tools: List[AgentTool] = []
        http_tools: List[AgentTool] = []
        for t in enabled_tools:
            if t.transport_type == "plugin":
                plugin_tools.append(t)
            elif t.transport_type == "http_webhook":
                http_tools.append(t)
            elif t.endpoint:
                tools_by_endpoint.setdefault(t.endpoint, []).append(t)

        # 3. Build authentication headers
        headers = await self._build_auth_headers(session_id, user_id, project_id)

        # 4. Build tool instances
        tools: List[Any] = []
        tools.extend(self._build_plugin_tools(plugin_tools, session_id, user_id, str(internal_agent.id)))
        tools.extend(self._build_http_webhook_tools(http_tools))
        
        mcp_tools, stdio_cmds = await self._build_mcp_server_instances(tools_by_endpoint, headers)
        tools.extend(mcp_tools)
        
        if stdio_cmds:
            tools.extend(await self._build_multi_mcp_stdio(stdio_cmds))

        return tools

    async def _build_auth_headers(self, session_id: Optional[str], user_id: Optional[str], project_id: Optional[str]) -> Dict[str, str]:
        """Helper to build consistent authentication headers."""
        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id
        if user_id:
            headers["X-User-ID"] = user_id
        
        if project_id:
            try:
                credential = await api_service_client.get_store_credential(project_id)
                if credential and credential.get("api_key"):
                    headers["X-API-Key"] = credential["api_key"]
            except Exception:
                pass
        
        if "X-API-Key" not in headers and settings.store_api_key:
            headers["X-API-Key"] = settings.store_api_key
        return headers

    def _build_plugin_tools(self, plugin_tools: List[AgentTool], session_id: Optional[str], user_id: Optional[str], agent_id: str) -> List[Any]:
        """Helper to construct plugin-based tools."""
        instances = []
        for t in plugin_tools:
            try:
                config = t.base_config or {}
                plugin_id = config.get("plugin_id")
                tool_name = config.get("tool_name")
                if not plugin_id or not tool_name:
                    continue

                # Build schema from parameters list
                props = {}
                req = []
                for p in config.get("parameters", []):
                    p_name = p.get("name")
                    p_type = p.get("type", "string")
                    prop = {"type": "string" if p_type == "enum" else p_type, "description": p.get("description", "")}
                    if p_type == "enum" and "enum_values" in p:
                        prop["enum"] = p["enum_values"]
                    props[p_name] = prop
                    if p.get("required"):
                        req.append(p_name)

                instances.append(create_plugin_tool(
                    plugin_id=plugin_id,
                    tool_name=tool_name,
                    title=t.tool_name,
                    description=config.get("description"),
                    parameters={"type": "object", "properties": props, "required": req} if req else {"type": "object", "properties": props},
                    session_id=session_id,
                    user_id=user_id,
                    agent_id=agent_id,
                ))
            except Exception as exc:
                self._logger.warning(f"Failed to create plugin tool {t.tool_name}", error=str(exc))
        return instances

    def _build_http_webhook_tools(self, http_tools: List[AgentTool]) -> List[Any]:
        """Helper to construct HTTP webhook tools."""
        instances = []
        for t in http_tools:
            try:
                config = t.base_config or {}
                if not t.endpoint:
                    continue
                instances.append(create_http_tool(
                    name=t.tool_name,
                    description=config.get("description") or t.tool_name,
                    endpoint=t.endpoint,
                    method=config.get("method", "POST"),
                    headers=config.get("headers"),
                    parameters=config.get("parameters"),
                    timeout=config.get("timeout", 30.0),
                ))
            except Exception as exc:
                self._logger.warning(f"Failed to create HTTP tool {t.tool_name}", error=str(exc))
        return instances

    async def _build_mcp_server_instances(self, tools_by_endpoint: Dict[str, List[AgentTool]], headers: Dict[str, str]) -> tuple[List[Any], List[str]]:
        """Helper to construct individual MCP server instances (HTTP/SSE/stdio).

        Routing logic:
        - STORE tools → ``_fetch_mcp_tools_from_endpoint`` (ToolStore gateway with API Key auth)
        - LOCAL tools → ``MCPTools`` standard MCP direct connection (internal services)
        """
        instances = []
        stdio_cmds = []
        for endpoint, endpoint_tools in tools_by_endpoint.items():
            try:
                transport = endpoint_tools[0].transport_type or "http"
                if transport == "stdio":
                    stdio_cmds.append(endpoint)
                    continue

                server_url = endpoint.rstrip("/")

                # Use tool_source_type to decide connection mode (not headers)
                is_store_tool = any(
                    t.tool_source_type == "STORE"
                    for t in endpoint_tools
                )

                if is_store_tool and headers:
                    # ToolStore gateway path – needs API Key authentication
                    fetched = await self._fetch_mcp_tools_from_endpoint(server_url, headers)
                    if fetched:
                        instances.extend(fetched)
                    else:
                        self._logger.warning("Dynamic MCP fetch failed", endpoint=endpoint)
                else:
                    # Standard MCP direct connection (LOCAL tools / internal services)
                    mcp = MCPTools(
                        transport="streamable-http" if transport == "http" else "sse",
                        url=server_url,
                    )
                    await mcp.connect()
                    instances.append(mcp)
            except Exception as exc:
                self._logger.warning(f"Failed to setup MCP server {endpoint}", error=str(exc))
        return instances, stdio_cmds

    async def _build_device_mcp_tools(self, internal_agent: "InternalAgent") -> List[Any]:
        """Create MCPTools connection for the agent's bound device.

        Reads ``bound_device_id`` from the internal agent and resolves the
        device-control MCP endpoint template to establish a Streamable HTTP
        connection.

        Returns:
            List containing a single connected MCPTools instance, or empty if
            no device is bound.
        """
        device_id = internal_agent.bound_device_id
        if not device_id:
            return []

        endpoint = settings.device_control_mcp_endpoint.replace("{device_id}", str(device_id))
        self._logger.info(
            "Connecting to device MCP",
            device_id=device_id,
            endpoint=endpoint,
        )

        mcp = MCPTools(transport="streamable-http", url=endpoint)
        await mcp.connect()
        return [mcp]

    async def _build_multi_mcp_stdio(self, stdio_cmds: List[str]) -> List[Any]:
        """Helper to construct MultiMCPTools for stdio servers."""
        try:
            multi = MultiMCPTools(stdio_cmds, allow_partial_failure=True)
            await multi.connect()
            return [multi]
        except Exception as exc:
            self._logger.error("MultiMCPTools initialization failed", error=str(exc))
            return []

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
            raise MissingConfigurationError("Model name is required", config_key="model_name")

        creds = config.provider_credentials
        if not creds:
            raise MissingConfigurationError("LLM provider credentials required", model_name=model_name)
       
        api_key = creds.api_key
        if not api_key:
            raise MissingConfigurationError(f"Missing API key for {model_name}", model_name=model_name)

        # Validation
        if config.temperature is not None and not (0 <= config.temperature <= 2):
            raise InvalidConfigurationError("Temperature must be 0-2", temperature=config.temperature)
        if config.max_tokens is not None and config.max_tokens <= 0:
            raise InvalidConfigurationError("max_tokens must be positive", max_tokens=config.max_tokens)

        provider_kind = (creds.provider_kind or "").lower()
        model_kwargs = {
            "id": model_name,
            "api_key": api_key,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }

        try:
            if provider_kind in {"openai", "openai_compatible"}:
                model_kwargs.update({
                    "role_map": {"system": "system", "user": "user", "assistant": "assistant", "tool": "tool", "model": "assistant"},
                    "base_url": creds.api_base_url,
                    "organization": creds.organization,
                    "timeout": creds.timeout,
                })
                return OpenAIChat(**{k: v for k, v in model_kwargs.items() if v is not None})

            if provider_kind == "anthropic":
                if creds.timeout:
                    model_kwargs["timeout"] = creds.timeout
                return Claude(**{k: v for k, v in model_kwargs.items() if v is not None})

            if provider_kind == "google":
                model_kwargs.update({"base_url": creds.api_base_url, "timeout": creds.timeout})
                return Gemini(**{k: v for k, v in model_kwargs.items() if v is not None})

        except Exception as exc:
            raise InvalidConfigurationError(f"Failed to init {provider_kind} model", model_name=model_name, error=str(exc)) from exc

        raise InvalidConfigurationError(
            f"Unsupported provider: {provider_kind}", 
            model_name=model_name, 
            supported=["openai", "openai_compatible", "anthropic", "google"]
        )
