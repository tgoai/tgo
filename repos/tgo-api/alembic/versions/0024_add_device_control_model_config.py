"""add device control model config fields

Revision ID: 0024_add_device_control_model
Revises: 0023_aiprovider_store_fields
Create Date: 2026-02-05

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0024_add_device_control_model'
down_revision: Union[str, None] = '0023_aiprovider_store_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add device control model configuration fields to api_project_ai_configs
    op.add_column(
        'api_project_ai_configs',
        sa.Column(
            'device_control_provider_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('api_ai_providers.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.add_column(
        'api_project_ai_configs',
        sa.Column(
            'device_control_model',
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.execute(
        "COMMENT ON COLUMN api_project_ai_configs.device_control_provider_id IS "
        "'AIProvider ID for device control model'"
    )
    op.execute(
        "COMMENT ON COLUMN api_project_ai_configs.device_control_model IS "
        "'Device control model identifier'"
    )


def downgrade() -> None:
    # Remove device control model configuration fields
    op.drop_column('api_project_ai_configs', 'device_control_model')
    op.drop_column('api_project_ai_configs', 'device_control_provider_id')
