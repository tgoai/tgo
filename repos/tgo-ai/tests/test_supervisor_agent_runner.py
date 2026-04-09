from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import uuid

import pytest

from app.models.internal import Agent as InternalAgent
from app.models.internal import AgentExecutionContext
from app.runtime.supervisor.agents.builder import AgnoAgentBuilder
from app.runtime.supervisor.agents.runner import AgnoAgentRunner
from app.runtime.tools.builder.agent_builder import AgentBuilder
from app.runtime.tools.config import ToolsRuntimeSettings


def _build_context() -> AgentExecutionContext:
    now = datetime.now(timezone.utc)
    agent_id = uuid.uuid4()
    agent = InternalAgent(
        id=agent_id,
        name="Support Agent",
        instruction="Base instruction",
        model="openai:gpt-4o",
        config={"temperature": 0.1, "expected_output": "from-agent"},
        tools=[],
        collections=[],
        workflows=[],
        is_default=True,
        created_at=now,
        updated_at=now,
    )
    return AgentExecutionContext(
        agent=agent,
        project_id=str(uuid.uuid4()),
        message="hello",
        system_message="Append this",
        expected_output="Respond in JSON",
        session_id="sess-1",
        user_id="user-1",
        request_id="req-1",
        timeout=30,
        mcp_url="http://mcp",
        rag_url="http://rag",
        enable_memory=True,
    )


@pytest.mark.asyncio
async def test_builder_passes_single_agent_overrides_to_agent_builder(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_build_agent(self, request, internal_agent=None):
        captured["request"] = request
        captured["internal_agent"] = internal_agent
        return SimpleNamespace(id=str(internal_agent.id), name=internal_agent.name)

    monkeypatch.setattr(AgentBuilder, "build_agent", fake_build_agent)

    builder = AgnoAgentBuilder(ToolsRuntimeSettings())
    context = _build_context()

    await builder.build_agent(context)

    request = captured["request"]
    assert request.project_id == context.project_id
    assert request.agent_id == str(context.agent.id)
    assert request.request_id == context.request_id
    assert request.config.system_prompt == context.agent.instruction
    assert request.config.system_message == context.system_message
    assert request.config.expected_output == context.expected_output


@pytest.mark.asyncio
async def test_runner_returns_single_agent_response_shape() -> None:
    context = _build_context()
    built_agent = SimpleNamespace(
        agent=SimpleNamespace(
            arun=AsyncMock(return_value=SimpleNamespace(content="ok", tools=[]))
        )
    )
    runner = AgnoAgentRunner()

    response = await runner.run(built_agent, context)

    assert response.success is True
    assert response.result is not None
    assert response.result.agent_id == context.agent.id
    assert response.result.agent_name == context.agent.name
    assert response.result.content == "ok"
    assert response.content == "ok"
    assert response.metadata is not None
    assert response.metadata.agent_id == context.agent.id
    assert response.metadata.agent_name == context.agent.name
