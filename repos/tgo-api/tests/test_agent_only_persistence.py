"""Tests for agent-only AI routing persistence and schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.platform import Platform
from app.models.project import Project
from app.schemas.ai import AgentCreateRequest, AgentResponse, AgentUpdateRequest
from app.schemas.platform_schema import PlatformAISettings


def test_platform_ai_settings_uses_single_agent_id() -> None:
    """Platform AI settings should expose a single agent override."""

    payload = PlatformAISettings.model_validate(
        {"agent_id": "123e4567-e89b-12d3-a456-426614174000"}
    )

    assert str(payload.agent_id) == "123e4567-e89b-12d3-a456-426614174000"
    assert "agent_ids" not in PlatformAISettings.model_fields


def test_platform_model_has_single_agent_id_column() -> None:
    """Platform persistence should store only one platform agent override."""

    columns = Platform.__table__.columns.keys()

    assert "agent_id" in columns
    assert "agent_ids" not in columns


def test_project_model_has_no_default_team_id_column() -> None:
    """Projects should no longer persist a default team selector."""

    assert "default_team_id" not in Project.__table__.columns.keys()


def test_agent_create_request_rejects_team_id() -> None:
    """Create payloads should fail fast when callers send team IDs."""

    with pytest.raises(ValidationError):
        AgentCreateRequest.model_validate(
            {
                "name": "A",
                "model": "gpt-4o",
                "team_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        )


def test_agent_update_request_rejects_team_id() -> None:
    """Update payloads should fail fast when callers send team IDs."""

    with pytest.raises(ValidationError):
        AgentUpdateRequest.model_validate(
            {"team_id": "123e4567-e89b-12d3-a456-426614174000"}
        )


def test_agent_response_has_no_team_id_field() -> None:
    """Agent responses should no longer advertise team affiliation."""

    assert "team_id" not in AgentResponse.model_fields
