from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from typing import Any
import unittest
from unittest.mock import patch

import httpx

from app.config import settings

_BASE_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "runtime" / "tools" / "custom" / "base.py"
)
_BASE_MODULE_SPEC = spec_from_file_location(
    "test_custom_tool_base_module",
    _BASE_MODULE_PATH,
)
assert _BASE_MODULE_SPEC is not None
assert _BASE_MODULE_SPEC.loader is not None
_BASE_MODULE = module_from_spec(_BASE_MODULE_SPEC)
sys.modules[_BASE_MODULE_SPEC.name] = _BASE_MODULE
_BASE_MODULE_SPEC.loader.exec_module(_BASE_MODULE)

EventClient = _BASE_MODULE.EventClient
ToolContext = _BASE_MODULE.ToolContext


class _DummyResponse:
    status_code = 200
    text = ""

    def json(self) -> dict[str, Any]:
        return {}


class _DummyAsyncClient:
    def __init__(self, captured: dict[str, Any], *args: Any, **kwargs: Any) -> None:
        self.captured = captured

    async def __aenter__(self) -> _DummyAsyncClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> _DummyResponse:
        self.captured["url"] = url
        self.captured["json"] = json
        self.captured["headers"] = headers
        return _DummyResponse()


class EventClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_event_uses_configured_internal_api_url(self) -> None:
        captured: dict[str, Any] = {}
        original_internal_url = settings.api_internal_service_url
        original_api_service_url = settings.api_service_url
        settings.api_internal_service_url = "http://tgo-api:8001"
        settings.api_service_url = "http://tgo-api:8000"
        self.addCleanup(
            setattr,
            settings,
            "api_internal_service_url",
            original_internal_url,
        )
        self.addCleanup(
            setattr,
            settings,
            "api_service_url",
            original_api_service_url,
        )

        client = EventClient(
            ToolContext(
                agent_id="agent-1",
                session_id="session-1",
                user_id="visitor-1",
                project_id="project-1",
            )
        )

        with patch.object(
            httpx,
            "AsyncClient",
            lambda *args, **kwargs: _DummyAsyncClient(captured, *args, **kwargs),
        ):
            result = await client.post_event(
                "user_sentiment.update",
                {"sentiment": {"satisfaction": 5}},
                error_messages={
                    "not_configured": "not_configured",
                    "api_error": "api_error",
                    "http_error": "http_error",
                    "unexpected_error": "unexpected_error",
                },
            )

        self.assertTrue(result.success)
        self.assertEqual(
            captured["url"],
            "http://tgo-api:8001/internal/ai/events",
        )
