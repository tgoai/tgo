"""Tests for setup flow with direct default-agent creation."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints import setup as setup_endpoints
from app.schemas.setup import CreateAdminRequest


class _SetupQuery:
    """Query double with configurable first/all values."""

    def __init__(self, *, first_result: object = None, all_result: object = None) -> None:
        self._first_result = first_result
        self._all_result = all_result if all_result is not None else []

    def filter(self, *_args, **_kwargs) -> "_SetupQuery":
        return self

    def order_by(self, *_args, **_kwargs) -> "_SetupQuery":
        return self

    def first(self) -> object:
        return self._first_result

    def all(self) -> object:
        return self._all_result


class _SetupDB:
    """DB double for setup endpoint tests."""

    def __init__(self) -> None:
        self.added: list[object] = []

    def query(self, model: object) -> _SetupQuery:
        name = getattr(model, "__name__", "")
        if name == "Staff":
            return _SetupQuery(first_result=None)
        if name == "PlatformTypeDefinition":
            return _SetupQuery(all_result=[])
        return _SetupQuery()

    def add(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.utcnow()
        self.added.append(obj)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, _obj: object) -> None:
        return None

    def rollback(self) -> None:
        return None


@pytest.mark.asyncio
async def test_create_default_admin_creates_default_agent_without_team(monkeypatch) -> None:
    """System setup should seed a default agent and never touch team APIs."""

    db = _SetupDB()
    setup_state = SimpleNamespace(
        is_installed=False,
        admin_created=False,
        llm_configured=False,
        skip_llm_config=False,
        setup_completed_at=None,
    )
    create_agent_mock = AsyncMock(return_value={"id": "agent-1"})

    monkeypatch.setattr(setup_endpoints, "_get_or_create_system_setup", lambda _db: setup_state)
    monkeypatch.setattr(setup_endpoints, "_recalculate_install_flags", lambda _setup: None)
    monkeypatch.setattr(setup_endpoints, "generate_api_key", lambda: "generated-api-key")
    monkeypatch.setattr(setup_endpoints, "get_password_hash", lambda _password: "hashed-password")
    monkeypatch.setattr(
        setup_endpoints.wukongim_client,
        "create_channel",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(setup_endpoints.ai_client, "create_agent", create_agent_mock)

    response = await setup_endpoints.create_admin(
        CreateAdminRequest(password="password123", project_name="Demo Project"),
        request=SimpleNamespace(url=SimpleNamespace(path="/v1/setup/admin")),
        db=db,
    )

    assert response.project_name == "Demo Project"
    assert create_agent_mock.await_args.kwargs["agent_data"]["is_default"] is True
    assert not hasattr(setup_endpoints.ai_client, "create_team")
