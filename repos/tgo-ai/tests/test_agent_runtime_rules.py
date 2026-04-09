from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.services.agent_runtime_rules import (
    choose_default_agent_for_project,
    choose_rollout_default_agent,
    merge_agent_config,
)


@dataclass(frozen=True)
class AgentRecord:
    id: UUID
    created_at: datetime | None
    updated_at: datetime | None
    is_default: bool = False
    team_id: UUID | None = None
    deleted_at: datetime | None = None


@dataclass(frozen=True)
class TeamRecord:
    id: UUID
    is_default: bool = False
    deleted_at: datetime | None = None


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


def test_choose_default_agent_for_project_prefers_explicit_default_agent() -> None:
    now = datetime.now(tz=timezone.utc)
    default_team = TeamRecord(id=uuid4(), is_default=True)
    explicit_default = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
        is_default=True,
    )
    default_team_member = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=1),
        updated_at=now,
        team_id=default_team.id,
    )

    chosen = choose_default_agent_for_project(
        [default_team_member, explicit_default],
        [default_team],
    )

    assert chosen == explicit_default


def test_choose_default_agent_for_project_prefers_default_team_member_before_other_agents() -> None:
    now = datetime.now(tz=timezone.utc)
    default_team = TeamRecord(id=uuid4(), is_default=True)
    default_team_member = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
        team_id=default_team.id,
    )
    newer_non_team_agent = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=1),
        updated_at=now,
    )

    chosen = choose_default_agent_for_project(
        [newer_non_team_agent, default_team_member],
        [default_team],
    )

    assert chosen == default_team_member


def test_choose_default_agent_for_project_promotes_sole_active_agent() -> None:
    now = datetime.now(tz=timezone.utc)
    active_agent = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    )
    deleted_agent = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=4),
        updated_at=now - timedelta(hours=3),
        deleted_at=now - timedelta(minutes=1),
    )

    chosen = choose_default_agent_for_project([deleted_agent, active_agent], [])

    assert chosen == active_agent


def test_choose_default_agent_for_project_returns_none_without_eligible_fallback() -> None:
    now = datetime.now(tz=timezone.utc)
    first_agent = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
    )
    second_agent = AgentRecord(
        id=uuid4(),
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=1),
    )

    chosen = choose_default_agent_for_project([first_agent, second_agent], [])

    assert chosen is None
