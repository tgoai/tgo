"""rename toolstore to store in credentials

Revision ID: 0020_rename_toolstore_to_store
Revises: 0019_add_toolstore_credentials
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0020_rename_toolstore_to_store'
down_revision: Union[str, None] = '0019_add_toolstore_credentials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename table
    op.rename_table('api_toolstore_credentials', 'api_store_credentials')
    
    # 2. Rename columns
    op.alter_column('api_store_credentials', 'toolstore_user_id', new_column_name='store_user_id')
    op.alter_column('api_store_credentials', 'toolstore_email', new_column_name='store_email')


def downgrade() -> None:
    # 1. Rename columns back
    op.alter_column('api_store_credentials', 'store_user_id', new_column_name='toolstore_user_id')
    op.alter_column('api_store_credentials', 'store_email', new_column_name='toolstore_email')
    
    # 2. Rename table back
    op.rename_table('api_store_credentials', 'api_toolstore_credentials')
