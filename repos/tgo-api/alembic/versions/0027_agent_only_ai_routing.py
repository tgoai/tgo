"""persist agent-only AI routing

Revision ID: 0027_agent_only_ai_routing
Revises: 0026_ai_provider_default_models
Create Date: 2026-04-09

"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0027_agent_only_ai_routing"
down_revision: Union[str, None] = "0026_ai_provider_default_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _choose_platform_agent_id(agent_ids: Sequence[UUID] | None) -> UUID | None:
    if not agent_ids:
        return None

    return agent_ids[0]


def _backfill_platform_agent_id() -> None:
    platforms = sa.table(
        "api_platforms",
        sa.column("id", sa.UUID()),
        sa.column("agent_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.column("agent_id", sa.UUID()),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(platforms.c.id, platforms.c.agent_ids)
    ).mappings()

    for row in rows:
        agent_id = _choose_platform_agent_id(row["agent_ids"])
        if agent_id is None:
            continue
        bind.execute(
            platforms.update()
            .where(platforms.c.id == row["id"])
            .values(agent_id=agent_id)
        )


def _backfill_platform_agent_ids() -> None:
    platforms = sa.table(
        "api_platforms",
        sa.column("id", sa.UUID()),
        sa.column("agent_id", sa.UUID()),
        sa.column("agent_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.select(platforms.c.id, platforms.c.agent_id)
    ).mappings()

    for row in rows:
        agent_id = row["agent_id"]
        if agent_id is None:
            continue
        bind.execute(
            platforms.update()
            .where(platforms.c.id == row["id"])
            .values(agent_ids=[agent_id])
        )


def upgrade() -> None:
    op.add_column(
        "api_platforms",
        sa.Column(
            "agent_id",
            sa.UUID(),
            nullable=True,
            comment="AI Agent ID assigned to this platform",
        ),
    )
    _backfill_platform_agent_id()
    op.drop_column("api_platforms", "agent_ids")
    op.drop_column("api_projects", "default_team_id")


def downgrade() -> None:
    op.add_column(
        "api_projects",
        sa.Column(
            "default_team_id",
            sa.String(length=64),
            nullable=True,
            comment="Default AI team ID from AI service",
        ),
    )
    op.add_column(
        "api_platforms",
        sa.Column(
            "agent_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
            comment="List of AI Agent IDs assigned to this platform",
        ),
    )
    _backfill_platform_agent_ids()
    op.drop_column("api_platforms", "agent_id")
