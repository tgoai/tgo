"""rename toolstore to store in ai_tools

Revision ID: f1g2h3i4j5k6
Revises: e7f8g9h0i1j2
Create Date: 2026-01-13 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1g2h3i4j5k6'
down_revision: Union[str, None] = 'e7f8g9h0i1j2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update enum type tool_source_type_enum
    # Postgres doesn't support adding values within a transaction block easily
    # But since we use autocommit or can handle it outside, we use this:
    op.execute("ALTER TYPE tool_source_type_enum ADD VALUE IF NOT EXISTS 'STORE'")

    # 2. Rename column toolstore_tool_id to store_resource_id
    op.alter_column('ai_tools', 'toolstore_tool_id', new_column_name='store_resource_id')
    
    # 3. Add index on store_resource_id
    op.create_index('idx_tools_store_resource_id', 'ai_tools', ['store_resource_id'], unique=False)


def downgrade() -> None:
    # 1. Drop index
    op.drop_index('idx_tools_store_resource_id', table_name='ai_tools')
    
    # 2. Rename column back
    op.alter_column('ai_tools', 'store_resource_id', new_column_name='toolstore_tool_id')
    
    # Note: We don't remove 'STORE' from enum in downgrade as it's not supported by Postgres
