"""add agent_category to ai_agents

Revision ID: g1h2i3j4k5l6
Revises: d1e2f3g4h5i6
Create Date: 2026-01-28 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'd1e2f3g4h5i6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add agent_category column to ai_agents
    # Values: 'normal' (default) or 'computer_use'
    op.add_column(
        'ai_agents',
        sa.Column(
            'agent_category',
            sa.String(length=50),
            nullable=False,
            server_default='normal',
            comment='Agent category: normal or computer_use'
        )
    )
    # Create index for efficient filtering by category
    op.create_index('idx_ai_agents_category', 'ai_agents', ['agent_category'])


def downgrade() -> None:
    op.drop_index('idx_ai_agents_category', table_name='ai_agents')
    op.drop_column('ai_agents', 'agent_category')
