"""Initial device control tables

Revision ID: 0001_init
Revises:
Create Date: 2026-01-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create device type enum (use raw SQL with IF NOT EXISTS for safety)
    op.execute("DO $$ BEGIN CREATE TYPE dc_device_type AS ENUM ('desktop', 'mobile'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    # Create device status enum (use raw SQL with IF NOT EXISTS for safety)
    op.execute("DO $$ BEGIN CREATE TYPE dc_device_status AS ENUM ('online', 'offline'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    # Create dc_devices table
    op.create_table(
        "dc_devices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column(
            "device_type",
            postgresql.ENUM("desktop", "mobile", name="dc_device_type", create_type=False),
            nullable=False,
            server_default="desktop",
        ),
        sa.Column("device_name", sa.String(length=255), nullable=False),
        sa.Column("os", sa.String(length=50), nullable=False),
        sa.Column("os_version", sa.String(length=50), nullable=True),
        sa.Column("screen_resolution", sa.String(length=20), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("online", "offline", name="dc_device_status", create_type=False),
            nullable=False,
            server_default="offline",
        ),
        sa.Column("bind_code", sa.String(length=10), nullable=True),
        sa.Column("bind_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_token", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dc_devices_project_id"), "dc_devices", ["project_id"], unique=False
    )

    # Create dc_sessions table
    op.create_table(
        "dc_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("device_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("screenshots_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["dc_devices.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dc_sessions_device_id"), "dc_sessions", ["device_id"], unique=False
    )
    op.create_index(
        op.f("ix_dc_sessions_agent_id"), "dc_sessions", ["agent_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dc_sessions_agent_id"), table_name="dc_sessions")
    op.drop_index(op.f("ix_dc_sessions_device_id"), table_name="dc_sessions")
    op.drop_table("dc_sessions")
    op.drop_index(op.f("ix_dc_devices_project_id"), table_name="dc_devices")
    op.drop_table("dc_devices")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS dc_device_status")
    op.execute("DROP TYPE IF EXISTS dc_device_type")
