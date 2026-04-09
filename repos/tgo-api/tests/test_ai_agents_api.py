"""API contract tests for agent-only AI endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.api.v1.endpoints.ai_agents import ai_client
from app.models.project import Project


def test_list_agents_openapi_has_no_team_id_parameter(client) -> None:
    """The public list-agents contract should no longer expose team filters."""

    schema = client.get("/v1/openapi.json").json()
    params = schema["paths"]["/v1/ai/agents"]["get"].get("parameters", [])

    assert all(param["name"] != "team_id" for param in params)


def test_list_agents_does_not_forward_team_id(
    client,
    authenticated_project: Project,
    monkeypatch,
) -> None:
    """Agent listing should only forward agent-centric filters downstream."""

    list_agents_mock = AsyncMock(
        return_value={
            "data": [],
            "pagination": {
                "total": 0,
                "limit": 20,
                "offset": 0,
                "has_next": False,
                "has_prev": False,
            },
        }
    )
    monkeypatch.setattr(ai_client, "list_agents", list_agents_mock)

    response = client.get("/v1/ai/agents", params={"model": "gpt-4o"})

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert "team_id" not in list_agents_mock.await_args.kwargs
    assert list_agents_mock.await_args.kwargs["project_id"] == str(authenticated_project.id)


def test_create_agent_rejects_team_id_payload(
    client,
    monkeypatch,
) -> None:
    """Legacy team IDs should be rejected instead of silently ignored."""

    create_agent_mock = AsyncMock()
    monkeypatch.setattr(ai_client, "create_agent", create_agent_mock)

    response = client.post(
        "/v1/ai/agents",
        json={
            "name": "Support Agent",
            "model": "gpt-4o",
            "team_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    )

    assert response.status_code == 422
    create_agent_mock.assert_not_awaited()
