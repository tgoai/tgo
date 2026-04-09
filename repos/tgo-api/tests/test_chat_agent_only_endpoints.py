"""Tests for agent-only public chat flows."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints import chat as chat_endpoints
from app.api.v1.endpoints import platforms as platform_endpoints
from app.schemas.chat import ChatCompletionRequest, StaffAgentChatRequest
from app.schemas.platform_schema import PlatformCreate
from app.models.platform import PlatformType


class _NoOpDB:
    """Small DB double for chat endpoint unit tests."""

    def add(self, _obj: object) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _PlatformDB:
    """DB double that records newly created platforms."""

    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        return None

    def refresh(self, _obj: object, attribute_names=None) -> None:
        return None


@pytest.mark.asyncio
async def test_chat_completion_prefers_platform_agent_id(monkeypatch) -> None:
    """Visitor chat should forward the platform-level agent override."""

    platform_agent_id = uuid4()
    project_id = uuid4()
    assigned_staff_id = uuid4()
    visitor = SimpleNamespace(
        id=uuid4(),
        is_unassigned=True,
        ai_disabled=None,
        is_last_message_from_ai=False,
        is_last_message_from_visitor=True,
        last_client_msg_no=None,
    )
    platform = SimpleNamespace(agent_id=platform_agent_id, ai_mode="auto")
    project = SimpleNamespace(id=project_id, api_key="ak_project")
    handle_ai_mock = AsyncMock(return_value={"success": True, "content": "ok"})

    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "validate_platform_and_project",
        lambda _api_key, _db: (platform, project),
    )
    monkeypatch.setattr(
        chat_endpoints,
        "get_or_create_visitor",
        AsyncMock(return_value=(visitor, False)),
    )
    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "send_user_message_to_wukongim",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        chat_endpoints,
        "transfer_to_staff",
        AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                assigned_staff_id=assigned_staff_id,
                message="assigned",
                queue_position=None,
            )
        ),
    )
    monkeypatch.setattr(
        chat_endpoints.wukongim_client,
        "send_visitor_profile_updated",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "is_ai_disabled",
        lambda _platform, _visitor: False,
    )
    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "handle_ai_response_non_stream",
        handle_ai_mock,
    )

    result = await chat_endpoints.chat_completion(
        ChatCompletionRequest(
            api_key="pk_test",
            message="hello",
            from_uid="visitor-open-id",
            stream=False,
        ),
        db=_NoOpDB(),
    )

    assert result["message"] == "ok"
    assert handle_ai_mock.await_args.kwargs["agent_id"] == str(platform_agent_id)


@pytest.mark.asyncio
async def test_chat_completion_omits_agent_id_without_platform_override(
    monkeypatch,
) -> None:
    """Visitor chat should defer to the project default agent when no override exists."""

    project_id = uuid4()
    assigned_staff_id = uuid4()
    visitor = SimpleNamespace(
        id=uuid4(),
        is_unassigned=True,
        ai_disabled=None,
        is_last_message_from_ai=False,
        is_last_message_from_visitor=True,
        last_client_msg_no=None,
    )
    platform = SimpleNamespace(agent_id=None, ai_mode="auto")
    project = SimpleNamespace(id=project_id, api_key="ak_project")
    handle_ai_mock = AsyncMock(return_value={"success": True, "content": "ok"})

    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "validate_platform_and_project",
        lambda _api_key, _db: (platform, project),
    )
    monkeypatch.setattr(
        chat_endpoints,
        "get_or_create_visitor",
        AsyncMock(return_value=(visitor, False)),
    )
    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "send_user_message_to_wukongim",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        chat_endpoints,
        "transfer_to_staff",
        AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                assigned_staff_id=assigned_staff_id,
                message="assigned",
                queue_position=None,
            )
        ),
    )
    monkeypatch.setattr(
        chat_endpoints.wukongim_client,
        "send_visitor_profile_updated",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "is_ai_disabled",
        lambda _platform, _visitor: False,
    )
    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "handle_ai_response_non_stream",
        handle_ai_mock,
    )

    result = await chat_endpoints.chat_completion(
        ChatCompletionRequest(
            api_key="pk_test",
            message="hello",
            from_uid="visitor-open-id",
            stream=False,
        ),
        db=_NoOpDB(),
    )

    assert result["message"] == "ok"
    assert "agent_id" not in handle_ai_mock.await_args.kwargs


@pytest.mark.asyncio
async def test_staff_agent_chat_routes_agent_only(monkeypatch) -> None:
    """Staff AI chat should spawn a background run with only an agent target."""

    project_id = uuid4()
    agent_id = uuid4()
    run_background_mock = AsyncMock(return_value=None)

    def fake_create_task(coro):
        coro.close()
        return SimpleNamespace(cancel=lambda: None)

    monkeypatch.setattr(
        chat_endpoints.chat_service,
        "send_user_message_to_wukongim",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(chat_endpoints.chat_service, "run_background_ai_interaction", run_background_mock)
    monkeypatch.setattr(chat_endpoints.asyncio, "create_task", fake_create_task)

    response = await chat_endpoints.staff_agent_chat(
        StaffAgentChatRequest(agent_id=agent_id, message="hello"),
        db=_NoOpDB(),
        current_user=SimpleNamespace(
            id=uuid4(),
            project_id=project_id,
            project=SimpleNamespace(id=project_id, api_key="ak_project"),
        ),
    )

    assert response.success is True
    assert run_background_mock.call_args.kwargs["agent_id"] == str(agent_id)
    assert "team_id" not in run_background_mock.call_args.kwargs


def test_chat_openapi_uses_agent_route_not_team_route(client) -> None:
    """OpenAPI should expose the single-agent route and drop the team-named route."""

    schema = client.get("/v1/openapi.json").json()

    assert "/v1/chat/agent" in schema["paths"]
    assert "/v1/chat/team" not in schema["paths"]


@pytest.mark.asyncio
async def test_create_platform_uses_single_agent_id(monkeypatch) -> None:
    """Platform creation should persist the new single-agent override field."""

    db = _PlatformDB()
    agent_id = uuid4()

    monkeypatch.setattr(platform_endpoints, "generate_api_key", lambda: "pk_platform")
    monkeypatch.setattr(
        platform_endpoints,
        "_build_platform_response",
        lambda platform, language="zh": platform,
    )

    response = await platform_endpoints.create_platform(
        PlatformCreate(
            name="Website",
            type=PlatformType.WEBSITE,
            agent_id=agent_id,
        ),
        db=db,
        current_user=SimpleNamespace(project_id=uuid4(), username="alice"),
    )

    assert response.agent_id == agent_id
    assert db.added[0].agent_id == agent_id
