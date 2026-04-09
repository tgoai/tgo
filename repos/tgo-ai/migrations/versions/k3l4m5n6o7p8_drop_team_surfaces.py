"""drop team surfaces

Revision ID: k3l4m5n6o7p8
Revises: j2k3l4m5n6o7
Create Date: 2026-04-09 18:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k3l4m5n6o7p8"
down_revision: Union[str, None] = "j2k3l4m5n6o7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE ai_agents SET team_id = NULL WHERE team_id IS NOT NULL"))

    with op.batch_alter_table("ai_agents") as batch_op:
        batch_op.drop_column("team_id")

    op.drop_table("ai_teams")


def downgrade() -> None:
    op.create_table(
        "ai_teams",
        sa.Column("project_id", sa.UUID(), nullable=False, comment="Associated project ID (logical reference to API service)"),
        sa.Column("name", sa.String(length=255), nullable=False, comment="Team name"),
        sa.Column("model", sa.String(length=150), nullable=True, comment='LLM model used by the team in format "provider:model_name"'),
        sa.Column("instruction", sa.Text(), nullable=True, comment="Team system prompt/instructions"),
        sa.Column("expected_output", sa.Text(), nullable=True, comment="Expected output format description"),
        sa.Column("session_id", sa.String(length=150), nullable=True, comment="Team session identifier"),
        sa.Column("llm_provider_id", sa.UUID(), nullable=True, comment="Associated LLM provider (credentials) ID"),
        sa.Column("is_default", sa.Boolean(), nullable=False, comment="Whether this is the default team for the project"),
        sa.Column("config", sa.JSON(), nullable=True, comment="Team configuration (respond_directly, num_history_runs, etc.)"),
        sa.Column("id", sa.UUID(), nullable=False, comment="Primary key UUID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="Record creation timestamp"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, comment="Record last update timestamp"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"),
        sa.ForeignKeyConstraint(["llm_provider_id"], ["ai_llm_providers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "is_default", name="uq_ai_teams_default_per_project"),
    )

    with op.batch_alter_table("ai_agents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "team_id",
                sa.UUID(),
                nullable=True,
                comment="Associated team ID for team-based organization",
            )
        )
        batch_op.create_foreign_key(
            None,
            "ai_teams",
            ["team_id"],
            ["id"],
            ondelete="SET NULL",
        )
