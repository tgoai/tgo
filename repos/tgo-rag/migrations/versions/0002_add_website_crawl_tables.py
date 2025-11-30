"""Add website crawl tables.

Revision ID: rag_0002_website_crawl
Revises: rag_0001_baseline
Create Date: 2024-01-01 00:00:00.000000

This migration adds tables for website crawling functionality:
- rag_website_crawl_jobs: Stores crawl job configurations and status
- rag_website_pages: Stores individual crawled pages
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "rag_0002_website_crawl"
down_revision = "rag_0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create website crawl tables."""
    
    # Create rag_website_crawl_jobs table
    op.create_table(
        "rag_website_crawl_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_url", sa.String(2048), nullable=False),
        sa.Column("max_pages", sa.Integer, nullable=False, default=100),
        sa.Column("max_depth", sa.Integer, nullable=False, default=3),
        sa.Column("include_patterns", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("exclude_patterns", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, default="pending"),
        sa.Column("pages_discovered", sa.Integer, nullable=False, default=0),
        sa.Column("pages_crawled", sa.Integer, nullable=False, default=0),
        sa.Column("pages_processed", sa.Integer, nullable=False, default=0),
        sa.Column("pages_failed", sa.Integer, nullable=False, default=0),
        sa.Column("crawl_options", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["rag_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collection_id"], ["rag_collections.id"], ondelete="CASCADE"),
    )
    
    # Create indexes for rag_website_crawl_jobs
    op.create_index("ix_rag_website_crawl_jobs_project_id", "rag_website_crawl_jobs", ["project_id"])
    op.create_index("ix_rag_website_crawl_jobs_collection_id", "rag_website_crawl_jobs", ["collection_id"])
    op.create_index("ix_rag_website_crawl_jobs_status", "rag_website_crawl_jobs", ["status"])
    op.create_index("ix_rag_website_crawl_jobs_created_at", "rag_website_crawl_jobs", ["created_at"])
    
    # Create rag_website_pages table
    op.create_table(
        "rag_website_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("crawl_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("depth", sa.Integer, nullable=False, default=0),
        sa.Column("content_markdown", sa.Text, nullable=True),
        sa.Column("content_length", sa.Integer, nullable=False, default=0),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("meta_description", sa.Text, nullable=True),
        sa.Column("http_status_code", sa.Integer, nullable=True),
        sa.Column("page_metadata", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["rag_website_crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["rag_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["rag_files.id"], ondelete="SET NULL"),
    )
    
    # Create indexes for rag_website_pages
    op.create_index("ix_rag_website_pages_crawl_job_id", "rag_website_pages", ["crawl_job_id"])
    op.create_index("ix_rag_website_pages_project_id", "rag_website_pages", ["project_id"])
    op.create_index("ix_rag_website_pages_url_hash", "rag_website_pages", ["url_hash"])
    op.create_index("ix_rag_website_pages_status", "rag_website_pages", ["status"])
    op.create_index(
        "ix_rag_website_pages_job_url_unique",
        "rag_website_pages",
        ["crawl_job_id", "url_hash"],
        unique=True
    )


def downgrade() -> None:
    """Drop website crawl tables."""
    
    # Drop indexes first
    op.drop_index("ix_rag_website_pages_job_url_unique", table_name="rag_website_pages")
    op.drop_index("ix_rag_website_pages_status", table_name="rag_website_pages")
    op.drop_index("ix_rag_website_pages_url_hash", table_name="rag_website_pages")
    op.drop_index("ix_rag_website_pages_project_id", table_name="rag_website_pages")
    op.drop_index("ix_rag_website_pages_crawl_job_id", table_name="rag_website_pages")
    
    op.drop_index("ix_rag_website_crawl_jobs_created_at", table_name="rag_website_crawl_jobs")
    op.drop_index("ix_rag_website_crawl_jobs_status", table_name="rag_website_crawl_jobs")
    op.drop_index("ix_rag_website_crawl_jobs_collection_id", table_name="rag_website_crawl_jobs")
    op.drop_index("ix_rag_website_crawl_jobs_project_id", table_name="rag_website_crawl_jobs")
    
    # Drop tables
    op.drop_table("rag_website_pages")
    op.drop_table("rag_website_crawl_jobs")

