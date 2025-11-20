"""
Development utilities for the RAG service.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_db_session
from .logging_config import get_logger
from .models.projects import Project

logger = get_logger(__name__)



def is_development_environment() -> bool:
    """
    Check if the current environment is development.
    
    Returns:
        True if the environment is set to "development"
    """
    settings = get_settings()
    return settings.environment.lower() == "development"


