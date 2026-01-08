"""Adapters bridging coordination runtime with local services."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
from typing import Dict, List, Optional

# settings import removed; no longer using default_team_model
from app.core.logging import get_logger
from app.models.agent import Agent as DBAgent
from app.models.team import Team as DBTeam
from app.models.internal import (
    Agent as InternalAgent,
    AgentCollection as InternalAgentCollection,
    AgentWorkflow as InternalAgentWorkflow,
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentTool as InternalAgentTool,
    Team as InternalTeam,
)
from app.runtime.tools.models import (
    AgentConfig,
    AgentRunRequest,
    MCPConfig,
    RagConfig,
    WorkflowConfig,
    LLMProviderCredentials,
    CompleteStreamEvent,
    ContentStreamEvent,
    ErrorStreamEvent,
    ToolCallStreamEvent,
)
from app.runtime.tools.executor.service import ToolsRuntimeService
from app.runtime.supervisor.streaming.workflow_events import WorkflowEventEmitter
from app.services.team_service import TeamService
from app.runtime.core.exceptions import (
    AgentExecutionError,
    StreamingError,
    TransformationError,
    DataMappingError,
)




logger = get_logger(__name__)


def _safe_uuid(value: str) -> uuid.UUID:
    """Convert string to UUID, falling back to namespace UUID if invalid."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):  # pragma: no cover - defensive
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


def _convert_agent(
    agent: DBAgent,
    tool_associations_map: Optional[Dict[uuid.UUID, Dict[str, any]]] = None,
) -> InternalAgent:
    """Convert database agent to internal agent model.

    Args:
        agent: Database agent model
        tool_associations_map: Optional map of tool_id -> association data (enabled, permissions, config)

    Returns:
        InternalAgent: Converted internal agent model

    Raises:
        DataMappingError: If required fields are missing or conversion fails
    """
    try:
        # Validate required fields
        if not agent.id:
            raise DataMappingError(
                "Agent ID is required",
                agent_name=agent.name if hasattr(agent, 'name') else None
            )
        if not agent.name:
            raise DataMappingError(
                "Agent name is required",
                agent_id=str(agent.id)
            )
        if not agent.model:
            raise DataMappingError(
                "Agent model is required",
                agent_id=str(agent.id),
                agent_name=agent.name
            )

        # Convert tools
        # Note: agent.tools is a list of Tool entities from ai_tools table
        # We need to get association data (enabled, permissions, config) from tool_associations_map
        tools = []
        for tool in agent.tools:
            try:
                # Get association data for this tool
                assoc_data = (tool_associations_map or {}).get(tool.id, {})
                enabled = assoc_data.get('enabled', True)
                permissions = assoc_data.get('permissions') or []
                tool_config = assoc_data.get('config') or {}

                tools.append(
                    InternalAgentTool(
                        tool_id=tool.id,
                        tool_name=tool.name,
                        tool_type=str(tool.tool_type.value) if hasattr(tool.tool_type, 'value') else str(tool.tool_type),
                        enabled=enabled,
                        permissions=permissions,
                        tool_config=tool_config,
                        transport_type=tool.transport_type,
                        endpoint=tool.endpoint,
                        base_config=tool.config or {},
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to convert agent tool, skipping",
                    agent_id=str(agent.id),
                    agent_name=agent.name,
                    tool_id=str(tool.id) if hasattr(tool, 'id') else 'unknown',
                    tool_name=getattr(tool, 'name', 'unknown'),
                    error=str(e),
                    error_type=type(e).__name__
                )
                continue

        # Convert collections
        collections: List[InternalAgentCollection] = []
        for binding in agent.collections:
            try:
                collection_id = _safe_uuid(binding.collection_id)
                collections.append(
                    InternalAgentCollection(
                        id=collection_id,
                        display_name=str(binding.collection_id),
                        description=None,
                        collection_metadata={"enabled": binding.enabled},
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to convert agent collection, skipping",
                    agent_id=str(agent.id),
                    agent_name=agent.name,
                    collection_id=str(binding.collection_id) if hasattr(binding, 'collection_id') else 'unknown',
                    error=str(e),
                    error_type=type(e).__name__
                )
                continue

        # Convert workflows
        workflows: List[InternalAgentWorkflow] = []
        for binding in agent.workflows:
            try:
                workflows.append(
                    InternalAgentWorkflow(
                        id=binding.id,
                        workflow_id=binding.workflow_id,
                        enabled=binding.enabled,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Failed to convert agent workflow, skipping",
                    agent_id=str(agent.id),
                    agent_name=agent.name,
                    workflow_id=str(binding.workflow_id) if hasattr(binding, 'workflow_id') else 'unknown',
                    error=str(e),
                    error_type=type(e).__name__
                )
                continue

        # Extract provider credentials (agent-level)
        provider_credentials = None
        try:
            provider = getattr(agent, "llm_provider", None)
            if provider is not None:
                kind = getattr(provider, "provider_kind", None)
                api_key = getattr(provider, "api_key", None)
                if kind and api_key:
                    provider_credentials = LLMProviderCredentials(
                        provider_kind=kind,
                        vendor=getattr(provider, "vendor", None),
                        api_base_url=getattr(provider, "api_base_url", None),
                        api_key=api_key,
                        organization=getattr(provider, "organization", None),
                        timeout=getattr(provider, "timeout", None),
                    )
        except Exception as e:
            logger.warning(
                "Failed to extract agent provider credentials",
                agent_id=str(agent.id),
                agent_name=agent.name,
                error=str(e),
                error_type=type(e).__name__,
            )

        # Create internal agent
        return InternalAgent(
            id=agent.id,
            name=agent.name,
            instruction=agent.instruction,
            model=agent.model,
            config=agent.config or {},
            team_id=str(agent.team_id) if agent.team_id else None,
            tools=tools,
            collections=collections,
            workflows=workflows,
            is_default=agent.is_default,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            llm_provider_credentials=provider_credentials,
        )
    except DataMappingError:
        # Re-raise data mapping errors
        raise
    except Exception as e:
        raise DataMappingError(
            "Failed to convert agent to internal model",
            agent_id=str(agent.id) if hasattr(agent, 'id') else None,
            agent_name=agent.name if hasattr(agent, 'name') else None,
            error=str(e)
        ) from e


async def _convert_team(team: DBTeam, team_service: TeamService) -> InternalTeam:
    """Convert database team to internal team model.

    Args:
        team: Database team model
        team_service: Team service for querying association data

    Returns:
        InternalTeam: Converted internal team model

    Raises:
        DataMappingError: If required fields are missing or conversion fails
    """
    try:
        # Validate required fields
        if not team.id:
            raise DataMappingError(
                "Team ID is required",
                team_name=team.name if hasattr(team, 'name') else None
            )
        if not team.name:
            raise DataMappingError(
                "Team name is required",
                team_id=str(team.id)
            )

        # Build tool associations map for all agents in this team
        # Map structure: {agent_id: {tool_id: {enabled, permissions, config}}}
        from app.models.agent import AgentToolAssociation
        from sqlalchemy import select, and_

        agent_ids = [agent.id for agent in team.agents if agent.id]
        tool_associations_by_agent: Dict[uuid.UUID, Dict[uuid.UUID, Dict[str, any]]] = {}

        if agent_ids:
            # Query all tool associations for agents in this team
            stmt = select(AgentToolAssociation).where(
                and_(
                    AgentToolAssociation.agent_id.in_(agent_ids),
                    AgentToolAssociation.deleted_at.is_(None),
                )
            )
            result = await team_service.db.execute(stmt)
            associations = result.scalars().all()

            # Build the map
            for assoc in associations:
                if assoc.agent_id not in tool_associations_by_agent:
                    tool_associations_by_agent[assoc.agent_id] = {}
                tool_associations_by_agent[assoc.agent_id][assoc.tool_id] = {
                    'enabled': assoc.enabled,
                    'permissions': assoc.permissions,
                    'config': assoc.config,
                }

        # Convert agents (with error handling for individual agents)
        agents = []
        for agent in team.agents:
            try:
                # Get tool associations map for this specific agent
                agent_tool_map = tool_associations_by_agent.get(agent.id, {})
                agents.append(_convert_agent(agent, tool_associations_map=agent_tool_map))
            except DataMappingError as e:
                logger.warning(
                    "Failed to convert team agent, skipping",
                    team_id=str(team.id),
                    team_name=team.name,
                    agent_id=str(agent.id) if hasattr(agent, 'id') else None,
                    agent_name=agent.name if hasattr(agent, 'name') else None,
                    error=str(e)
                )
                continue
            except Exception as e:
                logger.warning(
                    "Unexpected error converting team agent, skipping",
                    team_id=str(team.id),
                    team_name=team.name,
                    agent_id=str(agent.id) if hasattr(agent, 'id') else None,
                    error=str(e),
                    error_type=type(e).__name__
                )
                continue

        # Extract provider credentials (team-level)
        team_provider_credentials = None
        try:
            provider = getattr(team, "llm_provider", None)
            if provider is not None:
                kind = getattr(provider, "provider_kind", None)
                api_key = getattr(provider, "api_key", None)
                if kind and api_key:
                    team_provider_credentials = LLMProviderCredentials(
                        provider_kind=kind,
                        vendor=getattr(provider, "vendor", None),
                        api_base_url=getattr(provider, "api_base_url", None),
                        api_key=api_key,
                        organization=getattr(provider, "organization", None),
                        timeout=getattr(provider, "timeout", None),
                    )
        except Exception as e:
            logger.warning(
                "Failed to extract team provider credentials",
                team_id=str(team.id),
                team_name=team.name,
                error=str(e),
                error_type=type(e).__name__,
            )

        # Create internal team
        return InternalTeam(
            id=str(team.id),
            name=team.name,
            model=team.model,
            instruction=team.instruction,
            expected_output=team.expected_output,
            config=team.config or {},
            session_id=team.session_id,
            is_default=team.is_default,
            agents=agents,
            created_at=team.created_at,
            updated_at=team.updated_at,
            llm_provider_credentials=team_provider_credentials,
        )
    except DataMappingError:
        # Re-raise data mapping errors
        raise
    except Exception as e:
        raise DataMappingError(
            "Failed to convert team to internal model",
            team_id=str(team.id) if hasattr(team, 'id') else None,
            team_name=team.name if hasattr(team, 'name') else None,
            error=str(e)
        ) from e


class AIServiceClient:
    """Adapter that exposes team data in coordinator-friendly format."""

    def __init__(self, team_service: TeamService, project_id: uuid.UUID) -> None:
        self._team_service = team_service
        self._project_id = project_id
        self.logger = get_logger(__name__)

    async def __aenter__(self) -> "AIServiceClient":  # pragma: no cover - context manager convenience
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - nothing to cleanup
        return None

    async def get_team_with_agents(self, team_id: str, auth_headers: Dict[str, str]) -> InternalTeam:
        """Get team with agents by team ID.

        Args:
            team_id: Team ID or "default" for unassigned agents
            auth_headers: Authentication headers (unused but part of interface)

        Returns:
            InternalTeam: Team with converted agents

        Raises:
            DataMappingError: If team or agent conversion fails
            TransformationError: If data transformation fails
        """
        try:
            if team_id == "default":
                self.logger.debug(
                    "Fetching unassigned agents",
                    project_id=str(self._project_id)
                )
                agents = await self._team_service.get_unassigned_agents(self._project_id)

                # Build tool associations map for unassigned agents
                from app.models.agent import AgentToolAssociation
                from sqlalchemy import select, and_

                agent_ids = [agent.id for agent in agents if agent.id]
                tool_associations_by_agent: Dict[uuid.UUID, Dict[uuid.UUID, Dict[str, any]]] = {}

                if agent_ids:
                    stmt = select(AgentToolAssociation).where(
                        and_(
                            AgentToolAssociation.agent_id.in_(agent_ids),
                            AgentToolAssociation.deleted_at.is_(None),
                        )
                    )
                    result = await self._team_service.db.execute(stmt)
                    associations = result.scalars().all()

                    for assoc in associations:
                        if assoc.agent_id not in tool_associations_by_agent:
                            tool_associations_by_agent[assoc.agent_id] = {}
                        tool_associations_by_agent[assoc.agent_id][assoc.tool_id] = {
                            'enabled': assoc.enabled,
                            'permissions': assoc.permissions,
                            'config': assoc.config,
                        }

                # Convert agents with error handling
                converted_agents = []
                for agent in agents:
                    try:
                        agent_tool_map = tool_associations_by_agent.get(agent.id, {})
                        converted_agents.append(_convert_agent(agent, tool_associations_map=agent_tool_map))
                    except DataMappingError as e:
                        self.logger.warning(
                            "Failed to convert unassigned agent, skipping",
                            agent_id=str(agent.id) if hasattr(agent, 'id') else None,
                            error=str(e)
                        )
                        continue

                if not converted_agents:
                    raise TransformationError(
                        "No unassigned agents found to build default team",
                        project_id=str(self._project_id),
                        team_id="default",
                    )

                first_agent = converted_agents[0]
                return InternalTeam(
                    id="default",
                    name="Unassigned Agents",
                    model=first_agent.model,
                    instruction=None,
                    expected_output=None,
                    config={},
                    session_id=None,
                    is_default=False,
                    agents=converted_agents,
                    llm_provider_credentials=getattr(first_agent, "llm_provider_credentials", None),
                    created_at=datetime.now(tz=timezone.utc),
                    updated_at=datetime.now(tz=timezone.utc),
                )

            # Convert team_id to UUID
            try:
                team_uuid = uuid.UUID(str(team_id))
            except (ValueError, TypeError) as e:
                raise TransformationError(
                    "Invalid team ID format",
                    team_id=team_id,
                    error=str(e)
                ) from e

            self.logger.debug(
                "Fetching team with agents",
                team_id=str(team_uuid),
                project_id=str(self._project_id)
            )

            # Fetch team
            try:
                db_team = await self._team_service.get_team(self._project_id, team_uuid)
            except Exception as e:
                raise TransformationError(
                    "Failed to fetch team from database",
                    team_id=str(team_uuid),
                    project_id=str(self._project_id),
                    error=str(e)
                ) from e

            # Convert team
            return await _convert_team(db_team, self._team_service)

        except (DataMappingError, TransformationError):
            # Re-raise specific errors
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error getting team with agents",
                team_id=team_id,
                project_id=str(self._project_id),
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise TransformationError(
                "Unexpected error getting team with agents",
                team_id=team_id,
                project_id=str(self._project_id),
                error=str(e)
            ) from e

    async def list_teams(self, auth_headers: Dict[str, str], limit: int = 20, offset: int = 0) -> List[InternalTeam]:
        """List teams for the project.

        Args:
            auth_headers: Authentication headers (unused but part of interface)
            limit: Maximum number of teams to return
            offset: Offset for pagination

        Returns:
            List[InternalTeam]: List of converted teams

        Raises:
            DataMappingError: If team conversion fails
            TransformationError: If data transformation fails
        """
        try:
            self.logger.debug(
                "Listing teams",
                project_id=str(self._project_id),
                limit=limit,
                offset=offset
            )

            teams, _ = await self._team_service.list_teams(self._project_id, limit=limit, offset=offset)

            # Convert teams with error handling
            converted_teams = []
            for team in teams:
                try:
                    converted_teams.append(await _convert_team(team, self._team_service))
                except DataMappingError as e:
                    self.logger.warning(
                        "Failed to convert team, skipping",
                        team_id=str(team.id) if hasattr(team, 'id') else None,
                        team_name=team.name if hasattr(team, 'name') else None,
                        error=str(e)
                    )
                    continue

            return converted_teams

        except Exception as e:
            self.logger.error(
                "Unexpected error listing teams",
                project_id=str(self._project_id),
                limit=limit,
                offset=offset,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise TransformationError(
                "Unexpected error listing teams",
                project_id=str(self._project_id),
                error=str(e)
            ) from e


class AgentServiceClient:
    """Adapter that executes agents via :class:`ToolsRuntimeService`."""

    def __init__(self, tools_runtime: ToolsRuntimeService) -> None:
        self._tools = tools_runtime
        self.logger = get_logger(__name__)

    async def __aenter__(self) -> "AgentServiceClient":  # pragma: no cover
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        return None

    async def execute_agent(
        self,
        agent: InternalAgent,
        request: AgentExecutionRequest,
        auth_headers: Dict[str, str],
        timeout: Optional[int] = 60,
        mcp_url: Optional[str] = None,
        rag_url: Optional[str] = None,
        rag_api_key: Optional[str] = None,
    ) -> AgentExecutionResponse:
        """Execute agent without streaming.

        Args:
            agent: Internal agent model
            request: Agent execution request
            auth_headers: Authentication headers (unused but part of interface)
            timeout: Execution timeout in seconds (unused but part of interface)
            mcp_url: MCP service URL
            rag_url: RAG service URL
            rag_api_key: RAG API key

        Returns:
            AgentExecutionResponse: Execution response

        Raises:
            AgentExecutionError: If agent execution fails
            TransformationError: If request/response transformation fails
        """
        try:
            self.logger.debug(
                "Building agent run request",
                agent_id=str(agent.id),
                agent_name=agent.name,
                session_id=request.session_id,
                user_id=request.user_id
            )

            run_request = self._build_agent_run_request(
                agent,
                request,
                stream=False,
                mcp_url=mcp_url,
                rag_url=rag_url,
                rag_api_key=rag_api_key,
            )
        except Exception as e:
            self.logger.error(
                "Failed to build agent run request",
                agent_id=str(agent.id),
                agent_name=agent.name,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise TransformationError(
                "Failed to build agent run request",
                agent_id=str(agent.id),
                agent_name=agent.name,
                error=str(e)
            ) from e

        try:
            self.logger.debug(
                "Executing agent",
                agent_id=str(agent.id),
                agent_name=agent.name,
                session_id=request.session_id,
                user_id=request.user_id
            )

            response = await self._tools.run_agent(run_request)

            self.logger.debug(
                "Agent execution completed",
                agent_id=str(agent.id),
                agent_name=agent.name,
                success=response.success,
                has_content=bool(response.content)
            )
        except AgentExecutionError:
            # Re-raise agent execution errors
            raise
        except Exception as e:
            self.logger.error(
                "Agent execution failed",
                agent_id=str(agent.id),
                agent_name=agent.name,
                session_id=request.session_id,
                user_id=request.user_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise AgentExecutionError(
                "Agent execution failed",
                agent_id=str(agent.id),
                agent_name=agent.name,
                session_id=request.session_id,
                user_id=request.user_id,
                error=str(e)
            ) from e

        # Transform response
        try:
            return AgentExecutionResponse(
                content=response.content,
                tools=[tool.model_dump() for tool in response.tools] if response.tools else None,
                success=response.success,
                error=response.error,
                metadata=response.metadata or {},
            )
        except Exception as e:
            self.logger.error(
                "Failed to transform agent response",
                agent_id=str(agent.id),
                agent_name=agent.name,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise TransformationError(
                "Failed to transform agent response",
                agent_id=str(agent.id),
                agent_name=agent.name,
                error=str(e)
            ) from e

    async def execute_agent_streaming(
        self,
        agent: InternalAgent,
        request: AgentExecutionRequest,
        auth_headers: Dict[str, str],
        workflow_events: WorkflowEventEmitter,
        execution_id: str,
        timeout: Optional[int] = 60,
        mcp_url: Optional[str] = None,
        rag_url: Optional[str] = None,
        rag_api_key: Optional[str] = None,
    ) -> AgentExecutionResponse:
        """Execute agent with streaming.

        Args:
            agent: Internal agent model
            request: Agent execution request
            auth_headers: Authentication headers (unused but part of interface)
            workflow_events: Event emitter for workflow events
            execution_id: Unique execution ID
            timeout: Execution timeout in seconds (unused but part of interface)
            mcp_url: MCP service URL
            rag_url: RAG service URL
            rag_api_key: RAG API key

        Returns:
            AgentExecutionResponse: Execution response with streaming metadata

        Raises:
            StreamingError: If streaming fails
            TransformationError: If request/response transformation fails
        """
        # Build run request
        try:
            self.logger.debug(
                "Building agent streaming request",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id,
                session_id=request.session_id,
                user_id=request.user_id
            )

            run_request = self._build_agent_run_request(
                agent,
                request,
                stream=True,
                mcp_url=mcp_url,
                rag_url=rag_url,
                rag_api_key=rag_api_key,
            )
        except Exception as e:
            self.logger.error(
                "Failed to build agent streaming request",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise TransformationError(
                "Failed to build agent streaming request",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id,
                error=str(e)
            ) from e

        content_chunks: List[str] = []
        success = True
        error: Optional[str] = None
        chunk_index = 0
        tool_calls = 0

        # Process stream
        try:
            self.logger.debug(
                "Starting agent streaming",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id
            )

            async for event in self._tools.stream_agent(run_request):
                if isinstance(event, ContentStreamEvent):
                    if event.content:
                        content_chunks.append(event.content)
                        workflow_events.emit_agent_content_chunk(
                            agent_id=str(agent.id),
                            agent_name=agent.name,
                            execution_id=execution_id,
                            content_chunk=event.content,
                            chunk_index=chunk_index,
                            is_final=False,
                            agent_role=agent.config.get("role") if isinstance(agent.config, dict) else None,
                        )
                        chunk_index += 1
                elif isinstance(event, ToolCallStreamEvent):
                    if event.status == "started":
                        tool_calls += 1
                        workflow_events.emit_agent_tool_call_started(
                            agent_id=str(agent.id),
                            agent_name=agent.name,
                            execution_id=execution_id,
                            tool_name=event.tool_name,
                            tool_call_id=event.tool_call_id,
                            tool_input=event.tool_input,
                        )
                    elif event.status == "completed":
                        workflow_events.emit_agent_tool_call_completed(
                            agent_id=str(agent.id),
                            agent_name=agent.name,
                            execution_id=execution_id,
                            tool_name=event.tool_name,
                            tool_call_id=event.tool_call_id,
                            tool_input=event.tool_input,
                            tool_output=event.tool_output,
                        )
                elif isinstance(event, ErrorStreamEvent):
                    success = False
                    error = event.error
                    self.logger.error(
                        "Streaming agent execution error",
                        agent_id=str(agent.id),
                        agent_name=agent.name,
                        execution_id=execution_id,
                        error=event.error,
                        error_type=event.error_type,
                    )
                elif isinstance(event, CompleteStreamEvent):
                    final_response = event.final_response
                    if final_response:
                        success = final_response.success
                        error = final_response.error
                        if final_response.content:
                            content_chunks.append(final_response.content)

            self.logger.debug(
                "Agent streaming completed",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id,
                chunks_count=len(content_chunks),
                tool_calls_count=tool_calls,
                success=success
            )

        except StreamingError:
            # Re-raise streaming errors
            raise
        except Exception as e:
            self.logger.error(
                "Agent streaming failed",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise StreamingError(
                "Agent streaming failed",
                agent_id=str(agent.id),
                agent_name=agent.name,
                execution_id=execution_id,
                error=str(e)
            ) from e

        # Emit completion event
        final_content = "".join(content_chunks)
        workflow_events.emit_agent_response_complete(
            agent_id=str(agent.id),
            agent_name=agent.name,
            execution_id=execution_id,
            final_content=final_content,
            success=success,
            total_chunks=len(content_chunks),
            tool_calls_count=tool_calls,
        )

        return AgentExecutionResponse(
            content=final_content,
            tools=None,
            success=success,
            error=error,
            metadata={
                "streaming": True,
                "chunks_count": len(content_chunks),
                "tool_calls_count": tool_calls,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    def _build_agent_run_request(
        self,
        agent: InternalAgent,
        request: AgentExecutionRequest,
        *,
        stream: bool,
        mcp_url: Optional[str],
        rag_url: Optional[str],
        rag_api_key: Optional[str],
    ) -> AgentRunRequest:
        agent_config = self._build_agent_config(agent, request, mcp_url=mcp_url, rag_url=rag_url, rag_api_key=rag_api_key)
        return AgentRunRequest(
            message=request.message,
            config=agent_config,
            session_id=request.session_id,
            user_id=request.user_id,
            stream=stream,
            stream_intermediate_steps=stream,
            enable_memory=request.enable_memory,
        )

    def _build_agent_config(
        self,
        agent: InternalAgent,
        request: AgentExecutionRequest,
        *,
        mcp_url: Optional[str],
        rag_url: Optional[str],
        rag_api_key: Optional[str],
    ) -> AgentConfig:
        base_config = agent.config.copy()
        override_config = request.config or {}
        combined_config = {**base_config, **override_config}

        system_prompt = combined_config.get("system_prompt") or agent.instruction or ""
        temperature = combined_config.get("temperature")
        max_tokens = combined_config.get("max_tokens")

        mcp_config = None
        if mcp_url and agent.tools:
            mcp_config = MCPConfig(
                url=mcp_url,
                tools=[tool.tool_name for tool in agent.tools if tool.enabled],
                auth_required=False,
            )

        rag_config = None
        if rag_url and agent.collections:
            rag_config = RagConfig(
                rag_url=rag_url,
                collections=[str(collection.id) for collection in agent.collections],
                api_key=rag_api_key,
            )

        workflow_config = None
        from app.config import settings
        workflow_service_url = getattr(settings, "workflow_service_url", None)
        if workflow_service_url and agent.workflows:
            workflow_config = WorkflowConfig(
                workflow_url=workflow_service_url,
                workflows=[str(binding.workflow_id) for binding in agent.workflows if binding.enabled],
                project_id=str(getattr(agent, "project_id", None)),
            )

        # Resolve provider credentials from agent (AgentServiceClient has no team context)
        provider_credentials = getattr(agent, "llm_provider_credentials", None)

        return AgentConfig(
            model_name=agent.model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            mcp_config=mcp_config,
            rag=rag_config,
            workflow=workflow_config,
            enable_memory=combined_config.get("enable_memory"),
            provider_credentials=provider_credentials,
        )
