"""Tests for API exception handlers."""

from __future__ import annotations

import json
import unittest
from uuid import uuid4

from fastapi import Request
from pydantic import BaseModel, ValidationError as PydanticValidationError

from app.core.exceptions import validation_exception_handler


class _ValidationPayload(BaseModel):
    user_id: str


class ExceptionHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_exception_handler_serializes_uuid_inputs(
        self,
    ) -> None:
        """Validation responses should stay JSON-serializable."""
        invalid_user_id = uuid4()

        try:
            _ValidationPayload(user_id=invalid_user_id)
        except PydanticValidationError as exc:
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/internal/ai/events",
                    "headers": [],
                    "query_string": b"",
                    "client": ("testclient", 123),
                    "server": ("testserver", 80),
                    "scheme": "http",
                    "root_path": "",
                    "http_version": "1.1",
                }
            )
            response = await validation_exception_handler(request, exc)
        else:
            self.fail("Expected a validation error for UUID input")

        body = json.loads(response.body)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            body["error"]["details"]["errors"][0]["input"],
            str(invalid_user_id),
        )
