"""Tests for health check endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Note: These tests require the app to be importable
# In a real setup, you would mock the database connection


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_check_database_success(self):
        """Test database health check success."""
        from app.api.v1.health import check_database

        with patch("app.api.v1.health.SessionLocal") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_instance.execute = AsyncMock()
            mock_session.return_value = mock_session_instance

            result = await check_database()

            assert result.name == "postgresql"
            assert result.status == "healthy"
            assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_check_database_failure(self):
        """Test database health check failure."""
        from app.api.v1.health import check_database

        with patch("app.api.v1.health.SessionLocal") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            mock_session_instance.execute = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_session.return_value = mock_session_instance

            result = await check_database()

            assert result.name == "postgresql"
            assert result.status == "unhealthy"
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_check_tgo_api_success(self):
        """Test TGO API health check success."""
        from app.api.v1.health import check_tgo_api

        with patch("app.api.v1.health.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_client_instance

            result = await check_tgo_api()

            assert result.name == "tgo-api"
            assert result.status == "healthy"

    @pytest.mark.asyncio
    async def test_check_tgo_api_failure(self):
        """Test TGO API health check failure."""
        from app.api.v1.health import check_tgo_api

        with patch("app.api.v1.health.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get = AsyncMock(
                side_effect=Exception("Connection refused")
            )
            mock_client.return_value = mock_client_instance

            result = await check_tgo_api()

            assert result.name == "tgo-api"
            assert result.status == "unhealthy"
            assert result.error is not None
