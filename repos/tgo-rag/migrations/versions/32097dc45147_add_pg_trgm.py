"""add pg_trgm extension

Revision ID: 32097dc45147
Revises: 21097dc45146
Create Date: 2026-01-26 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32097dc45147'
down_revision = '21097dc45146'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
