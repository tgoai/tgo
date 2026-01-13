"""add tool title fields to ai_tools

Revision ID: e7f8g9h0i1j2
Revises: a1b2c3d4e5f6
Create Date: 2026-01-13 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7f8g9h0i1j2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to ai_tools
    op.add_column('ai_tools', sa.Column('title', sa.String(length=255), nullable=True, comment='Display title for the tool (Legacy/Fallback)'))
    op.add_column('ai_tools', sa.Column('title_zh', sa.String(length=255), nullable=True, comment='Display title for the tool (Chinese)'))
    op.add_column('ai_tools', sa.Column('title_en', sa.String(length=255), nullable=True, comment='Display title for the tool (English)'))


def downgrade() -> None:
    op.drop_column('ai_tools', 'title_en')
    op.drop_column('ai_tools', 'title_zh')
    op.drop_column('ai_tools', 'title')
