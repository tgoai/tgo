"""Add visitor assignment rule, history tables and staff description/name fields.

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_assignment_rule"
down_revision: Union[str, None] = "0005_add_permissions_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add visitor_assignment_rules, visitor_assignment_history tables and staff.description/name columns."""
    
    # Add name column to api_staff table
    op.add_column(
        "api_staff",
        sa.Column(
            "name",
            sa.String(100),
            nullable=True,
            comment="Staff real name",
        ),
    )
    
    # Add description column to api_staff table
    op.add_column(
        "api_staff",
        sa.Column(
            "description",
            sa.String(500),
            nullable=True,
            comment="Staff description for LLM assignment prompts",
        ),
    )
    
    # Create visitor_assignment_rules table
    op.create_table(
        "api_visitor_assignment_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            comment="Associated project ID (one rule per project)",
        ),
        sa.Column(
            "ai_provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_ai_providers.id", ondelete="SET NULL"),
            nullable=True,
            comment="AI provider to use for assignment analysis",
        ),
        sa.Column(
            "model",
            sa.String(100),
            nullable=True,
            comment="Specific model to use. If null, uses provider's default",
        ),
        sa.Column(
            "prompt",
            sa.Text,
            nullable=True,
            comment="Custom prompt for assignment analysis. If null, uses system default",
        ),
        sa.Column(
            "llm_assignment_enabled",
            sa.Boolean,
            nullable=False,
            default=True,
            comment="Whether to use LLM for automatic visitor assignment",
        ),
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=True,
            default="Asia/Shanghai",
            comment="Timezone for service hours (e.g., Asia/Shanghai, America/New_York)",
        ),
        sa.Column(
            "service_weekdays",
            postgresql.ARRAY(sa.Integer),
            nullable=True,
            comment="Service weekdays (1=Monday, 7=Sunday), e.g., [1,2,3,4,5]",
        ),
        sa.Column(
            "service_start_time",
            sa.String(5),
            nullable=True,
            comment="Service start time in HH:MM format, e.g., 09:00",
        ),
        sa.Column(
            "service_end_time",
            sa.String(5),
            nullable=True,
            comment="Service end time in HH:MM format, e.g., 18:00",
        ),
        sa.Column(
            "max_concurrent_chats",
            sa.Integer,
            nullable=True,
            default=10,
            comment="Maximum concurrent chats per staff member",
        ),
        sa.Column(
            "auto_close_hours",
            sa.Integer,
            nullable=True,
            default=48,
            comment="Auto close chat after N hours of inactivity",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="Creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            comment="Last update timestamp",
        ),
    )
    
    # Create index on project_id for faster lookups
    op.create_index(
        "ix_api_visitor_assignment_rules_project_id",
        "api_visitor_assignment_rules",
        ["project_id"],
        unique=True,
    )
    
    # Create index on ai_provider_id
    op.create_index(
        "ix_api_visitor_assignment_rules_ai_provider_id",
        "api_visitor_assignment_rules",
        ["ai_provider_id"],
    )
    
    # Create visitor_sessions table
    op.create_table(
        "api_visitor_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_projects.id", ondelete="CASCADE"),
            nullable=False,
            comment="Associated project ID",
        ),
        sa.Column(
            "visitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_visitors.id", ondelete="CASCADE"),
            nullable=False,
            comment="Visitor who initiated this session",
        ),
        sa.Column(
            "staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_staff.id", ondelete="SET NULL"),
            nullable=True,
            comment="Staff member currently handling this session",
        ),
        sa.Column(
            "platform_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_platforms.id", ondelete="SET NULL"),
            nullable=True,
            comment="Platform where this session originated",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="open",
            comment="Session status: open, closed",
        ),
        sa.Column(
            "closed_at",
            sa.DateTime,
            nullable=True,
            comment="Timestamp when session was closed",
        ),
        sa.Column(
            "duration_seconds",
            sa.Integer,
            nullable=True,
            comment="Total session duration in seconds",
        ),
        sa.Column(
            "message_count",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Total number of messages in this session",
        ),
        sa.Column(
            "visitor_message_count",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Number of messages sent by visitor",
        ),
        sa.Column(
            "staff_message_count",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Number of messages sent by staff",
        ),
        sa.Column(
            "ai_message_count",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Number of messages sent by AI",
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime,
            nullable=True,
            comment="Timestamp of the last message in this session",
        ),
        sa.Column(
            "last_message_seq",
            sa.Integer,
            nullable=True,
            comment="Sequence number of the last message in this session",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="Session start timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            comment="Last update timestamp",
        ),
    )
    
    # Create indexes for visitor_sessions
    op.create_index(
        "ix_api_visitor_sessions_project_id",
        "api_visitor_sessions",
        ["project_id"],
    )
    op.create_index(
        "ix_api_visitor_sessions_visitor_id",
        "api_visitor_sessions",
        ["visitor_id"],
    )
    op.create_index(
        "ix_api_visitor_sessions_staff_id",
        "api_visitor_sessions",
        ["staff_id"],
    )
    op.create_index(
        "ix_api_visitor_sessions_status",
        "api_visitor_sessions",
        ["status"],
    )
    op.create_index(
        "ix_api_visitor_sessions_created_at",
        "api_visitor_sessions",
        ["created_at"],
    )
    
    # Create visitor_assignment_history table
    op.create_table(
        "api_visitor_assignment_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_projects.id", ondelete="CASCADE"),
            nullable=False,
            comment="Associated project ID",
        ),
        sa.Column(
            "visitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_visitors.id", ondelete="CASCADE"),
            nullable=False,
            comment="Visitor being assigned",
        ),
        sa.Column(
            "assigned_staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_staff.id", ondelete="SET NULL"),
            nullable=True,
            comment="Staff member assigned to handle the visitor",
        ),
        sa.Column(
            "previous_staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_staff.id", ondelete="SET NULL"),
            nullable=True,
            comment="Previous staff member (for transfers)",
        ),
        sa.Column(
            "assigned_by_staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_staff.id", ondelete="SET NULL"),
            nullable=True,
            comment="Staff who initiated the assignment (for manual assignments)",
        ),
        sa.Column(
            "assignment_rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_visitor_assignment_rules.id", ondelete="SET NULL"),
            nullable=True,
            comment="Assignment rule used (for LLM assignments)",
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_visitor_sessions.id", ondelete="SET NULL"),
            nullable=True,
            comment="Associated visitor session",
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            default="llm",
            comment="Source of assignment: llm, manual, rule, transfer",
        ),
        sa.Column(
            "model_used",
            sa.String(100),
            nullable=True,
            comment="LLM model used for this assignment",
        ),
        sa.Column(
            "prompt_used",
            sa.Text,
            nullable=True,
            comment="Prompt sent to LLM",
        ),
        sa.Column(
            "llm_response",
            sa.Text,
            nullable=True,
            comment="Full LLM response",
        ),
        sa.Column(
            "reasoning",
            sa.Text,
            nullable=True,
            comment="LLM reasoning for the assignment decision",
        ),
        sa.Column(
            "visitor_message",
            sa.Text,
            nullable=True,
            comment="Visitor's message/question at assignment time",
        ),
        sa.Column(
            "visitor_context",
            postgresql.JSONB,
            nullable=True,
            comment="Additional visitor context (intent, sentiment, etc.)",
        ),
        sa.Column(
            "candidate_staff_ids",
            postgresql.JSONB,
            nullable=True,
            comment="List of staff IDs considered for assignment",
        ),
        sa.Column(
            "candidate_scores",
            postgresql.JSONB,
            nullable=True,
            comment="Scores/rankings for each candidate",
        ),
        sa.Column(
            "response_time_ms",
            sa.Integer,
            nullable=True,
            comment="LLM response time in milliseconds",
        ),
        sa.Column(
            "token_usage",
            postgresql.JSONB,
            nullable=True,
            comment="Token usage statistics",
        ),
        sa.Column(
            "notes",
            sa.Text,
            nullable=True,
            comment="Additional notes or comments",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="Assignment timestamp",
        ),
    )
    
    # Create indexes for assignment history
    op.create_index(
        "ix_api_visitor_assignment_history_project_id",
        "api_visitor_assignment_history",
        ["project_id"],
    )
    op.create_index(
        "ix_api_visitor_assignment_history_visitor_id",
        "api_visitor_assignment_history",
        ["visitor_id"],
    )
    op.create_index(
        "ix_api_visitor_assignment_history_assigned_staff_id",
        "api_visitor_assignment_history",
        ["assigned_staff_id"],
    )
    op.create_index(
        "ix_api_visitor_assignment_history_created_at",
        "api_visitor_assignment_history",
        ["created_at"],
    )
    op.create_index(
        "ix_api_visitor_assignment_history_source",
        "api_visitor_assignment_history",
        ["source"],
    )
    
    # Create visitor_waiting_queue table
    op.create_table(
        "api_visitor_waiting_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_projects.id", ondelete="CASCADE"),
            nullable=False,
            comment="Associated project ID",
        ),
        sa.Column(
            "visitor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_visitors.id", ondelete="CASCADE"),
            nullable=False,
            comment="Visitor waiting in queue",
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_visitor_sessions.id", ondelete="SET NULL"),
            nullable=True,
            comment="Associated visitor session",
        ),
        sa.Column(
            "assigned_staff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("api_staff.id", ondelete="SET NULL"),
            nullable=True,
            comment="Staff member who picked this visitor from queue",
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            default="no_staff",
            comment="Queue entry source: ai_request, visitor, transfer, system, no_staff",
        ),
        sa.Column(
            "urgency",
            sa.String(10),
            nullable=False,
            default="normal",
            comment="Urgency level: low, normal, high, urgent",
        ),
        sa.Column(
            "position",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Queue position (lower = higher priority)",
        ),
        sa.Column(
            "priority",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Priority level (higher = more urgent), derived from urgency",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="waiting",
            comment="Queue status: waiting, assigned, cancelled, expired",
        ),
        sa.Column(
            "visitor_message",
            sa.Text,
            nullable=True,
            comment="Message that triggered the transfer request",
        ),
        sa.Column(
            "reason",
            sa.String(255),
            nullable=True,
            comment="Reason for entering queue",
        ),
        sa.Column(
            "channel_id",
            sa.String(255),
            nullable=True,
            comment="Associated communication channel identifier",
        ),
        sa.Column(
            "channel_type",
            sa.Integer,
            nullable=True,
            comment="Associated communication channel type code",
        ),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB,
            nullable=True,
            comment="Additional contextual metadata",
        ),
        sa.Column(
            "retry_count",
            sa.Integer,
            nullable=False,
            default=0,
            comment="Number of assignment retry attempts",
        ),
        sa.Column(
            "last_attempt_at",
            sa.DateTime,
            nullable=True,
            comment="Timestamp of the last assignment attempt",
        ),
        sa.Column(
            "entered_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="When visitor entered the queue",
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime,
            nullable=True,
            comment="When visitor was assigned to a staff",
        ),
        sa.Column(
            "exited_at",
            sa.DateTime,
            nullable=True,
            comment="When visitor exited the queue",
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            comment="Record creation timestamp",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            comment="Last update timestamp",
        ),
    )
    
    # Create indexes for waiting queue
    op.create_index(
        "ix_api_visitor_waiting_queue_project_id",
        "api_visitor_waiting_queue",
        ["project_id"],
    )
    op.create_index(
        "ix_api_visitor_waiting_queue_visitor_id",
        "api_visitor_waiting_queue",
        ["visitor_id"],
    )
    op.create_index(
        "ix_api_visitor_waiting_queue_status",
        "api_visitor_waiting_queue",
        ["status"],
    )
    op.create_index(
        "ix_api_visitor_waiting_queue_position",
        "api_visitor_waiting_queue",
        ["position"],
    )
    # Composite index for queue ordering
    op.create_index(
        "ix_api_visitor_waiting_queue_priority_position",
        "api_visitor_waiting_queue",
        ["priority", "position"],
    )
    op.create_index(
        "ix_api_visitor_waiting_queue_source",
        "api_visitor_waiting_queue",
        ["source"],
    )


def downgrade() -> None:
    """Remove visitor_assignment_rules, visitor_assignment_history, visitor_sessions, visitor_waiting_queue tables and staff.description/name columns."""
    
    # Drop waiting queue indexes
    op.drop_index("ix_api_visitor_waiting_queue_source", table_name="api_visitor_waiting_queue")
    op.drop_index("ix_api_visitor_waiting_queue_priority_position", table_name="api_visitor_waiting_queue")
    op.drop_index("ix_api_visitor_waiting_queue_position", table_name="api_visitor_waiting_queue")
    op.drop_index("ix_api_visitor_waiting_queue_status", table_name="api_visitor_waiting_queue")
    op.drop_index("ix_api_visitor_waiting_queue_visitor_id", table_name="api_visitor_waiting_queue")
    op.drop_index("ix_api_visitor_waiting_queue_project_id", table_name="api_visitor_waiting_queue")
    
    # Drop waiting queue table
    op.drop_table("api_visitor_waiting_queue")
    
    # Drop assignment history indexes
    op.drop_index("ix_api_visitor_assignment_history_source", table_name="api_visitor_assignment_history")
    op.drop_index("ix_api_visitor_assignment_history_created_at", table_name="api_visitor_assignment_history")
    op.drop_index("ix_api_visitor_assignment_history_assigned_staff_id", table_name="api_visitor_assignment_history")
    op.drop_index("ix_api_visitor_assignment_history_visitor_id", table_name="api_visitor_assignment_history")
    op.drop_index("ix_api_visitor_assignment_history_project_id", table_name="api_visitor_assignment_history")
    
    # Drop assignment history table
    op.drop_table("api_visitor_assignment_history")
    
    # Drop visitor sessions indexes
    op.drop_index("ix_api_visitor_sessions_created_at", table_name="api_visitor_sessions")
    op.drop_index("ix_api_visitor_sessions_status", table_name="api_visitor_sessions")
    op.drop_index("ix_api_visitor_sessions_staff_id", table_name="api_visitor_sessions")
    op.drop_index("ix_api_visitor_sessions_visitor_id", table_name="api_visitor_sessions")
    op.drop_index("ix_api_visitor_sessions_project_id", table_name="api_visitor_sessions")
    
    # Drop visitor sessions table
    op.drop_table("api_visitor_sessions")
    
    # Drop assignment rules indexes
    op.drop_index("ix_api_visitor_assignment_rules_ai_provider_id", table_name="api_visitor_assignment_rules")
    op.drop_index("ix_api_visitor_assignment_rules_project_id", table_name="api_visitor_assignment_rules")
    
    # Drop assignment rules table
    op.drop_table("api_visitor_assignment_rules")
    
    # Drop description and name columns from api_staff
    op.drop_column("api_staff", "description")
    op.drop_column("api_staff", "name")
