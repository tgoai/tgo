"""Build direct single-agent runtime instances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agno.agent import Agent, RemoteAgent

from app.config import settings
from app.core.logging import get_logger
from app.models.internal import AgentExecutionContext
from app.runtime.tools.builder.agent_builder import AgentBuilder
from app.runtime.tools.config import ToolsRuntimeSettings
from app.runtime.tools.models import AgentConfig, AgentRunRequest, MCPConfig, RagConfig, WorkflowConfig


@dataclass
class BuiltAgent:
    """Container holding the constructed runnable agent."""

    agent: Agent | RemoteAgent


class AgnoAgentBuilder:
    """Build a single runnable Agno agent from the resolved execution context."""

    def __init__(self, settings_obj: Optional[ToolsRuntimeSettings] = None) -> None:
        runtime_settings = settings_obj or settings.tools_runtime
        self._agent_builder = AgentBuilder(runtime_settings)
        self._logger = get_logger("runtime.supervisor.agents.builder")

    async def build_agent(self, context: AgentExecutionContext) -> BuiltAgent:
        """Build the direct agent for one execution request."""
        request = AgentRunRequest(
            message=context.message,
            config=self._build_agent_config(context),
            session_id=context.session_id,
            user_id=context.user_id,
            project_id=context.project_id,
            agent_id=str(context.agent.id),
            request_id=context.request_id,
            skills_enabled=context.agent.skills_enabled,
            enable_memory=context.enable_memory,
        )
        agno_agent = await self._agent_builder.build_agent(request, internal_agent=context.agent)

        # Keep runtime ids stable so downstream events and cancellations use the persisted agent id.
        agno_agent.id = str(context.agent.id)
        agno_agent.name = context.agent.name or getattr(agno_agent, "name", "Agent")
        try:
            metadata = dict(context.agent.config or {})
            metadata.update(
                {
                    "agent_id": str(context.agent.id),
                    "project_id": context.project_id,
                    "request_id": context.request_id,
                }
            )
            agno_agent.metadata = metadata
        except Exception:  # pragma: no cover - best effort metadata enrichment
            self._logger.debug("Skipping runtime agent metadata update", agent_id=str(context.agent.id))

        return BuiltAgent(agent=agno_agent)

    def _build_agent_config(self, context: AgentExecutionContext) -> AgentConfig:
        """Build the effective AgentConfig for a single runtime execution."""
        config: Dict[str, Any] = dict(context.agent.config or {})

        mcp_config = None
        if context.mcp_url and context.agent.tools:
            mcp_config = MCPConfig(
                url=context.mcp_url,
                tools=[tool.tool_name for tool in context.agent.tools if tool.enabled],
                auth_required=False,
            )

        rag_config = None
        if context.rag_url and context.agent.collections:
            rag_config = RagConfig(
                rag_url=context.rag_url,
                collections=[binding.collection_id for binding in context.agent.collections if binding.enabled],
                project_id=context.project_id,
            )

        workflow_config = None
        workflow_url = getattr(settings, "workflow_service_url", None)
        if workflow_url and context.agent.workflows:
            workflow_config = WorkflowConfig(
                workflow_url=workflow_url,
                workflows=[str(binding.workflow_id) for binding in context.agent.workflows if binding.enabled],
                project_id=context.project_id,
            )

        return AgentConfig(
            model_name=context.agent.model,
            temperature=config.get("temperature"),
            max_tokens=config.get("max_tokens"),
            system_prompt=context.agent.instruction,
            system_message=context.system_message,
            expected_output=context.expected_output or config.get("expected_output"),
            mcp_config=mcp_config,
            rag=rag_config,
            workflow=workflow_config,
            enable_memory=context.enable_memory,
            provider_credentials=context.agent.llm_provider_credentials,
            markdown=config.get("markdown"),
            add_datetime_to_context=config.get("add_datetime_to_context"),
            add_location_to_context=config.get("add_location_to_context"),
            timezone_identifier=config.get("timezone_identifier"),
            tool_call_limit=config.get("tool_call_limit"),
            num_history_runs=config.get("num_history_runs"),
            ui_mode=context.ui_mode,
        )
