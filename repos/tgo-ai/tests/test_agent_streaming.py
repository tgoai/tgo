from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock
import json
import uuid

from app.models.internal import Agent as InternalAgent
from app.models.internal import AgentExecutionContext
from app.models.streaming import EventSeverity, EventType
from app.runtime.supervisor.streaming.workflow_events import WorkflowEventEmitter


def _build_context() -> AgentExecutionContext:
    now = datetime.now(timezone.utc)
    agent = InternalAgent(
        id=uuid.uuid4(),
        name="Support Agent",
        instruction="Base instruction",
        model="openai:gpt-4o",
        config={},
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
        system_message=None,
        expected_output=None,
        session_id="sess-1",
        user_id="user-1",
        request_id="req-1",
        timeout=30,
        mcp_url=None,
        rag_url=None,
        enable_memory=False,
    )


def test_workflow_started_event_uses_agent_metadata() -> None:
    sink = Mock()
    emitter = WorkflowEventEmitter(sink)
    context = _build_context()

    emitter.emit_workflow_started(context.request_id, context)

    sink.emit.assert_called_once()
    event_type, data, severity, metadata = sink.emit.call_args.args
    assert event_type == EventType.WORKFLOW_STARTED
    assert severity == EventSeverity.INFO
    assert data.request_id == context.request_id
    assert data.agent_id == str(context.agent.id)
    assert data.agent_name == context.agent.name
    assert data.session_id == context.session_id
    assert metadata["phase"] == "initialization"
    assert "team_id" not in metadata


def test_streaming_openapi_examples_are_agent_centric(client) -> None:
    schema = client.get("/openapi.json").json()
    examples = schema["paths"]["/api/v1/agents/run"]["post"]["responses"]["200"]["content"]["text/event-stream"]["examples"]
    serialized = json.dumps(examples)

    assert "team_run_" not in serialized
    assert "team_member_" not in serialized
    assert "team_id" not in serialized
    assert "agent_execution_started" in serialized
    assert "agent_content_chunk" in serialized
    assert "agent_tool_call_started" in serialized
    assert "agent_response_complete" in serialized
