"""add llm provider default model

Revision ID: c1d2e3f4g5h6
Revises: a2b3c4d5e6f7
Create Date: 2026-01-20 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4g5h6'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add default_model column to ai_llm_providers
    op.add_column('ai_llm_providers', sa.Column('default_model', sa.String(length=100), nullable=True, comment='Default model identifier (e.g., gpt-4o, qwen-plus)'))


def downgrade() -> None:
    # Remove default_model column from ai_llm_providers
    op.drop_column('ai_llm_providers', 'default_model')
