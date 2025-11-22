"""add is_supported and name_en to platform types

Revision ID: 0010_platform_type_support_en
Revises: 01e03a3b82e2
Create Date: 2025-11-19 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_platform_type_support_en"
down_revision: Union[str, None] = "01e03a3b82e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_platform_types",
        sa.Column(
            "is_supported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.sql.expression.true(),
        ),
    )
    op.add_column(
        "api_platform_types",
        sa.Column(
            "name_en",
            sa.String(length=100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("api_platform_types", "name_en")
    op.drop_column("api_platform_types", "is_supported")

