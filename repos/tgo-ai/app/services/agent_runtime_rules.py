"""Shared rule helpers for the agent-only runtime rollout."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Protocol, TypeVar, cast
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


class ProjectAgentLike(AgentLike, Protocol):
    """Agent fields needed for project-level default rollout."""

    is_default: bool
    team_id: UUID | None
    deleted_at: datetime | None


class TeamLike(Protocol):
    """Team fields needed for project-level default rollout."""

    id: UUID
    is_default: bool
    deleted_at: datetime | None


AgentLikeT = TypeVar("AgentLikeT", bound=AgentLike)


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
        team_value = team_mapping.get(key)
        if isinstance(agent_value, Mapping) and isinstance(team_value, Mapping):
            merged[key] = merge_agent_config(
                _ensure_json_mapping(agent_value),
                _ensure_json_mapping(team_value),
            )
            continue

        merged[key] = _clone_json_value(agent_value)

    return merged


def choose_rollout_default_agent(candidates: Sequence[AgentLikeT]) -> AgentLikeT | None:
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


def choose_default_agent_for_project(
    agents: Sequence[ProjectAgentLike],
    teams: Sequence[TeamLike],
) -> ProjectAgentLike | None:
    """Choose the post-migration project default agent, if any."""

    active_agents = [agent for agent in agents if agent.deleted_at is None]
    if not active_agents:
        return None

    explicit_defaults = [agent for agent in active_agents if agent.is_default]
    chosen_explicit_default = choose_rollout_default_agent(explicit_defaults)
    if chosen_explicit_default is not None:
        return chosen_explicit_default

    default_team_ids = {
        team.id
        for team in teams
        if team.is_default and team.deleted_at is None
    }
    if default_team_ids:
        default_team_agents = [
            agent for agent in active_agents if agent.team_id in default_team_ids
        ]
        chosen_default_team_agent = choose_rollout_default_agent(default_team_agents)
        if chosen_default_team_agent is not None:
            return chosen_default_team_agent

    if len(active_agents) == 1:
        return active_agents[0]

    return None


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return _MIN_DATETIME
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _ensure_json_mapping(value: Mapping[str, JsonValue]) -> JsonObject:
    return cast(JsonObject, {key: _clone_json_value(item) for key, item in value.items()})


def _clone_json_value(value: JsonValue) -> JsonValue:
    if isinstance(value, Mapping):
        return {key: _clone_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_json_value(item) for item in value]
    return value
