"""Build agno teams from supervisor data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import uuid

from agno.team import Team
from agno.agent import Agent

from app.config import settings
from app.models.internal import Agent as InternalAgent
from app.models.internal import CoordinationContext
from app.runtime.tools.builder.agent_builder import AgentBuilder
from app.runtime.tools.models import AgentConfig, AgentRunRequest
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

    def __init__(self, settings_obj: ToolsRuntimeSettings | None = None) -> None:
        settings_obj = settings_obj or settings.tools_runtime
        self._agent_builder = AgentBuilder(settings_obj)
        self._logger = get_logger(__name__)

    async def build_team(self, context: CoordinationContext) -> BuiltTeam:
        """Construct an agno Team for the given coordination context."""
        # Build team members
        members, agent_roles, agent_names = await self._build_members(context)
        # Resolve team model
        team_model = self._resolve_team_model(context, members)

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
    ) -> tuple[List[Agent], Dict[str, str], Dict[str, str]]:
        """Build all team member agents."""
        members: List[Agent] = []
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

    def _resolve_team_model(
        self, context: CoordinationContext, members: List[Agent]
    ) -> Optional[Any]:
        """Resolve the team's LLM model, falling back to first member's model."""
        if context.team.model:
            try:
                return self._agent_builder.resolve_model_instance(
                    AgentConfig(
                        model_name=context.team.model,
                        provider_credentials=context.team.llm_provider_credentials,
                    )
                )
            except InvalidConfigurationError:
                pass

        # Fallback to first member's model
        return getattr(members[0], "model", None) if members else None

    def _build_team_kwargs(
        self,
        context: CoordinationContext,
        members: List[Agent],
        team_model: Optional[Any],
    ) -> Dict[str, Any]:
        """Build the kwargs dict for Team instantiation."""
        self._logger.debug("Building team kwargs", team_model=str(team_model))
        return {
            "members": members,
            "name": context.team.name or "Supervisor Coordination Team",
            "role": "Coordinator",
            "description": context.team.instruction,
            "instructions": settings.supervisor_runtime.team_instructions,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "model": team_model,
            "additional_context": context.system_message,
            "determine_input_for_members": True,
            "delegate_task_to_all_members": False,
            "expected_output": context.expected_output,
            "add_datetime_to_context": True,
            "respond_directly": True, # 直接返回成员的回答，不进行额外的汇总
            "stream_member_events": True,
            "share_member_interactions": False,
            "show_members_responses": False,
            "enable_user_memories": context.enable_memory,
            "add_memories_to_context": context.enable_memory,
            "add_history_to_context": True,
            "num_history_runs": 5,
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
            ("visitor_info", self._create_visitor_info_tool),
            ("visitor_sentiment", self._create_visitor_sentiment_tool),
            ("visitor_tag", self._create_visitor_tag_tool),
            ("ui_templates", self._create_ui_template_tools),
        ]

        for tool_name, creator in tool_creators:
            result = creator(tool_context)
            if result is not None:
                # Handle both single tool and list of tools
                if isinstance(result, list):
                    tools.extend(result)
                else:
                    tools.append(result)

        return tools

    def _create_handoff_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create handoff tool with error handling."""
        try:
            from app.runtime.tools.custom.handoff import create_handoff_tool
            return create_handoff_tool(**ctx)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to add handoff tool", error=str(exc))
            return None

    def _create_visitor_info_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create visitor info tool with error handling."""
        try:
            from app.runtime.tools.custom.visitor_info import create_visitor_info_tool
            return create_visitor_info_tool(**ctx)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to add visitor info tool", error=str(exc))
            return None

    def _create_visitor_sentiment_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create visitor sentiment tool with error handling."""
        try:
            from app.runtime.tools.custom.visitor_sentiment import create_visitor_sentiment_tool
            return create_visitor_sentiment_tool(**ctx)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to add visitor sentiment tool", error=str(exc))
            return None

    def _create_visitor_tag_tool(self, ctx: Dict[str, Any]) -> Optional[Any]:
        """Create visitor tag tool with error handling."""
        try:
            from app.runtime.tools.custom.visitor_tag import create_visitor_tag_tool
            return create_visitor_tag_tool(**ctx)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to add visitor tag tool", error=str(exc))
            return None

    def _create_ui_template_tools(self, ctx: Dict[str, Any]) -> Optional[List[Any]]:
        """Create UI template tools for structured data rendering.

        Args:
            ctx: Tool context (not used for UI templates but kept for consistency).

        Returns:
            List of UI template tool functions, or None if creation fails.
        """
        try:
            from app.ui_templates.tools import get_ui_template, render_ui, list_ui_templates

            # Create function wrappers for UI template operations
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

            self._logger.debug("UI template tools created for team")
            return [ui_get_template, ui_render, ui_list_templates]

        except Exception as exc:  # noqa: BLE001
            self._logger.warning("Failed to create UI template tools", error=str(exc))
            return None

    def _setup_memory(
        self,
        context: CoordinationContext,
        members: List[Agent],
        team_kwargs: Dict[str, Any],
    ) -> None:
        """Setup memory backend if enabled."""
        if not context.enable_memory or not members:
            return

        try:
            memory_manager, memory_db = self._agent_builder.get_memory_backend(
                members[0].model
            )
            team_kwargs.update(db=memory_db, memory_manager=memory_manager)
        except InvalidConfigurationError as exc:
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
    ) -> Agent:
        """Convert an internal agent definition into an agno Agent instance."""
        agent_config = self._build_agent_config(internal_agent, context, config_overrides)

        request = AgentRunRequest(
            message=context.message,
            config=agent_config,
            session_id=context.session_id,
            user_id=context.user_id,
            enable_memory=context.enable_memory,
        )

        # Pass internal_agent to AgentBuilder so it can load MCP tools from agent.tools
        agno_agent = await self._agent_builder.build_agent(request, internal_agent=internal_agent)

        agent_id = str(internal_agent.id) if internal_agent.id else str(uuid.uuid4())
        agno_agent.id = agent_id
        agno_agent.name = internal_agent.name or agno_agent.name
        metadata = dict(internal_agent.config or {})
        metadata.update({
            "role": role,
            "team_agent": True,
        })
        agno_agent.metadata = metadata

        return agno_agent

    def _build_agent_config(
        self,
        internal_agent: InternalAgent,
        context: CoordinationContext,
        overrides: Dict[str, Any],
    ) -> AgentConfig:
        base_config = internal_agent.config or {}
        combined = {**base_config, **overrides}

        mcp_config = None
        if context.mcp_url and internal_agent.tools:
            from app.runtime.tools.models import MCPConfig

            mcp_config = MCPConfig(
                url=context.mcp_url,
                tools=[tool.tool_name for tool in internal_agent.tools if tool.enabled],
                auth_required=False,
            )

        rag_config = None
        if context.rag_url and internal_agent.collections:
            from app.runtime.tools.models import RagConfig

            rag_config = RagConfig(
                rag_url=context.rag_url,
                collections=[str(binding.id) for binding in internal_agent.collections],
                api_key=context.rag_api_key,
                project_id=str(context.project_id) if context.project_id is not None else None,
            )

        # Resolve provider credentials: Agent-level overrides Team-level; otherwise error later in builder
        provider_credentials = (
            internal_agent.llm_provider_credentials
            or getattr(context.team, "llm_provider_credentials", None)
        )

        return AgentConfig(
            model_name=internal_agent.model,
            temperature=combined.get("temperature"),
            max_tokens=combined.get("max_tokens"),
            system_prompt=internal_agent.instruction,
            mcp_config=mcp_config,
            rag=rag_config,
            enable_memory=context.enable_memory,
            provider_credentials=provider_credentials,
        )
