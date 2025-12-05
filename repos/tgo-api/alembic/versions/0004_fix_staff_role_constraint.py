"""Fix staff role constraint to include admin.

Revision ID: 0004_fix_staff_role_constraint
Revises: 0003_add_tag_name_zh
Create Date: 2024-12-04

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0004_fix_staff_role_constraint"
down_revision: Union[str, None] = "0003_add_tag_name_zh"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update staff role check constraint to include 'admin'."""
    # Drop the old constraint
    op.drop_constraint("chk_api_staff_role", "api_staff", type_="check")
    
    # Create new constraint with 'admin' included
    op.create_check_constraint(
        "chk_api_staff_role",
        "api_staff",
        "role IN ('user', 'admin', 'agent')",
    )


def downgrade() -> None:
    """Revert staff role check constraint to exclude 'admin'."""
    # Drop the new constraint
    op.drop_constraint("chk_api_staff_role", "api_staff", type_="check")
    
    # Recreate old constraint (warning: this will fail if any 'admin' roles exist)
    op.create_check_constraint(
        "chk_api_staff_role",
        "api_staff",
        "role IN ('user', 'agent')",
    )

