"""Tests for removing team-oriented channel and chat schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.chat import StaffAgentChatRequest, UIUserActionRequest


def test_staff_agent_chat_request_rejects_team_id() -> None:
    """Staff chat requests should only accept agent routing."""

    with pytest.raises(ValidationError):
        StaffAgentChatRequest.model_validate(
            {
                "message": "hello",
                "team_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        )


def test_staff_agent_chat_request_accepts_agent_id() -> None:
    """Agent-only staff chat requests should stay valid."""

    request = StaffAgentChatRequest.model_validate(
        {
            "message": "hello",
            "agent_id": "123e4567-e89b-12d3-a456-426614174000",
        }
    )

    assert str(request.agent_id) == "123e4567-e89b-12d3-a456-426614174000"


def test_ui_user_action_request_has_no_team_id_field() -> None:
    """UI actions should no longer expose team routing."""

    assert "team_id" not in UIUserActionRequest.model_fields


def test_channels_openapi_has_no_team_entity_or_team_metadata(client) -> None:
    """OpenAPI should only document visitor/staff/agent channel entities."""

    schema = client.get("/v1/openapi.json").json()
    channel_info = schema["components"]["schemas"]["ChannelInfoResponse"]
    entity_enum = channel_info["properties"]["entity_type"]["enum"]
    extra_description = channel_info["properties"]["extra"]["description"]

    assert "team" not in entity_enum
    assert "team_id" not in extra_description
