"""add bound_device_id to ai_agents

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2026-02-06 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add bound_device_id column to ai_agents
    op.add_column(
        'ai_agents',
        sa.Column(
            'bound_device_id',
            sa.String(length=100),
            nullable=True,
            comment='Bound device ID for device control MCP connection'
        )
    )


def downgrade() -> None:
    op.drop_column('ai_agents', 'bound_device_id')
