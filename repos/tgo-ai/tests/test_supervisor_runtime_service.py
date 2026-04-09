from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
import uuid

import pytest

from app.exceptions import NotFoundError
from app.models.internal import Agent as InternalAgent
from app.runtime.supervisor.application.service import SupervisorRuntimeService
from app.runtime.supervisor.infrastructure.services import AIServiceClient
from app.schemas.agent_run import SupervisorRunRequest


def _build_internal_agent(*, agent_id: uuid.UUID | None = None, name: str = "Support Agent") -> InternalAgent:
    now = datetime.now(timezone.utc)
    return InternalAgent(
        id=agent_id or uuid.uuid4(),
        name=name,
        instruction="You are helpful.",
        model="openai:gpt-4o",
        config={"temperature": 0.2},
        tools=[],
        collections=[],
        workflows=[],
        is_default=False,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_prepare_context_uses_explicit_agent_id(monkeypatch) -> None:
    agent = _build_internal_agent()
    project_id = uuid.uuid4()
    service = SupervisorRuntimeService(session_factory=Mock(), tools_runtime_service=Mock())

    fake_agent_service = Mock()
    fake_agent_service.get_default_agent = AsyncMock()

    @asynccontextmanager
    async def fake_agent_service_context():
        yield fake_agent_service

    monkeypatch.setattr(service, "_agent_service_context", fake_agent_service_context, raising=False)
    monkeypatch.setattr(
        AIServiceClient,
        "get_agent",
        AsyncMock(return_value=agent),
        raising=False,
    )

    context, resolved_agent_id = await service._prepare_context(
        SupervisorRunRequest(message="hello", agent_id=str(agent.id)),
        project_id,
        {"X-Request-ID": "req-explicit"},
    )

    assert context.agent.id == agent.id
    assert resolved_agent_id == str(agent.id)
    fake_agent_service.get_default_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_context_uses_project_default_agent_when_agent_id_missing(monkeypatch) -> None:
    agent = _build_internal_agent()
    project_id = uuid.uuid4()
    service = SupervisorRuntimeService(session_factory=Mock(), tools_runtime_service=Mock())

    fake_agent_service = Mock()
    fake_agent_service.get_default_agent = AsyncMock(return_value=Mock(id=agent.id))

    @asynccontextmanager
    async def fake_agent_service_context():
        yield fake_agent_service

    monkeypatch.setattr(service, "_agent_service_context", fake_agent_service_context, raising=False)
    monkeypatch.setattr(
        AIServiceClient,
        "get_agent",
        AsyncMock(return_value=agent),
        raising=False,
    )

    context, resolved_agent_id = await service._prepare_context(
        SupervisorRunRequest(message="hello"),
        project_id,
        {"X-Request-ID": "req-default"},
    )

    assert context.agent.id == agent.id
    assert resolved_agent_id == str(agent.id)
    fake_agent_service.get_default_agent.assert_awaited_once_with(project_id)


@pytest.mark.asyncio
async def test_run_returns_failure_when_project_default_agent_missing(monkeypatch) -> None:
    project_id = uuid.uuid4()
    service = SupervisorRuntimeService(session_factory=Mock(), tools_runtime_service=Mock())
    service._agent_builder = Mock()
    service._agent_builder.build_agent = AsyncMock()
    service._agent_runner = Mock()
    service._agent_runner.run = AsyncMock()

    fake_agent_service = Mock()
    fake_agent_service.get_default_agent = AsyncMock(side_effect=NotFoundError("Agent"))

    @asynccontextmanager
    async def fake_agent_service_context():
        yield fake_agent_service

    monkeypatch.setattr(service, "_agent_service_context", fake_agent_service_context, raising=False)

    response = await service.run(
        SupervisorRunRequest(message="hello"),
        project_id,
        extra_headers={"X-Request-ID": "req-missing-default"},
    )

    assert response.success is False
    assert response.result is None
    assert response.metadata is None
    assert response.content == ""
    assert response.error == "Default agent not configured for project"
    service._agent_builder.build_agent.assert_not_awaited()
    service._agent_runner.run.assert_not_awaited()
