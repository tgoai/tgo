from typing import List, Union
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.utils.crypto import decrypt_str
from app.models.store_credential import StoreCredential
from app.services.store_client import store_client

logger = get_logger("store_sync")

async def sync_uninstall_models_to_store(
    db: Session,
    project_id: Union[str, UUID],
    store_resource_ids: List[str]
) -> None:
    """
    Asynchronously notify Store API to uninstall models.
    This is intended to be used with FastAPI BackgroundTasks.
    """
    if not store_resource_ids:
        return

    # 1. Get project store credentials
    credential = db.scalar(
        select(StoreCredential).where(StoreCredential.project_id == project_id)
    )
    if not credential:
        logger.warning(f"Project {project_id} not bound to Store, skipping uninstall sync")
        return

    api_key = decrypt_str(credential.api_key_encrypted)
    if not api_key:
        logger.error(f"Failed to decrypt API Key for project {project_id}")
        return

    # 2. Call Store API for each model
    for resource_id in store_resource_ids:
        try:
            logger.info(f"Syncing uninstall to Store: project={project_id}, resource={resource_id}")
            await store_client.uninstall_model(resource_id, api_key)
        except Exception as e:
            logger.error(f"Failed to sync uninstall to Store for {resource_id}: {str(e)}")

async def sync_uninstall_all_provider_models(
    db: Session,
    project_id: Union[str, UUID],
    provider_id: UUID
) -> None:
    """
    Fetch all models for a provider that have a store_resource_id and uninstall them.
    """
    from app.models.ai_model import AIModel
    
    # Get models with store_resource_id
    models = db.scalars(
        select(AIModel).where(
            AIModel.provider_id == provider_id,
            AIModel.store_resource_id.is_not(None),
            AIModel.deleted_at.is_(None)
        )
    ).all()
    
    resource_ids = [m.store_resource_id for m in models]
    if resource_ids:
        await sync_uninstall_models_to_store(db, project_id, resource_ids)
