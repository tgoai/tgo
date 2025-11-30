"""Add collection_type and crawl_config columns to rag_collections table.

Revision ID: rag_0003_collection_type
Revises: rag_0002_website_crawl
Create Date: 2024-01-01 00:00:00.000000

This migration adds:
- collection_type column to distinguish between file/website/qa collections
- crawl_config column (JSONB) for storing website crawl configurations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "rag_0003_collection_type"
down_revision = "rag_0002_website_crawl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add collection_type and crawl_config columns to rag_collections table."""

    # Create the enum type first
    collection_type_enum = sa.Enum(
        'file', 'website', 'qa',
        name='collection_type_enum',
        create_type=True
    )
    collection_type_enum.create(op.get_bind(), checkfirst=True)

    # Add the collection_type column with default value 'file'
    op.add_column(
        'rag_collections',
        sa.Column(
            'collection_type',
            sa.Enum('file', 'website', 'qa', name='collection_type_enum'),
            nullable=False,
            server_default='file'
        )
    )

    # Add the crawl_config column (JSONB, nullable)
    op.add_column(
        'rag_collections',
        sa.Column(
            'crawl_config',
            postgresql.JSONB,
            nullable=True
        )
    )

    # Create index for collection_type
    op.create_index(
        'idx_rag_collections_collection_type',
        'rag_collections',
        ['collection_type']
    )


def downgrade() -> None:
    """Remove collection_type and crawl_config columns from rag_collections table."""

    # Drop the index first
    op.drop_index('idx_rag_collections_collection_type', table_name='rag_collections')

    # Drop the columns
    op.drop_column('rag_collections', 'crawl_config')
    op.drop_column('rag_collections', 'collection_type')

    # Drop the enum type
    sa.Enum(name='collection_type_enum').drop(op.get_bind(), checkfirst=True)

