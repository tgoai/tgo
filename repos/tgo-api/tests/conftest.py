"""Shared test fixtures for API endpoint coverage."""

from __future__ import annotations

import os
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from uuid import uuid4

import anyio
import httpx
import pytest

os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-key-for-pytest-only-1234567890",
)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/tgo_api_test",
)

from app.core.database import get_db
from app.core.security import get_authenticated_project
from app.main import app
from app.models.project import Project


class SyncASGIClient:
    """Small sync wrapper around httpx.AsyncClient for ASGI app tests."""

    def __init__(self, app_instance: object) -> None:
        self._client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_instance),
            base_url="http://testserver",
        )

    def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        async def _request() -> httpx.Response:
            return await self._client.request(method, url, **kwargs)

        return anyio.run(_request)

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: object) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def close(self) -> None:
        anyio.run(self._client.aclose)


class _UnsetDBSession:
    """Raise a clear error when a test forgets to provide a DB session."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(
            f"db_override.session must be configured before accessing '{name}'"
        )


@dataclass
class DBOverride:
    """Mutable holder for per-test DB session overrides."""

    session: object | None = None


@pytest.fixture
def authenticated_project() -> Project:
    """Return a lightweight authenticated project for dependency overrides."""

    return Project(
        id=uuid4(),
        name="Test Project",
        api_key="ak_test_downstream_api_key",
    )


@pytest.fixture
def db_override() -> DBOverride:
    """Expose a mutable DB session hook for endpoint tests."""

    return DBOverride()


@pytest.fixture
def client(
    authenticated_project: Project,
    db_override: DBOverride,
) -> Iterator[SyncASGIClient]:
    """Build a test client with auth and DB dependencies overridden."""

    async def override_authenticated_project() -> tuple[Project, str]:
        return authenticated_project, authenticated_project.api_key

    def override_get_db() -> Generator[object, None, None]:
        session = db_override.session
        yield session if session is not None else _UnsetDBSession()

    app.dependency_overrides[get_authenticated_project] = (
        override_authenticated_project
    )
    app.dependency_overrides[get_db] = override_get_db

    test_client = SyncASGIClient(app)
    yield test_client
    test_client.close()

    app.dependency_overrides.clear()
