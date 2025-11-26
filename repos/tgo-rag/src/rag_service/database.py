"""
Database connection and session management.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from .config import get_settings
from .models import Base

logger = logging.getLogger(__name__)

# Global variables for database engine and session factory
engine = None
async_session_factory = None


def reset_db_state():
    """
    Reset the global database engine and session factory.
    
    This function MUST be called before creating a new asyncio event loop
    in Celery workers to avoid 'Future attached to a different loop' errors.
    
    The issue occurs because:
    1. SQLAlchemy async engine/connections are bound to a specific event loop
    2. When Celery tasks create new event loops, old connections are still bound
       to the previous (closed) event loop
    3. This causes 'Event loop is closed' or 'attached to a different loop' errors
    
    Call this function in:
    - Celery worker_process_init signal handler
    - Before creating a new event loop in any Celery task
    """
    global engine, async_session_factory
    
    # Dispose of old engine if it exists (cleanup connections)
    if engine is not None:
        try:
            # Note: We can't await dispose() here since we may not have an event loop
            # The next task will create a fresh engine anyway
            pass
        except Exception:
            pass
    
    engine = None
    async_session_factory = None
    logger.debug("Database state reset for new event loop")


def create_database_engine():
    """Create and configure the database engine."""
    global engine
    
    settings = get_settings()
    
    # Create async engine with connection pooling
    engine_kwargs = {
        "echo": settings.debug,
        "pool_pre_ping": True,
    }

    # Use NullPool for development/test to avoid connection issues
    if settings.environment in ("development", "test"):
        engine_kwargs["poolclass"] = NullPool
    else:
        # Only add pool settings when not using NullPool
        engine_kwargs.update({
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
        })

    engine = create_async_engine(settings.database_url, **engine_kwargs)
    
    logger.info(f"Database engine created for {settings.environment} environment")
    return engine


def create_session_factory():
    """Create the async session factory."""
    global async_session_factory, engine
    
    if engine is None:
        engine = create_database_engine()
    
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
        autocommit=False,
    )
    
    logger.info("Async session factory created")
    return async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.
    
    This is the main way to get a database session for use in the application.
    It ensures proper cleanup and error handling.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        async with get_db_session() as session:
            result = await session.execute(select(Project))
            projects = result.scalars().all()
    """
    global async_session_factory
    
    if async_session_factory is None:
        async_session_factory = create_session_factory()
    
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def get_db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database sessions.
    
    This function is used as a FastAPI dependency to inject database sessions
    into route handlers.
    
    Yields:
        AsyncSession: Database session
    """
    async with get_db_session() as session:
        yield session


async def init_database():
    """
    Initialize the database by creating all tables.
    
    This function should be called during application startup to ensure
    all database tables are created.
    """
    global engine
    
    if engine is None:
        engine = create_database_engine()
    
    try:
        async with engine.begin() as conn:
            # If Alembic is managing the schema (version table exists), skip create_all
            result = await conn.execute(text("SELECT to_regclass('public.rag_alembic_version')"))
            version_table = result.scalar()
            if version_table:
                logger.info("Alembic version table detected; skipping Base.metadata.create_all")
            else:
                # Bootstrap schema in environments without Alembic
                await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_database():
    """
    Close the database engine and clean up connections.
    
    This function should be called during application shutdown to ensure
    proper cleanup of database connections.
    """
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database engine disposed")


async def check_database_connection() -> bool:
    """
    Check if the database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        async with get_db_session() as session:
            # Simple query to test connection
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


# Utility functions for common database operations

async def create_tables():
    """Create all database tables."""
    await init_database()


async def drop_tables():
    """Drop all database tables (use with caution!)."""
    global engine
    
    if engine is None:
        engine = create_database_engine()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.warning("All database tables dropped")


async def reset_database():
    """Reset the database by dropping and recreating all tables."""
    await drop_tables()
    await create_tables()
    logger.info("Database reset completed")


# Database health check for monitoring
async def database_health_check() -> dict:
    """
    Perform a comprehensive database health check.
    
    Returns:
        dict: Health check results with status and metrics
    """
    health_info = {
        "status": "unhealthy",
        "connection": False,
        "tables_exist": False,
        "error": None,
    }
    
    try:
        # Check basic connection
        connection_ok = await check_database_connection()
        health_info["connection"] = connection_ok
        
        if connection_ok:
            # Check if tables exist
            async with get_db_session() as session:
                # Try to query one of our main tables
                result = await session.execute(text("SELECT COUNT(*) FROM rag_projects"))
                result.scalar()
                health_info["tables_exist"] = True
                health_info["status"] = "healthy"
        
    except Exception as e:
        health_info["error"] = str(e)
        logger.error(f"Database health check failed: {e}")
    
    return health_info
