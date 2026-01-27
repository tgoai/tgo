"""Initial schema for tgo-vision-agent.

Creates tables for:
- va_inbox: Message inbox for UI automation
- va_sessions: AgentBay session management
- va_message_fingerprints: Message deduplication

Revision ID: 0001_init
Revises:
Create Date: 2026-01-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = '0001_init'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create va_inbox table
    op.create_table(
        'va_inbox',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('platform_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('app_type', sa.String(50), nullable=False, index=True,
                  comment='Application type: wechat, douyin, xiaohongshu, etc.'),
        sa.Column('contact_id', sa.String(255), nullable=False, index=True,
                  comment='Contact ID within the application'),
        sa.Column('contact_name', sa.String(255), nullable=False,
                  comment='Contact display name'),
        sa.Column('message_content', sa.Text, nullable=False,
                  comment='Message content'),
        sa.Column('message_type', sa.String(50), nullable=False, default='text',
                  comment='Message type: text, image, voice, video, etc.'),
        sa.Column('direction', sa.String(20), nullable=False,
                  comment='Message direction: inbound or outbound'),
        sa.Column('status', sa.String(50), nullable=False, default='pending', index=True,
                  comment='Processing status: pending, processing, completed, failed'),
        sa.Column('screenshot_path', sa.String(500), nullable=True,
                  comment='Path to screenshot for debugging'),
        sa.Column('app_metadata', JSONB, nullable=True,
                  comment='Application-specific metadata'),
        sa.Column('error_message', sa.Text, nullable=True,
                  comment='Error message if processing failed'),
        sa.Column('retry_count', sa.Integer, default=0,
                  comment='Number of retry attempts'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create va_sessions table
    op.create_table(
        'va_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('platform_id', UUID(as_uuid=True), nullable=False, unique=True, index=True,
                  comment='Platform ID from tgo-api (one session per platform)'),
        sa.Column('app_type', sa.String(50), nullable=False, index=True,
                  comment='Application type: wechat, douyin, xiaohongshu, etc.'),
        sa.Column('agentbay_session_id', sa.String(255), nullable=False, unique=True,
                  comment='AgentBay session ID'),
        sa.Column('environment_type', sa.String(50), nullable=False, default='mobile',
                  comment='Environment type: mobile or desktop'),
        sa.Column('status', sa.String(50), nullable=False, default='active', index=True,
                  comment='Session status: active, paused, terminated'),
        sa.Column('app_login_status', sa.String(50), nullable=False, default='offline',
                  comment='App login status: logged_in, qr_pending, offline'),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True,
                  comment='Last heartbeat timestamp'),
        sa.Column('last_screenshot_at', sa.DateTime(timezone=True), nullable=True,
                  comment='Last screenshot timestamp'),
        sa.Column('config', JSONB, nullable=True,
                  comment='Session configuration'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=False),
    )

    # Create va_message_fingerprints table
    op.create_table(
        'va_message_fingerprints',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('platform_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('fingerprint', sa.String(64), nullable=False, index=True,
                  comment='SHA-256 hash of message content + contact + approximate time'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False,
                  comment='Expiration time for automatic cleanup'),
    )

    # Create composite indexes for common queries
    op.create_index(
        'ix_va_inbox_platform_status',
        'va_inbox',
        ['platform_id', 'status']
    )
    op.create_index(
        'ix_va_inbox_platform_contact',
        'va_inbox',
        ['platform_id', 'contact_id']
    )
    op.create_index(
        'ix_va_fingerprints_platform_fingerprint',
        'va_message_fingerprints',
        ['platform_id', 'fingerprint']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_va_fingerprints_platform_fingerprint', 'va_message_fingerprints')
    op.drop_index('ix_va_inbox_platform_contact', 'va_inbox')
    op.drop_index('ix_va_inbox_platform_status', 'va_inbox')

    # Drop tables
    op.drop_table('va_message_fingerprints')
    op.drop_table('va_sessions')
    op.drop_table('va_inbox')
