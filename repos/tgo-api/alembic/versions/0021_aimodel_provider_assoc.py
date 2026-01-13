"""associate aimodel with aiprovider and migrate available_models

Revision ID: 0021_aimodel_provider_assoc
Revises: 0020_rename_toolstore_to_store
Create Date: 2026-01-13

"""
from typing import Sequence, Union
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision: str = '0021_aimodel_provider_assoc'
down_revision: Union[str, None] = '0020_rename_toolstore_to_store'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add provider_id column to api_ai_models
    op.add_column('api_ai_models', sa.Column('provider_id', sa.UUID(), sa.ForeignKey('api_ai_providers.id', ondelete='CASCADE'), nullable=True))
    
    # 2. Drop unique constraint on (provider, model_id)
    # The constraint name from ai_model.py is 'uq_ai_models_provider_model_id'
    # We use try-except or just assume it exists
    try:
        op.drop_constraint('uq_ai_models_provider_model_id', 'api_ai_models', type_='unique')
    except Exception:
        pass
    
    # 3. Data Migration: From JSONB available_models to AIModel rows
    connection = op.get_bind()
    
    # Fetch all providers and their available_models
    providers = connection.execute(sa.text("SELECT id, provider, available_models FROM api_ai_providers")).fetchall()
    
    for provider_id, provider_kind, available_models_json in providers:
        if not available_models_json:
            continue
        
        available_models = available_models_json if isinstance(available_models_json, list) else []
        
        for model_id in available_models:
            # Fetch global metadata if exists to copy info
            global_model = connection.execute(
                sa.text("SELECT model_name, model_type, description, capabilities, context_window, max_tokens, is_active FROM api_ai_models WHERE model_id = :mid AND provider = :pkind AND provider_id IS NULL LIMIT 1"),
                {"mid": model_id, "pkind": provider_kind}
            ).fetchone()
            
            if global_model:
                # Copy from global
                connection.execute(
                    sa.text("""
                        INSERT INTO api_ai_models (id, provider, model_id, model_name, model_type, description, capabilities, context_window, max_tokens, is_active, provider_id, created_at, updated_at)
                        VALUES (:id, :p, :mid, :mname, :mtype, :desc, :cap, :cwin, :mtok, :active, :pid, NOW(), NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "p": provider_kind,
                        "mid": model_id,
                        "mname": global_model.model_name,
                        "mtype": global_model.model_type,
                        "desc": global_model.description,
                        "cap": json.dumps(global_model.capabilities) if global_model.capabilities else None,
                        "cwin": global_model.context_window,
                        "mtok": global_model.max_tokens,
                        "active": global_model.is_active,
                        "pid": provider_id
                    }
                )
            else:
                # Create a minimal record
                connection.execute(
                    sa.text("""
                        INSERT INTO api_ai_models (id, provider, model_id, model_name, model_type, is_active, provider_id, created_at, updated_at)
                        VALUES (:id, :p, :mid, :mname, :mtype, true, :pid, NOW(), NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "p": provider_kind,
                        "mid": model_id,
                        "mname": model_id,
                        "mtype": "chat",
                        "pid": provider_id
                    }
                )

    # 4. Drop available_models column from api_ai_providers
    op.drop_column('api_ai_providers', 'available_models')


def downgrade() -> None:
    # 1. Add back available_models column
    op.add_column('api_ai_providers', sa.Column('available_models', postgresql.JSONB(), nullable=False, server_default='[]'))
    
    # 2. Migrate data back
    connection = op.get_bind()
    models = connection.execute(sa.text("SELECT provider_id, model_id FROM api_ai_models WHERE provider_id IS NOT NULL")).fetchall()
    
    # We need to collect models per provider
    provider_models = {}
    for pid, mid in models:
        if pid not in provider_models:
            provider_models[pid] = []
        if mid not in provider_models[pid]:
            provider_models[pid].append(mid)
    
    for pid, mids in provider_models.items():
        connection.execute(
            sa.text("UPDATE api_ai_providers SET available_models = :mids WHERE id = :pid"),
            {"mids": json.dumps(mids), "pid": pid}
        )
    
    # 3. Add back unique constraint
    try:
        op.create_unique_constraint('uq_ai_models_provider_model_id', 'api_ai_models', ['provider', 'model_id'])
    except Exception:
        pass
    
    # 4. Delete the local AIModel records
    connection.execute(sa.text("DELETE FROM api_ai_models WHERE provider_id IS NOT NULL"))
    
    # 5. Remove provider_id column
    op.drop_column('api_ai_models', 'provider_id')
