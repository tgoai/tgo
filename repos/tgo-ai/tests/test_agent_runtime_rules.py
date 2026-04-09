from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.services.agent_runtime_rules import choose_rollout_default_agent, merge_agent_config


@dataclass(frozen=True)
class AgentRecord:
    id: UUID
    created_at: datetime | None
    updated_at: datetime | None


def test_merge_agent_config_recursively_prefers_agent_values() -> None:
    team_config = {
        "memory": {"enabled": True, "window": 12},
        "tools": {"mode": "team", "allowed": ["search", "handoff"]},
        "temperature": 0.3,
    }
    agent_config = {
        "memory": {"window": 4},
        "tools": {"allowed": ["search"]},
        "temperature": None,
    }

    merged = merge_agent_config(agent_config, team_config)

    assert merged == {
        "memory": {"enabled": True, "window": 4},
        "tools": {"mode": "team", "allowed": ["search"]},
        "temperature": None,
    }


def test_merge_agent_config_keeps_agent_none_as_explicit_override() -> None:
    assert merge_agent_config({"temperature": None}, {"temperature": 0.2}) == {
        "temperature": None,
    }


def test_choose_rollout_default_agent_uses_updated_created_uuid_order() -> None:
    now = datetime.now(tz=timezone.utc)
    older_agent = AgentRecord(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
    )
    newer_agent = AgentRecord(
        id=UUID("00000000-0000-0000-0000-000000000003"),
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    )
    tied_agent = AgentRecord(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    )

    chosen = choose_rollout_default_agent([older_agent, newer_agent, tied_agent])

    assert chosen == newer_agent


def test_choose_rollout_default_agent_returns_none_for_empty_candidates() -> None:
    assert choose_rollout_default_agent([]) is None

