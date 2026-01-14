"""add store fields to aiprovider

Revision ID: 0023_aiprovider_store_fields
Revises: 0022_aimodel_store_sync
Create Date: 2026-01-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0023_aiprovider_store_fields'
down_revision: Union[str, None] = '0022_aimodel_store_sync'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add store_resource_id and is_from_store to api_ai_providers
    op.add_column('api_ai_providers', sa.Column('store_resource_id', sa.String(length=100), nullable=True))
    op.add_column('api_ai_providers', sa.Column('is_from_store', sa.Boolean(), nullable=False, server_default='false'))
    
    op.execute("COMMENT ON COLUMN api_ai_providers.store_resource_id IS 'Store resource ID if provider is from store'")
    op.execute("COMMENT ON COLUMN api_ai_providers.is_from_store IS 'Whether this provider was created from store'")


def downgrade() -> None:
    # Remove columns from api_ai_providers
    op.drop_column('api_ai_providers', 'is_from_store')
    op.drop_column('api_ai_providers', 'store_resource_id')
