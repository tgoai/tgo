"""Regression tests for internal AI event ingestion."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.api.internal.endpoints import ai_events
from app.schemas.ai import AIServiceEvent


class _FakeQuery:
    def __init__(self, result: object) -> None:
        self._result = result

    def filter(self, *_args: object, **_kwargs: object) -> _FakeQuery:
        return self

    def first(self) -> object:
        return self._result


class _FakeDB:
    def __init__(self, visitor: object, project: object) -> None:
        self._results = {
            ai_events.Visitor: visitor,
            ai_events.Project: project,
        }

    def query(self, model: object) -> _FakeQuery:
        return _FakeQuery(self._results[model])


class InternalAIEventsTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_ai_event_normalizes_user_id_to_string(
        self,
    ) -> None:
        """Internal ingestion should keep the canonical user_id as a string."""
        visitor_id = uuid4()
        project_id = uuid4()
        visitor = SimpleNamespace(
            id=visitor_id,
            project_id=project_id,
            deleted_at=None,
        )
        project = SimpleNamespace(id=project_id, deleted_at=None)
        db = _FakeDB(visitor=visitor, project=project)
        event = AIServiceEvent(
            event_type="user_info.update",
            user_id=str(visitor_id),
            payload={},
        )

        handler = AsyncMock(return_value={"ok": True})
        with patch.object(ai_events, "_handle_visitor_info_update", handler):
            result = await ai_events.ingest_ai_event_internal(
                event=event,
                db=db,
            )

        self.assertEqual(
            result,
            {"event_type": "user_info.update", "result": {"ok": True}},
        )
        self.assertEqual(event.user_id, str(visitor_id))
        self.assertEqual(handler.await_args.args[0].user_id, str(visitor_id))
