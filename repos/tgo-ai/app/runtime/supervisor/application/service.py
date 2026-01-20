"""Supervisor runtime service implemented via agno teams."""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional, Tuple

from agno.team import Team
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.logging import get_logger

from app.models.internal import Team as InternalTeam
from app.models.streaming import (
    EventType,
    StreamingEvent,
    TeamRunLifecycleData,
    TeamRunCompletedData,
    TeamRunErrorData,
)
from app.runtime.supervisor.infrastructure.services import AIServiceClient
from app.runtime.supervisor.models.coordination import CoordinationContext, CoordinationRequest
from app.runtime.supervisor.streaming.workflow_events import (
    WorkflowEventEmitter,
    create_workflow_events,
)
from app.runtime.supervisor.teams import AgnoTeamBuilder, AgnoTeamRunner, TeamRunResult
from app.runtime.tools.executor.service import ToolsRuntimeService
from app.schemas.agent_run import SupervisorRunRequest, SupervisorRunResponse
from app.services.team_service import TeamService
from app.streaming.event_emitter import cleanup_event_emitter, get_event_emitter
from app.streaming.sse_handler import create_sse_response


@dataclass
class RunRegistryEntry:
    """Typed entry for a running team execution."""
    team: Team
    project_id: str
    request_id: str
    correlation_id: str
    team_id: str
    team_name: str
    started_at: float


@dataclass
class TeamHolder:
    """Typed container to hold the current Team instance for this stream."""
    team: Optional[Team] = None



class SupervisorRuntimeService:
    """High-level façade coordinating advanced multi-agent workflows via agno teams."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tools_runtime_service: ToolsRuntimeService,
    ) -> None:
        self._session_factory = session_factory
        self._tools_runtime = tools_runtime_service
        self._logger = get_logger("runtime.supervisor.service")
        self._team_builder = AgnoTeamBuilder(
            getattr(self._tools_runtime, "_settings", settings.tools_runtime),
            session_factory=self._session_factory,
        )
        self._team_runner = AgnoTeamRunner()

        # Run registry (run_id -> RunRegistryEntry) with async lock for safety
        self._runs: Dict[str, RunRegistryEntry] = {}
        self._runs_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    async def run(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> SupervisorRunResponse:
        """Execute a coordination request and return aggregated response."""
        headers = self._build_auth_headers(project_id, extra_headers)
        context, _ = await self._prepare_context(payload, project_id, headers)

        built_team = await self._team_builder.build_team(context)

        self._logger.debug(
            "Starting supervisor run",
            team_id=context.team.id,
            request_id=headers.get("X-Request-ID"),
        )

        return await self._team_runner.run(built_team, context)

    async def stream(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        extra_headers: Optional[Dict[str, str]] = None,
        http_request=None,
    ):
        """Execute coordination request with Server-Sent Events streaming."""
        if http_request is None:
            raise RuntimeError("HTTP request object required for streaming")

        auth_headers = self._build_auth_headers(project_id, extra_headers)

        request_id = auth_headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = str(uuid.uuid4())

        event_emitter = get_event_emitter(request_id, correlation_id)
        event_emitter.enable_streaming()
        workflow_events = create_workflow_events(event_emitter)

        # Typed holder for the Team instance used by this stream
        team_holder: TeamHolder = TeamHolder()

        # Event listeners to register/unregister runs in the registry
        def _on_team_started(evt: StreamingEvent) -> None:
            try:
                if evt.event_type != EventType.TEAM_RUN_STARTED:
                    return
                data = evt.data
                if not isinstance(data, TeamRunLifecycleData):
                    return
                if team_holder.team is None:
                    self._logger.warning(
                        "TEAM_RUN_STARTED received before team available; skipping registry registration",
                        request_id=request_id,
                        correlation_id=correlation_id,
                    )
                    return
                entry = RunRegistryEntry(
                    team=team_holder.team,
                    project_id=str(project_id),
                    request_id=request_id,
                    correlation_id=correlation_id,
                    team_id=data.team_id,
                    team_name=data.team_name,
                    started_at=time.time(),
                )
                # Register synchronously to avoid race with client-side cancel immediately after STARTED
                self._runs[data.run_id] = entry
                self._logger.debug(
                    "Registered running team execution (sync)",
                    run_id=data.run_id,
                    team_id=entry.team_id,
                    request_id=entry.request_id,
                )
            except Exception as e:  # pragma: no cover - defensive
                self._logger.exception("Failed to register run in registry", error=str(e))

        def _on_team_completed(evt: StreamingEvent) -> None:
            try:
                if evt.event_type != EventType.TEAM_RUN_COMPLETED:
                    return
                data = evt.data
                if not isinstance(data, TeamRunCompletedData):
                    return
                asyncio.create_task(self._unregister_run(data.run_id))
            except Exception as e:  # pragma: no cover - defensive
                self._logger.exception("Failed to unregister run on completion", error=str(e))

        def _on_team_failed(evt: StreamingEvent) -> None:
            try:
                if evt.event_type != EventType.TEAM_RUN_FAILED:
                    return
                data = evt.data
                if not isinstance(data, TeamRunErrorData):
                    return
                if data.run_id:
                    asyncio.create_task(self._unregister_run(data.run_id))
            except Exception as e:  # pragma: no cover - defensive
                self._logger.exception("Failed to unregister run on failure", error=str(e))

        # Register listeners
        event_emitter.on(EventType.TEAM_RUN_STARTED, _on_team_started)
        event_emitter.on(EventType.TEAM_RUN_COMPLETED, _on_team_completed)
        event_emitter.on(EventType.TEAM_RUN_FAILED, _on_team_failed)

        async def coordination_task() -> None:
            try:
                context, _ = await self._prepare_context(payload, project_id, auth_headers)
                built_team = await self._team_builder.build_team(context)

                # Expose team to event listeners before starting the stream
                team_holder.team = built_team.team

                coordination_request = CoordinationRequest(
                    context=context,
                    auth_headers=auth_headers,
                    request_id=request_id,
                )
                workflow_events.emit_workflow_started(coordination_request)

                print("--------------------------------")
                print("Starting team stream")
                print("--------------------------------")
                team_result = await self._team_runner.stream(built_team, context, workflow_events)

                print("--------------------------------")
                print("Team stream completed")
                print("--------------------------------")

                workflow_events.emit_workflow_completed(
                    team_result.total_time,
                    len(team_result.agent_results),
                )

                # Give SSE handler time to process the completed event before cleanup
                await asyncio.sleep(0.1)
            except Exception as exc:  # pragma: no cover - streaming error path
                self._logger.exception(
                    "Coordination workflow failed during streaming",
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
                workflow_events.emit_workflow_failed(str(exc), "coordination")
            finally:
                # Clean up listeners and emitter
                try:
                    event_emitter.off(EventType.TEAM_RUN_STARTED, _on_team_started)
                    event_emitter.off(EventType.TEAM_RUN_COMPLETED, _on_team_completed)
                    event_emitter.off(EventType.TEAM_RUN_FAILED, _on_team_failed)
                except Exception:
                    pass
                cleanup_event_emitter(request_id, correlation_id)

        asyncio.create_task(coordination_task())
        return create_sse_response(event_emitter, http_request)


    # ------------------------------------------------------------------
    # Cancellation API and run registry helpers
    async def cancel(self, run_id: str, project_id: uuid.UUID, reason: Optional[str] = None) -> bool:
        """Cancel a running team execution by run_id.

        Returns True if a cancellation signal was sent, False if not found or not permitted.
        """
        # Validate ownership and fetch entry under lock
        async with self._runs_lock:
            entry = self._runs.get(run_id)
        if entry is None:
            self._logger.info("Cancel requested for unknown run_id", run_id=run_id)
            return False
        if str(project_id) != entry.project_id:
            self._logger.warning(
                "Cancel forbidden: project mismatch",
                run_id=run_id,
                expected_project_id=entry.project_id,
                got_project_id=str(project_id),
            )
            return False

        try:
            entry.team.cancel_run(run_id)
            # Proactively emit a failure event with cancelled reason for fast UI feedback
            try:
                emitter = get_event_emitter(entry.request_id, entry.correlation_id)
                workflow_events = create_workflow_events(emitter)
                workflow_events.emit_team_run_failed(
                    team_id=entry.team_id,
                    team_name=entry.team_name,
                    error=reason or "cancelled_by_user",
                    run_id=run_id,
                )
            except Exception:  # pragma: no cover - best-effort
                pass
            return True
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.exception("Cancel request failed", run_id=run_id, error=str(exc))
            return False

    async def _register_run(self, run_id: str, entry: RunRegistryEntry) -> None:
        async with self._runs_lock:
            self._runs[run_id] = entry
            self._logger.debug(
                "Registered running team execution",
                run_id=run_id,
                team_id=entry.team_id,
                request_id=entry.request_id,
            )

    async def _unregister_run(self, run_id: str) -> None:
        async with self._runs_lock:
            if run_id in self._runs:
                entry = self._runs.pop(run_id)
                self._logger.debug(
                    "Unregistered team execution",
                    run_id=run_id,
                    team_id=entry.team_id,
                    request_id=entry.request_id,
                )

    # ------------------------------------------------------------------
    # Helpers
    async def _prepare_context(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        headers: Dict[str, str],
    ) -> Tuple[CoordinationContext, str]:
        async with self._team_service_context() as team_service:
            effective_payload, team_id = await self._ensure_team_id(payload, project_id, team_service)
            async with AIServiceClient(team_service, project_id) as ai_client:
                team = await ai_client.get_team_with_agents(team_id, headers)

        # Filter to specific agents if agent_ids or agent_id is specified
        target_agent_ids = payload.agent_ids or ([payload.agent_id] if payload.agent_id else None)
        if target_agent_ids:
            filtered_agents = [a for a in team.agents if str(a.id) in target_agent_ids]
            if not filtered_agents:
                raise ValueError(f"None of the specified agents {target_agent_ids} found in team {team_id}")
            team = team.model_copy(update={"agents": filtered_agents})

        context = self._build_coordination_context(
            effective_payload,
            team,
            api_key=None,
            project_id=str(project_id),
        )
        return context, team_id

    @asynccontextmanager
    async def _team_service_context(self) -> AsyncIterator[TeamService]:
        session: AsyncSession = self._session_factory()
        try:
            yield TeamService(session)
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        else:
            if session.in_transaction():
                await session.rollback()
        finally:
            await session.close()

    async def _ensure_team_id(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        team_service: TeamService,
    ) -> tuple[SupervisorRunRequest, str]:
        if payload.team_id:
            return payload, str(payload.team_id)

        default_team = await team_service.get_default_team(project_id)
        updated = payload.model_copy(update={"team_id": str(default_team.id)})
        return updated, str(default_team.id)

    @staticmethod
    def _build_auth_headers(project_id: uuid.UUID, extra_headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        headers = dict(extra_headers or {})
        headers.setdefault("X-Project-ID", str(project_id))
        headers.setdefault("X-Request-ID", str(uuid.uuid4()))
        return headers

    @staticmethod
    def _get_execution_strategy(payload: SupervisorRunRequest) -> str:
        if payload.config and payload.config.execution_strategy:
            return payload.config.execution_strategy
        return "auto"

    def _build_coordination_context(
        self,
        payload: SupervisorRunRequest,
        team: InternalTeam,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> CoordinationContext:
        strategy = self._get_execution_strategy(payload)
        max_agents = (
            payload.config.max_agents
            if payload.config
            else settings.supervisor_runtime.coordination.max_concurrent_agents
        )
        timeout = (
            payload.config.timeout
            if payload.config
            else settings.supervisor_runtime.coordination.default_timeout
        )
        require_consensus = (
            payload.config.require_consensus
            if payload.config
            else settings.supervisor_runtime.coordination.enable_consensus
        )

        return CoordinationContext(
            team=team,
            project_id=project_id,
            message=payload.message,
            session_id=payload.session_id,
            user_id=payload.user_id,
            execution_strategy="optimal" if strategy == "auto" else strategy,
            max_agents=max_agents,
            timeout=timeout,
            require_consensus=require_consensus,
            mcp_url=payload.mcp_url,
            rag_url=payload.rag_url,
            rag_api_key=api_key,
            system_message=payload.system_message,
            expected_output=payload.expected_output,
            enable_memory=payload.enable_memory,
        )
