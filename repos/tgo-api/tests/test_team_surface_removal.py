"""Tests covering removed team-oriented tgo-api surfaces."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints import store as store_endpoints
from app.core.dev_data import DEFAULT_PERMISSIONS, DEFAULT_USER_GLOBAL_PERMISSIONS
from app.models.project import Project
import app.schemas as app_schemas
from app.schemas.store import StoreInstallAgentRequest


class _FakeStoreDB:
    """Minimal DB double for store installation tests."""

    def __init__(self, credential: object, project: Project) -> None:
        self._credential = credential
        self._project = project

    def scalar(self, _statement: object) -> object:
        return self._credential

    def get(self, _model: type[Project], _project_id: object) -> Project:
        return self._project


def test_ai_teams_routes_absent(client) -> None:
    """OpenAPI should not publish the removed AI team routes."""

    schema = client.get("/v1/openapi.json").json()

    assert all(not path.startswith("/v1/ai/teams") for path in schema["paths"])


def test_team_schema_exports_absent() -> None:
    """tgo-api should not keep legacy team schemas in its public exports."""

    removed_exports = (
        "TeamCreateRequest",
        "TeamUpdateRequest",
        "TeamResponse",
        "TeamListResponse",
        "TeamWithDetailsResponse",
    )

    assert all(not hasattr(app_schemas, name) for name in removed_exports)


def test_team_permissions_absent_from_seed_data() -> None:
    """Default permissions should no longer advertise AI team resources."""

    assert all(resource != "ai_teams" for resource, _action, _desc in DEFAULT_PERMISSIONS)
    assert all(resource != "ai_teams" for resource, _action in DEFAULT_USER_GLOBAL_PERMISSIONS)


@pytest.mark.asyncio
async def test_install_agent_from_store_payload_has_no_team_id(monkeypatch) -> None:
    """Store-installed agents should be created without any team selector."""

    project_id = uuid4()
    fake_db = _FakeStoreDB(
        credential=SimpleNamespace(api_key_encrypted="encrypted"),
        project=Project(
            id=project_id,
            name="Test Project",
            api_key="ak_test_downstream_api_key",
        ),
    )
    agent_template = SimpleNamespace(
        id="store-agent-1",
        name="Store Agent",
        title_zh=None,
        instruction="Help the customer",
        instruction_zh=None,
        model=None,
        default_config={"temperature": 0.2},
        recommended_tools=[],
        model_id=None,
    )
    create_agent_mock = AsyncMock(return_value={"id": "agent-1"})
    install_agent_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(store_endpoints, "decrypt_str", lambda _value: "store-api-key")
    monkeypatch.setattr(
        store_endpoints.store_client,
        "get_agent",
        AsyncMock(return_value=agent_template),
    )
    monkeypatch.setattr(store_endpoints.ai_client, "create_agent", create_agent_mock)
    monkeypatch.setattr(
        store_endpoints.store_client,
        "install_agent",
        install_agent_mock,
    )

    result = await store_endpoints.install_agent_from_store(
        StoreInstallAgentRequest(resource_id="store-agent-1"),
        db=fake_db,
        current_user=SimpleNamespace(project_id=project_id),
    )

    assert result == {"id": "agent-1"}
    assert "team_id" not in create_agent_mock.await_args.kwargs["agent_data"]
