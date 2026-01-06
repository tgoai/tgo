"""Add pt_telegram_inbox table for Telegram Bot messages

Revision ID: add_telegram_inbox
Revises: add_dingtalk_inbox
Create Date: 2026-01-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_telegram_inbox'
down_revision = 'add_dingtalk_inbox'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pt_telegram_inbox',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('platform_id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('update_id', sa.BigInteger(), nullable=True),
        sa.Column('from_user', sa.String(length=255), nullable=False),
        sa.Column('from_username', sa.String(length=255), nullable=True),
        sa.Column('from_display_name', sa.String(length=255), nullable=True),
        sa.Column('chat_id', sa.String(length=255), nullable=False),
        sa.Column('chat_type', sa.String(length=20), server_default='private', nullable=False),
        sa.Column('msg_type', sa.String(length=50), server_default='text', nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('ai_reply', sa.Text(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['platform_id'], ['pt_platforms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('platform_id', 'message_id', 'chat_id', name='uq_telegram_inbox_platform_message_chat')
    )
    op.create_index('ix_pt_telegram_inbox_platform_id', 'pt_telegram_inbox', ['platform_id'], unique=False)
    op.create_index('ix_pt_telegram_inbox_chat_id', 'pt_telegram_inbox', ['chat_id'], unique=False)
    op.create_index('ix_telegram_inbox_platform_status', 'pt_telegram_inbox', ['platform_id', 'status'], unique=False)
    op.create_index('ix_telegram_inbox_status_fetched', 'pt_telegram_inbox', ['status', 'fetched_at'], unique=False)
    op.create_index('ix_telegram_inbox_update_id', 'pt_telegram_inbox', ['update_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_telegram_inbox_update_id', table_name='pt_telegram_inbox')
    op.drop_index('ix_telegram_inbox_status_fetched', table_name='pt_telegram_inbox')
    op.drop_index('ix_telegram_inbox_platform_status', table_name='pt_telegram_inbox')
    op.drop_index('ix_pt_telegram_inbox_chat_id', table_name='pt_telegram_inbox')
    op.drop_index('ix_pt_telegram_inbox_platform_id', table_name='pt_telegram_inbox')
    op.drop_table('pt_telegram_inbox')
