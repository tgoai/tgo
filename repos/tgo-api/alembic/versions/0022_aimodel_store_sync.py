"""add store_resource_id to aimodel

Revision ID: 0022_add_aimodel_store_resource_id
Revises: 0021_aimodel_provider_assoc
Create Date: 2026-01-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022_aimodel_store_sync'
down_revision: Union[str, None] = '0021_aimodel_provider_assoc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add store_resource_id to api_ai_models
    op.add_column('api_ai_models', sa.Column('store_resource_id', sa.String(length=100), nullable=True))
    op.execute("COMMENT ON COLUMN api_ai_models.store_resource_id IS 'Store resource ID for models installed from store'")


def downgrade() -> None:
    # Remove store_resource_id from api_ai_models
    op.drop_column('api_ai_models', 'store_resource_id')
