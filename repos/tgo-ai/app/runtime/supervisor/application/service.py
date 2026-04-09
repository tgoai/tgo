"""Supervisor runtime service implemented via direct single-agent execution."""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.logging import get_logger
from app.exceptions import NotFoundError
from app.models.internal import AgentExecutionContext
from app.runtime.supervisor.agents.builder import AgnoAgentBuilder
from app.runtime.supervisor.agents.runner import AgnoAgentRunner
from app.runtime.supervisor.infrastructure.services import AIServiceClient
from app.runtime.supervisor.streaming.workflow_events import create_workflow_events
from app.runtime.tools.executor.service import ToolsRuntimeService
from app.schemas.agent_run import SupervisorRunRequest, SupervisorRunResponse
from app.services.agent_service import AgentService
from app.streaming.event_emitter import cleanup_event_emitter, get_event_emitter
from app.streaming.sse_handler import create_sse_response


@dataclass
class RunRegistryEntry:
    """Typed entry for a running single-agent execution."""

    runnable: object
    project_id: str
    request_id: str
    correlation_id: str
    execution_id: str
    agent_id: str
    agent_name: str
    started_at: float


class SupervisorRuntimeService:
    """High-level facade coordinating direct single-agent runtime execution."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tools_runtime_service: ToolsRuntimeService,
    ) -> None:
        self._session_factory = session_factory
        self._tools_runtime = tools_runtime_service
        self._logger = get_logger("runtime.supervisor.service")
        runtime_settings = getattr(self._tools_runtime, "_settings", None)
        self._agent_builder = AgnoAgentBuilder(runtime_settings)
        self._agent_runner = AgnoAgentRunner()
        self._runs: Dict[str, RunRegistryEntry] = {}
        self._runs_lock = asyncio.Lock()

    async def run(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> SupervisorRunResponse:
        """Execute a single-agent request and return the unified response."""
        headers = self._build_auth_headers(project_id, extra_headers)

        try:
            context, _ = await self._prepare_context(payload, project_id, headers)
            built_agent = await self._agent_builder.build_agent(context)
            self._logger.debug(
                "Starting supervisor run",
                agent_id=str(context.agent.id),
                request_id=context.request_id,
            )
            return await self._agent_runner.run(built_agent, context)
        except NotFoundError as exc:
            return self._build_failure_response(str(exc))
        except ValueError as exc:
            return self._build_failure_response(str(exc))
        except Exception as exc:  # pragma: no cover - defensive runtime path
            self._logger.exception(
                "Supervisor run failed",
                project_id=str(project_id),
                request_id=headers.get("X-Request-ID"),
            )
            return self._build_failure_response(str(exc) or "Agent run failed")

    async def stream(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        extra_headers: Optional[Dict[str, str]] = None,
        http_request=None,
    ):
        """Execute a single-agent request with Server-Sent Events streaming."""
        if http_request is None:
            raise RuntimeError("HTTP request object required for streaming")

        auth_headers = self._build_auth_headers(project_id, extra_headers)
        request_id = auth_headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = str(uuid.uuid4())

        event_emitter = get_event_emitter(request_id, correlation_id)
        event_emitter.enable_streaming()
        workflow_events = create_workflow_events(event_emitter)

        async def coordination_task() -> None:
            execution_id: Optional[str] = None
            try:
                context, _ = await self._prepare_context(payload, project_id, auth_headers)
                built_agent = await self._agent_builder.build_agent(context)
                execution_id = str(uuid.uuid4())

                await self._register_run(
                    execution_id,
                    RunRegistryEntry(
                        runnable=built_agent.agent,
                        project_id=str(project_id),
                        request_id=request_id,
                        correlation_id=correlation_id,
                        execution_id=execution_id,
                        agent_id=str(context.agent.id),
                        agent_name=context.agent.name,
                        started_at=time.time(),
                    ),
                )

                workflow_events.emit_agent_execution_started(
                    agent_id=str(context.agent.id),
                    agent_name=context.agent.name,
                    execution_id=execution_id,
                    question=context.message,
                )
                agent_result = await self._agent_runner.stream(
                    built_agent,
                    context,
                    workflow_events,
                    execution_id,
                )
                workflow_events.emit_workflow_completed(agent_result.total_time, 1)
            except ValueError as exc:
                workflow_events.emit_workflow_failed(str(exc), "agent_resolution")
            except NotFoundError as exc:
                workflow_events.emit_workflow_failed(str(exc), "agent_resolution")
            except Exception as exc:  # pragma: no cover - streaming error path
                self._logger.exception(
                    "Agent workflow failed during streaming",
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
                workflow_events.emit_workflow_failed(str(exc), "agent_execution")
            finally:
                if execution_id is not None:
                    await self._unregister_run(execution_id)
                cleanup_event_emitter(request_id, correlation_id)

        asyncio.create_task(coordination_task())
        return create_sse_response(event_emitter, http_request)

    async def cancel(self, run_id: str, project_id: uuid.UUID, reason: Optional[str] = None) -> bool:
        """Cancel a running single-agent execution by run_id."""
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

        cancel_run = getattr(entry.runnable, "cancel_run", None)
        if not callable(cancel_run):
            self._logger.warning(
                "Cancel unsupported for running agent",
                run_id=run_id,
                agent_id=entry.agent_id,
            )
            return False

        try:
            cancel_run(run_id)
            return True
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.exception("Cancel request failed", run_id=run_id, error=str(exc))
            return False

    async def _register_run(self, run_id: str, entry: RunRegistryEntry) -> None:
        async with self._runs_lock:
            self._runs[run_id] = entry
            self._logger.debug(
                "Registered running agent execution",
                run_id=run_id,
                agent_id=entry.agent_id,
                request_id=entry.request_id,
            )

    async def _unregister_run(self, run_id: str) -> None:
        async with self._runs_lock:
            entry = self._runs.pop(run_id, None)
        if entry is not None:
            self._logger.debug(
                "Unregistered agent execution",
                run_id=run_id,
                agent_id=entry.agent_id,
                request_id=entry.request_id,
            )

    async def _prepare_context(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        headers: Dict[str, str],
    ) -> Tuple[AgentExecutionContext, str]:
        async with self._agent_service_context() as agent_service:
            agent_id = await self._resolve_agent_id(payload, project_id, agent_service)
            async with AIServiceClient(agent_service, project_id) as ai_client:
                agent = await ai_client.get_agent(agent_id, headers)

        context = AgentExecutionContext(
            agent=agent,
            project_id=str(project_id),
            message=payload.message,
            system_message=payload.system_message,
            expected_output=payload.expected_output,
            session_id=payload.session_id,
            user_id=payload.user_id,
            request_id=headers["X-Request-ID"],
            timeout=payload.timeout,
            mcp_url=payload.mcp_url,
            rag_url=payload.rag_url,
            enable_memory=payload.enable_memory,
        )
        return context, agent_id

    @asynccontextmanager
    async def _agent_service_context(self) -> AsyncIterator[AgentService]:
        session: AsyncSession = self._session_factory()
        try:
            yield AgentService(session)
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        else:
            if session.in_transaction():
                await session.rollback()
        finally:
            await session.close()

    async def _resolve_agent_id(
        self,
        payload: SupervisorRunRequest,
        project_id: uuid.UUID,
        agent_service: AgentService,
    ) -> str:
        if payload.agent_id:
            return str(payload.agent_id)

        try:
            default_agent = await agent_service.get_default_agent(project_id)
        except NotFoundError as exc:
            raise ValueError("Default agent not configured for project") from exc
        return str(default_agent.id)

    @staticmethod
    def _build_auth_headers(project_id: uuid.UUID, extra_headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        headers = dict(extra_headers or {})
        headers.setdefault("X-Project-ID", str(project_id))
        headers.setdefault("X-Request-ID", str(uuid.uuid4()))
        return headers

    @staticmethod
    def _build_failure_response(message: str) -> SupervisorRunResponse:
        return SupervisorRunResponse(
            success=False,
            message=message,
            result=None,
            content="",
            metadata=None,
            error=message,
        )
