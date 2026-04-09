"""Pytest configuration and fixtures."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.dependencies import get_agent_service
from app.main import app
from app.models.base import BaseModel
from app.models.project import Project
from app.services.agent_service import AgentService

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

# Create test session factory
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)

    # Create session
    async with TestSessionLocal() as session:
        yield session

    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        id=uuid.uuid4(),
        name="Test Project",
        api_key="ak_test_1234567890abcdef",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
def client(db_session: AsyncSession) -> TestClient:
    """Create a test client with database dependency override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_get_agent_service() -> AgentService:
        return AgentService(db_session)

    # Override the lifespan to skip database initialization
    @asynccontextmanager
    async def test_lifespan(app):
        # Skip database initialization in tests
        yield

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_service] = override_get_agent_service

    # Temporarily replace the lifespan
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = test_lifespan

    with TestClient(app) as test_client:
        yield test_client

    # Restore original lifespan
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()

