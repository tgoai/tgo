"""Baseline migration for tgo-ai.

This migration represents the starting point of the schema after
resetting migrations. It creates all ai_* tables defined in the
SQLAlchemy models so that a fresh database is fully ready for use.
"""

from alembic import op
from app.models.base import BaseModel

# revision identifiers, used by Alembic.
revision = "ai_0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all ai_* tables defined on BaseModel.metadata.

    We delegate to SQLAlchemy's metadata to ensure the schema matches
    the current models. "checkfirst=True" makes this safe to run on an
    empty database and idempotent if tables already exist.
    """

    bind = op.get_bind()

    # Only create ai_* tables (this matches Alembic's include_* filters)
    tables = [t for t in BaseModel.metadata.sorted_tables if t.name.startswith("ai_")]
    for table in tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Drop all ai_* tables.

    This is primarily for local development/testing. In production you
    typically wouldn't downgrade a baseline in this way.
    """

    bind = op.get_bind()

    # Drop in reverse dependency order
    tables = [t for t in reversed(BaseModel.metadata.sorted_tables) if t.name.startswith("ai_")]
    for table in tables:
        table.drop(bind=bind, checkfirst=True)

