"""add config field to ai_teams

Revision ID: af2b3c4d5e6f
Revises: 1f73bd15b1c0
Create Date: 2026-01-08 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af2b3c4d5e6f'
down_revision: Union[str, None] = '1f73bd15b1c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add config column to ai_teams table
    op.add_column('ai_teams', sa.Column('config', sa.JSON(), nullable=True, comment='Team configuration (respond_directly, num_history_runs, etc.)'))


def downgrade() -> None:
    # Remove config column from ai_teams table
    op.drop_column('ai_teams', 'config')

