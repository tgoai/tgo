"""add device model configuration fields

Revision ID: 0003_add_device_model_config
Revises: 0002_remove_bind_code
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_add_device_model_config"
down_revision: Union[str, None] = "0002_remove_bind_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add AI model configuration fields to dc_devices
    op.add_column(
        "dc_devices",
        sa.Column(
            "ai_provider_id",
            sa.String(length=100),
            nullable=True,
            comment="AI Provider ID for this device",
        ),
    )
    op.add_column(
        "dc_devices",
        sa.Column(
            "model",
            sa.String(length=100),
            nullable=True,
            comment="LLM model identifier for this device",
        ),
    )


def downgrade() -> None:
    # Remove AI model configuration fields from dc_devices
    op.drop_column("dc_devices", "model")
    op.drop_column("dc_devices", "ai_provider_id")
