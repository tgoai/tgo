"""Add rag_qa_pairs table for QA knowledge base.

Revision ID: rag_0007_add_qa_pairs
Revises: rag_0006_add_collection_id
Create Date: 2024-01-05 00:00:00.000000

This migration creates the rag_qa_pairs table for storing question-answer
pairs in QA knowledge base collections.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = "rag_0007_add_qa_pairs"
down_revision = "rag_0006_add_collection_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create rag_qa_pairs table and make file_id nullable in rag_file_documents."""

    # First, make file_id nullable in rag_file_documents to support QA pairs
    # which don't have an associated file
    op.alter_column(
        "rag_file_documents",
        "file_id",
        nullable=True,
    )

    # Drop the existing foreign key constraint
    op.drop_constraint(
        "rag_file_documents_file_id_fkey",
        "rag_file_documents",
        type_="foreignkey"
    )

    # Re-create with SET NULL on delete
    op.create_foreign_key(
        "rag_file_documents_file_id_fkey",
        "rag_file_documents",
        "rag_files",
        ["file_id"],
        ["id"],
        ondelete="SET NULL"
    )

    # Create rag_qa_pairs table
    op.create_table(
        "rag_qa_pairs",
        # Primary key
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        
        # Foreign keys
        sa.Column(
            "collection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rag_collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        
        # Question and answer content
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        
        # Organization
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("subcategory", sa.String(255), nullable=True),
        sa.Column("tags", ARRAY(sa.String(100)), nullable=True),
        sa.Column("qa_metadata", JSONB(), nullable=True),
        
        # Source and status
        sa.Column(
            "source_type",
            sa.String(50),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        
        # Reference to generated document
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rag_file_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create indexes
    op.create_index(
        "idx_qa_pairs_collection_id",
        "rag_qa_pairs",
        ["collection_id"],
    )
    op.create_index(
        "idx_qa_pairs_project_id",
        "rag_qa_pairs",
        ["project_id"],
    )
    op.create_index(
        "idx_qa_pairs_question_hash",
        "rag_qa_pairs",
        ["question_hash"],
    )
    op.create_index(
        "idx_qa_pairs_category",
        "rag_qa_pairs",
        ["category"],
    )
    op.create_index(
        "idx_qa_pairs_status",
        "rag_qa_pairs",
        ["status"],
    )
    
    # GIN index for tags array
    op.create_index(
        "idx_qa_pairs_tags",
        "rag_qa_pairs",
        ["tags"],
        postgresql_using="gin",
    )
    
    # Unique constraint for deduplication
    op.create_unique_constraint(
        "uq_qa_pairs_collection_question",
        "rag_qa_pairs",
        ["collection_id", "question_hash"],
    )


def downgrade() -> None:
    """Drop rag_qa_pairs table and revert file_id changes."""

    # Drop unique constraint
    op.drop_constraint("uq_qa_pairs_collection_question", "rag_qa_pairs", type_="unique")

    # Drop indexes
    op.drop_index("idx_qa_pairs_tags", table_name="rag_qa_pairs")
    op.drop_index("idx_qa_pairs_status", table_name="rag_qa_pairs")
    op.drop_index("idx_qa_pairs_category", table_name="rag_qa_pairs")
    op.drop_index("idx_qa_pairs_question_hash", table_name="rag_qa_pairs")
    op.drop_index("idx_qa_pairs_project_id", table_name="rag_qa_pairs")
    op.drop_index("idx_qa_pairs_collection_id", table_name="rag_qa_pairs")

    # Drop table
    op.drop_table("rag_qa_pairs")

    # Revert file_id changes in rag_file_documents
    # First delete any documents without file_id (QA documents)
    op.execute("DELETE FROM rag_file_documents WHERE file_id IS NULL")

    # Drop the foreign key constraint
    op.drop_constraint(
        "rag_file_documents_file_id_fkey",
        "rag_file_documents",
        type_="foreignkey"
    )

    # Make file_id non-nullable again
    op.alter_column(
        "rag_file_documents",
        "file_id",
        nullable=False,
    )

    # Re-create with CASCADE on delete
    op.create_foreign_key(
        "rag_file_documents_file_id_fkey",
        "rag_file_documents",
        "rag_files",
        ["file_id"],
        ["id"],
        ondelete="CASCADE"
    )

