"""Add collection_id column to rag_website_pages table.

Revision ID: rag_0006_add_collection_id
Revises: rag_0005_remove_project_fk
Create Date: 2024-01-04 00:00:00.000000

This migration adds a collection_id column to the rag_website_pages table
to establish a direct relationship between pages and collections.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "rag_0006_add_collection_id"
down_revision = "rag_0005_remove_project_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add collection_id column to rag_website_pages."""
    
    # First, add the column as nullable to handle existing data
    op.add_column(
        "rag_website_pages",
        sa.Column("collection_id", UUID(as_uuid=True), nullable=True)
    )
    
    # Update existing records: get collection_id from the associated crawl_job
    op.execute("""
        UPDATE rag_website_pages wp
        SET collection_id = wcj.collection_id
        FROM rag_website_crawl_jobs wcj
        WHERE wp.crawl_job_id = wcj.id
    """)
    
    # Now make the column non-nullable
    op.alter_column(
        "rag_website_pages",
        "collection_id",
        nullable=False
    )
    
    # Add foreign key constraint
    op.create_foreign_key(
        "rag_website_pages_collection_id_fkey",
        "rag_website_pages",
        "rag_collections",
        ["collection_id"],
        ["id"],
        ondelete="CASCADE"
    )
    
    # Add index for performance
    op.create_index(
        "idx_website_pages_collection_id",
        "rag_website_pages",
        ["collection_id"]
    )


def downgrade() -> None:
    """Remove collection_id column from rag_website_pages."""
    
    # Drop index
    op.drop_index("idx_website_pages_collection_id", table_name="rag_website_pages")
    
    # Drop foreign key constraint
    op.drop_constraint(
        "rag_website_pages_collection_id_fkey",
        "rag_website_pages",
        type_="foreignkey"
    )
    
    # Drop column
    op.drop_column("rag_website_pages", "collection_id")

