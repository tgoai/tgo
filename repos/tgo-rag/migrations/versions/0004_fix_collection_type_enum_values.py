"""Fix collection_type enum values to use lowercase.

Revision ID: rag_0004_fix_enum
Revises: rag_0003_collection_type
Create Date: 2024-01-02 00:00:00.000000

This migration fixes the enum values from uppercase (FILE, WEBSITE, QA)
to lowercase (file, website, qa) to match the Python enum definition.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "rag_0004_fix_enum"
down_revision = "rag_0003_collection_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Fix collection_type enum values to lowercase."""
    
    # Step 1: Remove the default constraint temporarily
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type DROP DEFAULT")
    
    # Step 2: Convert the column to text temporarily
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type TYPE text")
    
    # Step 3: Drop the old enum type
    op.execute("DROP TYPE IF EXISTS collection_type_enum")
    
    # Step 4: Create new enum with lowercase values
    op.execute("CREATE TYPE collection_type_enum AS ENUM ('file', 'website', 'qa')")
    
    # Step 5: Update any existing data (convert uppercase to lowercase if needed)
    op.execute("UPDATE rag_collections SET collection_type = LOWER(collection_type) WHERE collection_type IS NOT NULL")
    
    # Step 6: Convert the column back to enum type
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type TYPE collection_type_enum USING collection_type::collection_type_enum")
    
    # Step 7: Restore the default
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type SET DEFAULT 'file'")


def downgrade() -> None:
    """Revert to uppercase enum values."""
    
    # Step 1: Remove the default constraint temporarily
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type DROP DEFAULT")
    
    # Step 2: Convert the column to text temporarily
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type TYPE text")
    
    # Step 3: Drop the lowercase enum type
    op.execute("DROP TYPE IF EXISTS collection_type_enum")
    
    # Step 4: Create enum with uppercase values
    op.execute("CREATE TYPE collection_type_enum AS ENUM ('FILE', 'WEBSITE', 'QA')")
    
    # Step 5: Update data to uppercase
    op.execute("UPDATE rag_collections SET collection_type = UPPER(collection_type) WHERE collection_type IS NOT NULL")
    
    # Step 6: Convert the column back to enum type
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type TYPE collection_type_enum USING collection_type::collection_type_enum")
    
    # Step 7: Restore the default (uppercase)
    op.execute("ALTER TABLE rag_collections ALTER COLUMN collection_type SET DEFAULT 'FILE'")

