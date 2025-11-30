"""Remove project_id foreign key constraints from website tables.

Revision ID: rag_0005_remove_project_fk
Revises: rag_0004_fix_enum
Create Date: 2024-01-03 00:00:00.000000

The project_id is a logical reference to an external API service,
not a local table. Remove the foreign key constraints to allow
inserting records without requiring the project to exist in rag_projects.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "rag_0005_remove_project_fk"
down_revision = "rag_0004_fix_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove project_id foreign key constraints from website tables."""
    
    # Remove foreign key constraint from rag_website_crawl_jobs
    op.drop_constraint(
        "rag_website_crawl_jobs_project_id_fkey",
        "rag_website_crawl_jobs",
        type_="foreignkey"
    )
    
    # Remove foreign key constraint from rag_website_pages
    op.drop_constraint(
        "rag_website_pages_project_id_fkey",
        "rag_website_pages",
        type_="foreignkey"
    )


def downgrade() -> None:
    """Restore project_id foreign key constraints."""
    
    # Re-add foreign key constraint to rag_website_crawl_jobs
    op.create_foreign_key(
        "rag_website_crawl_jobs_project_id_fkey",
        "rag_website_crawl_jobs",
        "rag_projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE"
    )
    
    # Re-add foreign key constraint to rag_website_pages
    op.create_foreign_key(
        "rag_website_pages_project_id_fkey",
        "rag_website_pages",
        "rag_projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE"
    )

