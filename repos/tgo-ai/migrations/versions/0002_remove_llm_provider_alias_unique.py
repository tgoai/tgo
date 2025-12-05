"""remove llm provider project_id alias unique constraint

Revision ID: 0002_remove_alias_unique
Revises: 66112c4c8880
Create Date: 2024-12-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_remove_alias_unique'
down_revision: Union[str, None] = '66112c4c8880'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove the unique constraint on (project_id, alias)
    op.drop_constraint('uq_ai_llm_providers_project_alias', 'ai_llm_providers', type_='unique')


def downgrade() -> None:
    # Re-create the unique constraint
    op.create_unique_constraint(
        'uq_ai_llm_providers_project_alias',
        'ai_llm_providers',
        ['project_id', 'alias']
    )

