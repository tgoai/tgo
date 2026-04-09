"""Shared rule helpers for the agent-only runtime rollout."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID


JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]

_MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


class AgentLike(Protocol):
    """Minimal fields needed for rollout default-agent selection."""

    id: UUID
    created_at: datetime | None
    updated_at: datetime | None


def merge_agent_config(
    agent_config: Mapping[str, JsonValue] | None,
    team_config: Mapping[str, JsonValue] | None,
) -> JsonObject:
    """Deep-merge runtime config with agent-side precedence."""

    merged: JsonObject = {}
    team_mapping = team_config or {}
    agent_mapping = agent_config or {}

    for key in team_mapping:
        merged[key] = _clone_json_value(team_mapping[key])

    for key, agent_value in agent_mapping.items():
        if key in team_mapping and isinstance(agent_value, Mapping) and isinstance(team_mapping[key], Mapping):
            merged[key] = merge_agent_config(
                _ensure_json_mapping(agent_value),
                _ensure_json_mapping(team_mapping[key]),
            )
            continue

        merged[key] = _clone_json_value(agent_value)

    return merged


def choose_rollout_default_agent(candidates: Sequence[AgentLike]) -> AgentLike | None:
    """Pick the deterministic survivor for default-agent rollout."""

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda agent: (
            _normalize_datetime(agent.updated_at),
            _normalize_datetime(agent.created_at),
            str(agent.id),
        ),
    )


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return _MIN_DATETIME
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ensure_json_mapping(value: Mapping[str, JsonValue]) -> JsonObject:
    return {key: _clone_json_value(item) for key, item in value.items()}


def _clone_json_value(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: _clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    return value
