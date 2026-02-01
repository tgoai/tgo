"""Build agno teams from supervisor data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
import uuid
import asyncio

from agno.team import Team
from agno.agent import Agent, RemoteAgent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.runtime.tools.builder.agent_builder import AgentBuilder, StoreRemoteAgent


class ComputerUseRemoteAgent(RemoteAgent):
    """RemoteAgent wrapper that passes device_id via HTTP Header for Computer Use agents.
    
    This extends Agno's native RemoteAgent to automatically include the bound device_id
    in the X-Device-ID HTTP header when the agent is invoked, allowing the tgo-device-control
    AgentOS to know which device to control.
    """
    
    def __init__(
        self,
        base_url: str,
        agent_id: str,
        device_id: str,
        timeout: float = 120.0,
        **kwargs,
    ):
        super().__init__(base_url=base_url, agent_id=agent_id, timeout=timeout, **kwargs)
        self._device_id = device_id
    
    def _get_auth_headers(self, auth_token: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Add X-Device-ID header along with any base auth headers."""
        headers: Dict[str, str] = {}
        # Call parent to get existing headers if any
        try:
            if hasattr(super(), "_get_auth_headers"):
                headers = super()._get_auth_headers(auth_token) or {}
            elif hasattr(super(), "get_auth_headers"):
                headers = super().get_auth_headers(auth_token) or {}
        except Exception:
            pass
        
        # Inject device ID via header
        headers["X-Device-ID"] = self._device_id
        return headers
    
    def get_auth_headers(self, auth_token: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Public version of get_auth_headers."""
        return self._get_auth_headers(auth_token)
from app.services.api_service import api_service_client

from app.config import settings
from app.models.internal import Agent as InternalAgent
from app.models.internal import CoordinationContext
from app.models.llm_provider import LLMProvider
from app.models.project_ai_config import ProjectAIConfig
from app.runtime.tools.models import (
    AgentConfig, 
    AgentRunRequest, 
    LLMProviderCredentials,
    MCPConfig,
    RagConfig,
    WorkflowConfig
)
from app.runtime.tools.config import ToolsRuntimeSettings
from app.runtime.core.exceptions import InvalidConfigurationError
from app.core.logging import get_logger


@dataclass
class BuiltTeam:
    """Container holding the constructed agno team and member metadata."""

    team: Team
    agent_roles: Dict[str, str]
    agent_names: Dict[str, str]


class AgnoTeamBuilder:
    """Build agno teams from persisted supervisor entities."""

    def __init__(
        self, 
        settings_obj: ToolsRuntimeSettings | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None
    ) -> None:
        settings_obj = settings_obj or settings.tools_runtime
        self._agent_builder = AgentBuilder(settings_obj)
        self._session_factory = session_factory
        self._logger = get_logger(__name__)

    async def build_team(self, context: CoordinationContext) -> BuiltTeam:
        """Construct an agno Team for the given coordination context."""
        # Build team members
        members, agent_roles, agent_names = await self._build_members(context)
        # Resolve team model
        team_model = await self._resolve_team_model(context, members)

        # Build team kwargs
        team_kwargs = self._build_team_kwargs(context, members, team_model)

        # Inject team-level tools
        team_kwargs["tools"] = self._build_team_tools(context)

        # Setup memory if enabled
        self._setup_memory(context, members, team_kwargs)

        return BuiltTeam(
            team=Team(**team_kwargs),
            agent_roles=agent_roles,
            agent_names=agent_names,
        )

    async def _build_members(
        self, context: CoordinationContext
    ) -> tuple[List[Union[Agent, RemoteAgent]], Dict[str, str], Dict[str, str]]:
        """Build all team member agents."""
        members: List[Union[Agent, RemoteAgent]] = []
        agent_roles: Dict[str, str] = {}
        agent_names: Dict[str, str] = {}
        for internal_agent in context.team.agents:
            member_agent = await self._create_member_agent(
                internal_agent,
                context,
                config_overrides=internal_agent.config or {},
                role="member",
            )
            members.append(member_agent)
            agent_roles[member_agent.id] = "member"
            agent_names[member_agent.id] = member_agent.name or "Team Member"

        return members, agent_roles, agent_names

    async def _resolve_fallback_provider(self, project_id: str) -> Optional[dict]:
        """Fetch project default or first available LLM Provider from database."""
        if not self._session_factory:
            self._logger.warning("No session factory provided to TeamBuilder, cannot resolve fallback provider")
            return None

        try:
            project_uuid = uuid.UUID(project_id) if isinstance(project_id, str) else project_id
        except (ValueError, TypeError):
            self._logger.warning(f"Invalid project_id format: {project_id}")
            return None

        async with self._session_factory() as session:
            # 1. Check ProjectAIConfig for default chat configuration
            try:
                config = await session.get(ProjectAIConfig, project_uuid)
                if config and config.default_chat_provider_id:
                    provider = await session.get(LLMProvider, config.default_chat_provider_id)
                    if provider and provider.is_active:
                        return {
                            "model": config.default_chat_model or provider.default_model or provider.alias,
                            "credentials": LLMProviderCredentials(
                                provider_kind=provider.provider_kind,
                                api_key=provider.api_key,
                                api_base_url=provider.api_base_url,
                                organization=provider.organization,
                                timeout=provider.timeout,
                            )
                        }
            except Exception as e:
                self._logger.warning(f"Failed to fetch ProjectAIConfig for {project_id}: {e}")

            # 2. Fallback to first available Provider in the project
            try:
                stmt = select(LLMProvider).where(
                    LLMProvider.project_id == project_uuid,
                    LLMProvider.is_active == True
                ).limit(1)
                result = await session.execute(stmt)
                provider = result.scalar_one_or_none()
                
                if provider:
                    return {
                        "model": provider.default_model or provider.alias,
                        "credentials": LLMProviderCredentials(
                            provider_kind=provider.provider_kind,
                            api_key=provider.api_key,
                            api_base_url=provider.api_base_url,
                            organization=provider.organization,
                            timeout=provider.timeout,
                        )
                    }
            except Exception as e:
                self._logger.warning(f"Failed to fetch first available provider for {project_id}: {e}")
            
            return None

    async def _resolve_team_model(
        self, context: CoordinationContext, members: List[Union[Agent, RemoteAgent]]
    ) -> Optional[Any]:
        """Resolve the team's LLM model with fallback logic."""
        # 1. Try Team configured LLM Provider
        if context.team.llm_provider_credentials:
            try:
                return self._agent_builder.resolve_model_instance(
                    AgentConfig(
                        model_name=context.team.model,
                        provider_credentials=context.team.llm_provider_credentials,
                    )
                )
            except InvalidConfigurationError:
                pass

        # 2. Try project default configuration or first available Provider
        if context.project_id:
            fallback = await self._resolve_fallback_provider(context.project_id)
            if fallback:
                try:
                    return self._agent_builder.resolve_model_instance(
                        AgentConfig(
                            model_name=fallback["model"],
                            provider_credentials=fallback["credentials"],
                        )
                    )
                except InvalidConfigurationError:
                    pass

        # 3. Fallback to first member's model (original logic)
        return getattr(members[0], "model", None) if members else None

    def _build_team_kwargs(
        self,
        context: CoordinationContext,
        members: List[Union[Agent, RemoteAgent]],
        team_model: Optional[Any],
    ) -> Dict[str, Any]:
        """Build the kwargs dict for Team instantiation."""
        # Extract config and merge with defaults
        config = context.team.config or {}
        
        self._logger.debug(
            "Building team kwargs", 
            team_id=str(context.team.id),
            team_model=str(team_model),
            members_count=len(members)
        )

        return {
            "members": members,
            "name": context.team.name or "Supervisor Coordination Team",
            "role": config.get("role", "Coordinator"),
            "description": context.team.instruction,
            "instructions": settings.supervisor_runtime.team_instructions,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "model": team_model,
            "additional_context": context.system_message,
            "determine_input_for_members": config.get("determine_input_for_members", True),
            "delegate_task_to_all_members": config.get("delegate_to_all_members", False),
            "expected_output": context.expected_output,
            "add_datetime_to_context": config.get("add_datetime_to_context", True),
            "add_location_to_context": config.get("add_location_to_context", False),
            "timezone_identifier": config.get("timezone_identifier"),
            "markdown": config.get("markdown", True),
            "respond_directly": config.get("respond_directly", False),
            "stream_member_events": config.get("stream_member_events", True),
            "share_member_interactions": config.get("share_member_interactions", False),
            "show_members_responses": config.get("show_members_responses", False),
            "tool_call_limit": config.get("tool_call_limit"),
            "enable_user_memories": context.enable_memory,
            "add_memories_to_context": context.enable_memory,
            "add_history_to_context": config.get("add_history_to_context", True),
            "num_history_runs": config.get("num_history_runs", 5),
            "metadata": {"team_id": str(context.team.id)},
        }

    def _build_team_tools(self, context: CoordinationContext) -> List[Any]:
        """Build team-level tools with graceful error handling."""
        tools: List[Any] = []
        tool_context = {
            "team_id": str(context.team.id),
            "session_id": context.session_id,
            "user_id": context.user_id,
            "project_id": context.project_id,
        }

        # Tool creators with their names for logging
        tool_creators: List[tuple[str, Callable]] = [
            ("handoff", self._create_handoff_tool),
            ("user_info", self._create_user_info_tool),
            ("user_sentiment", self._create_user_sentiment_tool),
            ("user_tag", self._create_user_tag_tool),
            ("ui_templates", self._create_ui_template_tools),
        ]

        for tool_name, creator in tool_creators:
            try:
                result = creator(tool_context)
                if result is not None:
                    if isinstance(result, list):
                        tools.extend(result)
                    else:
                        tools.append(result)
            except Exception as exc:
                self._logger.warning(f"Error creating tool '{tool_name}'", error=str(exc))

        return tools

    def _create_handoff_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create handoff tool with error handling."""
        try:
            from app.runtime.tools.custom.handoff import create_handoff_tool
            return create_handoff_tool(**ctx)
        except ImportError:
            self._logger.debug("Handoff tool module not found, skipping")
            return None
        except Exception as exc:
            self._logger.warning("Failed to add handoff tool", error=str(exc))
            return None

    def _create_user_info_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create user info tool with error handling."""
        try:
            from app.runtime.tools.custom.user_info import create_user_info_tool
            return create_user_info_tool(**ctx)
        except ImportError:
            return None
        except Exception as exc:
            self._logger.warning("Failed to add user info tool", error=str(exc))
            return None

    def _create_user_sentiment_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create user sentiment tool with error handling."""
        try:
            from app.runtime.tools.custom.user_sentiment import create_user_sentiment_tool
            return create_user_sentiment_tool(**ctx)
        except ImportError:
            return None
        except Exception as exc:
            self._logger.warning("Failed to add user sentiment tool", error=str(exc))
            return None

    def _create_user_tag_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create user tag tool with error handling."""
        try:
            from app.runtime.tools.custom.user_tag import create_user_tag_tool
            return create_user_tag_tool(**ctx)
        except ImportError:
            return None
        except Exception as exc:
            self._logger.warning("Failed to add user tag tool", error=str(exc))
            return None

    def _create_ui_template_tools(self, ctx: Dict[str, Any]) -> Optional[List[Any]]:
        """Create UI template tools for structured data rendering."""
        try:
            from app.ui_templates.tools import get_ui_template, render_ui, list_ui_templates

            # Use descriptive names for tool functions
            ui_get_template = get_ui_template
            ui_render = render_ui
            ui_list_templates = list_ui_templates

            # Assign docstrings for Agent understanding if not already present
            if not ui_get_template.__doc__:
                ui_get_template.__doc__ = "获取指定 UI 模板的详细 schema 格式和使用示例。"
            if not ui_render.__doc__:
                ui_render.__doc__ = "将业务数据渲染为前端可识别的 UI 组件代码块 (tgo-ui-widget)。"
            if not ui_list_templates.__doc__:
                ui_list_templates.__doc__ = "列出所有可用的 UI 模板及其简短描述。"

            self._logger.debug("UI template tools created for team")
            return [ui_get_template, ui_render, ui_list_templates]

        except ImportError:
            return None
        except Exception as exc:
            self._logger.warning("Failed to create UI template tools", error=str(exc))
            return None

    def _setup_memory(
        self,
        context: CoordinationContext,
        members: List[Union[Agent, RemoteAgent]],
        team_kwargs: Dict[str, Any],
    ) -> None:
        """Setup memory backend if enabled."""
        if not context.enable_memory or not members:
            return

        try:
            # Safely get model from the first member
            model = getattr(members[0], "model", None)
            memory_manager, memory_db = self._agent_builder.get_memory_backend(model)
            team_kwargs.update(db=memory_db, memory_manager=memory_manager)
        except Exception as exc:
            self._logger.warning(
                "Memory backend unavailable; continuing without persistence",
                error=str(exc),
            )

    async def _create_member_agent(
        self,
        internal_agent: InternalAgent,
        context: CoordinationContext,
        *,
        config_overrides: Dict[str, Any],
        role: str,
    ) -> Union[Agent, RemoteAgent]:
        """Convert an internal agent definition into an agno Agent or RemoteAgent."""
        # 1. Handle Computer Use Agents (device control)
        if getattr(internal_agent, "agent_category", "normal") == "computer_use":
            return await self._build_computer_use_agent(internal_agent, context, role)

        # 2. Handle Local Agents
        return await self._build_local_agent(internal_agent, context, config_overrides, role)

    async def _build_computer_use_agent(
        self,
        internal_agent: InternalAgent,
        context: CoordinationContext,
        role: str,
    ) -> ComputerUseRemoteAgent:
        """Build a Computer Use Agent using ComputerUseRemoteAgent wrapper.
        
        Computer Use Agents are special agents that control remote devices
        through the tgo-device-control AgentOS service. The device_id is
        automatically injected into messages when the agent runs.
        """
        # Get bound device ID from config
        agent_config = internal_agent.config or {}
        device_id = agent_config.get("bound_device_id")
        
        if not device_id:
            self._logger.warning(
                f"Computer Use Agent {internal_agent.name} has no bound device",
                agent_id=str(internal_agent.id),
            )
            raise ValueError(f"Computer Use Agent {internal_agent.name} must have a bound device")
        
        self._logger.info(
            f"Building Computer Use Agent with device {device_id}",
            agent_id=str(internal_agent.id),
            agent_name=internal_agent.name,
            device_id=device_id,
        )
        
        # Create ComputerUseRemoteAgent pointing to tgo-device-control AgentOS
        # The device_id is automatically injected into messages
        agent_id = str(internal_agent.id) if internal_agent.id else str(uuid.uuid4())
        
        # Store device_id in metadata for reference
        metadata = {
            "role": role,
            "team_agent": True,
            "is_remote": True,
            "agent_category": "computer_use",
            "device_id": device_id,
        }
        
        remote_agent = ComputerUseRemoteAgent(
            base_url=settings.device_control_agentos_url,
            agent_id=settings.device_control_agent_id,
            device_id=device_id,
            timeout=120.0,  # Computer use tasks may take longer
        )
        
        # Override agent properties
        remote_agent.id = agent_id
        remote_agent.name = internal_agent.name or "Computer Use Agent"
        remote_agent.metadata = metadata
        
        return remote_agent

    async def _build_remote_agent(
        self, 
        internal_agent: InternalAgent, 
        context: CoordinationContext, 
        role: str
    ) -> StoreRemoteAgent:
        """Helper to construct a StoreRemoteAgent."""
        api_key = None
        if context.project_id:
            try:
                credential = await api_service_client.get_store_credential(context.project_id)
                if credential:
                    api_key = credential.get("api_key")
                else:
                    self._logger.warning(f"No store credential found for project {context.project_id}")
            except Exception as e:
                self._logger.warning(f"Failed to fetch store credential: {e}")
        else:
            self._logger.warning("No project_id provided, skipping store credentials")

        # Load local tools if any
        local_tools = []
        if internal_agent.tools:
            try:
                local_tools = await self._build_tools_for_remote_agent(internal_agent, context)
                self._logger.debug(
                    f"Loaded {len(local_tools)} local tools for remote agent",
                    agent_id=str(internal_agent.id),
                )
            except Exception as e:
                self._logger.warning(f"Failed to load local tools for remote agent: {e}")

        # Construct metadata
        agent_id = str(internal_agent.id) if internal_agent.id else str(uuid.uuid4())
        metadata = dict(internal_agent.config or {})
        metadata.update({
            "role": role,
            "team_agent": True,
            "is_remote": True,
        })

        return StoreRemoteAgent(
            base_url=internal_agent.remote_agent_url,
            agent_id=internal_agent.store_agent_id,
            timeout=60.0,
            override_id=agent_id,
            override_name=internal_agent.name,
            override_metadata=metadata,
            api_key=api_key,
            tools=local_tools,
        )

    async def _build_local_agent(
        self,
        internal_agent: InternalAgent,
        context: CoordinationContext,
        config_overrides: Dict[str, Any],
        role: str,
    ) -> Agent:
        """Helper to construct a local Agno Agent."""
        agent_config = self._build_agent_config(internal_agent, context, config_overrides)

        request = AgentRunRequest(
            message=context.message,
            config=agent_config,
            session_id=context.session_id,
            user_id=context.user_id,
            project_id=context.project_id,
            enable_memory=context.enable_memory,
        )

        # Build agent instance
        agno_agent = await self._agent_builder.build_agent(request, internal_agent=internal_agent)

        # Set IDs and metadata
        agent_id = str(internal_agent.id) if internal_agent.id else str(uuid.uuid4())
        agno_agent.id = agent_id
        agno_agent.name = internal_agent.name or agno_agent.name
        
        metadata = dict(internal_agent.config or {})
        metadata.update({
            "role": role,
            "team_agent": True,
            "is_remote": False,
        })
        agno_agent.metadata = metadata

        return agno_agent

    def _build_agent_config(
        self,
        internal_agent: InternalAgent,
        context: CoordinationContext,
        overrides: Dict[str, Any],
    ) -> AgentConfig:
        """Build a consolidated AgentConfig for member construction."""
        config = {**(internal_agent.config or {}), **overrides}

        mcp_config = None
        if context.mcp_url and internal_agent.tools:
            mcp_config = MCPConfig(
                url=context.mcp_url,
                tools=[tool.tool_name for tool in internal_agent.tools if tool.enabled],
                auth_required=False,
            )

        rag_config = None
        if context.rag_url and internal_agent.collections:
            rag_config = RagConfig(
                rag_url=context.rag_url,
                collections=[b.collection_id for b in internal_agent.collections if b.enabled],
                api_key=context.rag_api_key,
                project_id=str(context.project_id) if context.project_id else None,
                # filters={"content_type": "qa_pair"} # TODO: 这里暂时去掉过滤条件，目前问题：加了过滤条件后，旧数据搜索结果为空
            )

        workflow_config = None
        workflow_url = getattr(settings, "workflow_service_url", None)
        if workflow_url and internal_agent.workflows:
            workflow_config = WorkflowConfig(
                workflow_url=workflow_url,
                workflows=[str(b.workflow_id) for b in internal_agent.workflows if b.enabled],
                project_id=str(context.project_id) if context.project_id else None,
            )

        # Resolve provider credentials: Agent-level overrides Team-level
        provider_credentials = (
            internal_agent.llm_provider_credentials
            or getattr(context.team, "llm_provider_credentials", None)
        )

        return AgentConfig(
            model_name=internal_agent.model,
            temperature=config.get("temperature"),
            max_tokens=config.get("max_tokens"),
            system_prompt=internal_agent.instruction,
            mcp_config=mcp_config,
            rag=rag_config,
            workflow=workflow_config,
            enable_memory=context.enable_memory,
            provider_credentials=provider_credentials,
            markdown=config.get("markdown"),
            add_datetime_to_context=config.get("add_datetime_to_context"),
            add_location_to_context=config.get("add_location_to_context"),
            timezone_identifier=config.get("timezone_identifier"),
            show_tool_calls=config.get("show_tool_calls"),
            tool_call_limit=config.get("tool_call_limit"),
            num_history_runs=config.get("num_history_runs"),
        )

    async def _build_tools_for_remote_agent(
        self,
        internal_agent: InternalAgent,
        context: CoordinationContext,
    ) -> List[Any]:
        """
        为远程 Agent 构建本地工具。
        
        复用 AgentBuilder 的工具构建逻辑，确保本地工具可以被远程 Agent 使用。
        """
        # 使用 AgentBuilder 的工具构建能力
        # 构建一个临时的 AgentConfig 来触发工具加载
        config = AgentConfig(
            model_name=internal_agent.model or "gpt-4o",  # 远程 Agent 实际上不会使用这个模型
            system_prompt=internal_agent.instruction,
        )
        
        # 创建一个临时的 request 对象
        request = AgentRunRequest(
            message="",  # 不会实际使用
            config=config,
            session_id=context.session_id,
            user_id=context.user_id,
            project_id=context.project_id,
        )
        
        # 调用 AgentBuilder 的私有方法来构建工具
        try:
            tools = await self._agent_builder._build_mcp_tools_from_agent(
                internal_agent,
                context.session_id,
                context.user_id,
                project_id=context.project_id,
            )
            return tools or []
        except Exception as e:
            self._logger.warning(f"Failed to build tools for remote agent: {e}")
            return []
