"""remove bind code columns

Revision ID: 0002_remove_bind_code
Revises: 0001_init
Create Date: 2026-01-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_remove_bind_code"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove bind_code and bind_code_expires_at columns from dc_devices
    op.drop_column("dc_devices", "bind_code")
    op.drop_column("dc_devices", "bind_code_expires_at")


def downgrade() -> None:
    # Add bind_code and bind_code_expires_at columns back to dc_devices
    op.add_column("dc_devices", sa.Column("bind_code", sa.String(length=10), nullable=True))
    op.add_column("dc_devices", sa.Column("bind_code_expires_at", sa.DateTime(timezone=True), nullable=True))
