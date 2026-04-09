from app.runtime.tools.custom.base import ToolContext


def test_tool_context_build_metadata_uses_agent_scope() -> None:
    context = ToolContext(
        agent_id="agent-1",
        session_id="sess-1",
        user_id="user-1",
        project_id="project-1",
        request_id="req-1",
    )

    metadata = context.build_metadata({"source": "ai"})

    assert metadata == {
        "source": "ai",
        "agent_id": "agent-1",
        "user_id": "user-1",
        "project_id": "project-1",
        "session_id": "sess-1",
        "request_id": "req-1",
    }
    assert "team_id" not in metadata
