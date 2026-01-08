"""Add Slack inbox table.

Revision ID: add_slack_inbox
Revises: add_telegram_inbox
Create Date: 2026-01-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'add_slack_inbox'
down_revision = 'add_telegram_inbox'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pt_slack_inbox',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('platform_id', UUID(as_uuid=True), sa.ForeignKey('pt_platforms.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('slack_user_id', sa.String(255), nullable=False),
        sa.Column('channel_id', sa.String(255), nullable=False, index=True),
        sa.Column('ts', sa.String(50), nullable=False),
        sa.Column('thread_ts', sa.String(50), nullable=True),
        sa.Column('text', sa.Text, nullable=True),
        sa.Column('files', JSONB, nullable=True),
        sa.Column('ai_reply', sa.Text, nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.UniqueConstraint('platform_id', 'channel_id', 'ts', name='uq_slack_inbox_platform_channel_ts'),
        sa.Index('ix_slack_inbox_platform_status', 'platform_id', 'status'),
        sa.Index('ix_slack_inbox_status_fetched', 'status', 'fetched_at'),
    )


def downgrade() -> None:
    op.drop_table('pt_slack_inbox')
