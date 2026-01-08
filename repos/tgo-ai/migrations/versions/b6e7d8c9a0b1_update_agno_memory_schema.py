"""update agno memory schema

Revision ID: b6e7d8c9a0b1
Revises: af2b3c4d5e6f
Create Date: 2026-01-08 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6e7d8c9a0b1'
down_revision: Union[str, None] = 'af2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at and feedback columns to agno_memories table
    # The logs indicate the table is in the 'ai' schema
    # We use raw SQL to handle the 'IF NOT EXISTS' logic which is more robust for external tables
    op.execute('ALTER TABLE IF EXISTS ai.agno_memories ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP')
    op.execute('ALTER TABLE IF EXISTS ai.agno_memories ADD COLUMN IF NOT EXISTS feedback JSONB')


def downgrade() -> None:
    # Remove created_at and feedback columns from agno_memories table
    op.execute('ALTER TABLE IF EXISTS ai.agno_memories DROP COLUMN IF EXISTS created_at')
    op.execute('ALTER TABLE IF EXISTS ai.agno_memories DROP COLUMN IF EXISTS feedback')

