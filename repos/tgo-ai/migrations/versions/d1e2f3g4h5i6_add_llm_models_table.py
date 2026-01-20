"""add llm models table

Revision ID: d1e2f3g4h5i6
Revises: c1d2e3f4g5h6
Create Date: 2026-01-20 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3g4h5i6'
down_revision: Union[str, None] = 'c1d2e3f4g5h6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ai_llm_models table
    op.create_table(
        'ai_llm_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, comment='Primary key UUID (externally provided)'),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), nullable=False, comment='Associated provider ID'),
        sa.Column('model_id', sa.String(length=100), nullable=False, comment='Model identifier (e.g., gpt-4, claude-3-opus, qwen-max)'),
        sa.Column('model_name', sa.String(length=100), nullable=False, comment='Display name for the model'),
        sa.Column('model_type', sa.String(length=20), server_default='chat', nullable=False, comment='Model type: chat or embedding'),
        sa.Column('description', sa.String(length=255), nullable=True, comment='Optional description of the model'),
        sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Model capabilities JSON, e.g., {vision: true, function_calling: true}'),
        sa.Column('context_window', sa.Integer(), nullable=True, comment='Context window size (tokens)'),
        sa.Column('max_tokens', sa.Integer(), nullable=True, comment='Maximum output tokens'),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False, comment='Whether this model is enabled'),
        sa.Column('store_resource_id', sa.String(length=100), nullable=True, comment='Store resource ID for models installed from store'),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='When this record was last synchronized'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Record last update timestamp'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True, comment='Soft delete timestamp'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_llm_providers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_id', 'model_id', name='uq_ai_llm_models_provider_model')
    )
    op.create_index('idx_llm_models_model_type', 'ai_llm_models', ['model_type'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_llm_models_model_type', table_name='ai_llm_models')
    op.drop_table('ai_llm_models')
