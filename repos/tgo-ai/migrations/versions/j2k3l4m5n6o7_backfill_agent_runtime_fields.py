"""backfill agent runtime fields and enforce default uniqueness

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-04-09 12:00:00.000000

"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import uuid
from typing import Sequence, Union, cast

from alembic import op
import sqlalchemy as sa

from app.services.agent_runtime_rules import (
    JsonObject,
    JsonValue,
    choose_default_agent_for_project,
    merge_agent_config,
)


# revision identifiers, used by Alembic.
revision: str = "j2k3l4m5n6o7"
down_revision: Union[str, None] = "i1j2k3l4m5n6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


@dataclass(frozen=True)
class ProjectAgentState:
    """Minimal agent state needed for deterministic default rollout."""

    id: uuid.UUID
    team_id: uuid.UUID | None
    is_default: bool
    created_at: datetime | None
    updated_at: datetime | None
    deleted_at: datetime | None


@dataclass(frozen=True)
class ProjectTeamState:
    """Minimal team state needed for deterministic default rollout."""

    id: uuid.UUID
    is_default: bool
    deleted_at: datetime | None


def build_agent_runtime_backfill(
    agent_row: Mapping[str, object],
    team_row: Mapping[str, object] | None,
) -> dict[str, object]:
    """Compute the migrated runtime fields for one agent."""

    agent_config = _coerce_json_mapping(agent_row.get("config"))
    team_config = _build_team_runtime_config(team_row)

    return {
        "model": _prefer_agent_value(agent_row.get("model"), _get_mapping_value(team_row, "model")),
        "instruction": _prefer_agent_value(
            agent_row.get("instruction"),
            _get_mapping_value(team_row, "instruction"),
        ),
        "llm_provider_id": _prefer_agent_value(
            agent_row.get("llm_provider_id"),
            _get_mapping_value(team_row, "llm_provider_id"),
        ),
        "config": merge_agent_config(agent_config, team_config),
    }


def upgrade() -> None:
    bind = op.get_bind()

    agents_table = sa.table(
        "ai_agents",
        sa.column("id", sa.UUID()),
        sa.column("project_id", sa.UUID()),
        sa.column("team_id", sa.UUID()),
        sa.column("model", sa.String(length=150)),
        sa.column("instruction", sa.Text()),
        sa.column("llm_provider_id", sa.UUID()),
        sa.column("config", sa.JSON()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    teams_table = sa.table(
        "ai_teams",
        sa.column("id", sa.UUID()),
        sa.column("project_id", sa.UUID()),
        sa.column("model", sa.String(length=150)),
        sa.column("instruction", sa.Text()),
        sa.column("expected_output", sa.Text()),
        sa.column("session_id", sa.String(length=150)),
        sa.column("llm_provider_id", sa.UUID()),
        sa.column("config", sa.JSON()),
        sa.column("is_default", sa.Boolean()),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )

    agent_rows = bind.execute(sa.select(agents_table)).mappings().all()
    team_rows = bind.execute(sa.select(teams_table)).mappings().all()

    teams_by_id = {
        cast(uuid.UUID, row["id"]): row
        for row in team_rows
        if row.get("id") is not None
    }
    teams_by_project: dict[uuid.UUID, list[ProjectTeamState]] = defaultdict(list)
    for row in team_rows:
        project_id = cast(uuid.UUID | None, row.get("project_id"))
        team_id = cast(uuid.UUID | None, row.get("id"))
        if project_id is None or team_id is None:
            continue
        teams_by_project[project_id].append(
            ProjectTeamState(
                id=team_id,
                is_default=bool(row.get("is_default")),
                deleted_at=cast(datetime | None, row.get("deleted_at")),
            )
        )

    agents_by_project: dict[uuid.UUID, list[ProjectAgentState]] = defaultdict(list)
    for row in agent_rows:
        agent_id = cast(uuid.UUID | None, row.get("id"))
        project_id = cast(uuid.UUID | None, row.get("project_id"))
        if agent_id is None or project_id is None:
            continue

        team_id = cast(uuid.UUID | None, row.get("team_id"))
        backfill = build_agent_runtime_backfill(row, teams_by_id.get(team_id))
        bind.execute(
            agents_table.update()
            .where(agents_table.c.id == agent_id)
            .values(**backfill)
        )

        agents_by_project[project_id].append(
            ProjectAgentState(
                id=agent_id,
                team_id=team_id,
                is_default=bool(row.get("is_default")),
                created_at=cast(datetime | None, row.get("created_at")),
                updated_at=cast(datetime | None, row.get("updated_at")),
                deleted_at=cast(datetime | None, row.get("deleted_at")),
            )
        )

    for project_id, project_agents in agents_by_project.items():
        chosen_default = choose_default_agent_for_project(
            project_agents,
            teams_by_project.get(project_id, []),
        )
        bind.execute(
            agents_table.update()
            .where(agents_table.c.project_id == project_id)
            .values(is_default=False)
        )
        if chosen_default is not None:
            bind.execute(
                agents_table.update()
                .where(agents_table.c.id == chosen_default.id)
                .values(is_default=True)
            )

    op.create_index(
        "uq_ai_agents_default_per_project_active",
        "ai_agents",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true AND deleted_at IS NULL"),
        sqlite_where=sa.text("is_default = 1 AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_agents_default_per_project_active", table_name="ai_agents")


def _build_team_runtime_config(team_row: Mapping[str, object] | None) -> JsonObject | None:
    if team_row is None:
        return None

    config = _coerce_json_mapping(team_row.get("config")) or {}
    expected_output = team_row.get("expected_output")
    if expected_output is not None:
        config["expected_output"] = cast(JsonValue, expected_output)
    return config


def _coerce_json_mapping(value: object) -> JsonObject | None:
    if not isinstance(value, Mapping):
        return None

    return {
        str(key): cast(JsonValue, item)
        for key, item in value.items()
    }


def _get_mapping_value(mapping: Mapping[str, object] | None, key: str) -> object | None:
    if mapping is None:
        return None
    return mapping.get(key)


def _prefer_agent_value(agent_value: object | None, team_value: object | None) -> object | None:
    if agent_value is not None:
        return agent_value
    return team_value
