"""Tests for WuKongIM payload normalization."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.wukongim_client import WuKongIMClient


class WuKongIMClientTests(unittest.IsolatedAsyncioTestCase):
    """Regression tests for WuKongIM history payload decoding."""

    async def test_sync_channel_messages_decodes_double_encoded_payload(
        self,
    ) -> None:
        """History sync should normalize SDK-style double-encoded payloads."""

        client = WuKongIMClient()
        client._make_request = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "start_message_seq": 0,
                "end_message_seq": 0,
                "more": 0,
                "messages": [
                    {
                        "header": {
                            "no_persist": 0,
                            "red_dot": 0,
                            "sync_once": 0,
                        },
                        "setting": 0,
                        "message_id": 1,
                        "client_msg_no": "msg-1",
                        "message_seq": 1,
                        "from_uid": "visitor-1-vtr",
                        "channel_id": "visitor-1-vtr",
                        "channel_type": 251,
                        "timestamp": 1777018628,
                        "payload": (
                            "ImV5SjBlWEJsSWpveExDSmpiMjUwWlc1MElqb2k1"
                            "TDJnNWFXOUluMD0i"
                        ),
                    }
                ],
            }
        )

        result = await client.sync_channel_messages(
            login_uid="visitor-1",
            channel_id="visitor-1-vtr",
            channel_type=251,
            include_event_meta=1,
            event_summary_mode="full",
        )

        self.assertEqual(
            result.messages[0].payload,
            {"type": 1, "content": "你好"},
        )

    async def test_send_event_uses_event_type_as_command_name(self) -> None:
        """Legacy custom events should use the event type as the command."""

        client = WuKongIMClient()
        send_result = SimpleNamespace(message_id=1, client_msg_no="profile-1")
        client.send_message = AsyncMock(  # type: ignore[method-assign]
            return_value=send_result,
        )

        result = await client.send_event(
            channel_id="visitor-1-vtr",
            channel_type=251,
            event_type="visitor.profile.updated",
            data={"visitor_id": "visitor-1"},
            client_msg_no="profile-1",
            force=False,
        )

        self.assertIs(result, send_result)
        client.send_message.assert_awaited_once_with(
            payload={
                "type": 99,
                "cmd": "visitor.profile.updated",
                "param": {"visitor_id": "visitor-1"},
            },
            from_uid=None,
            channel_id="visitor-1-vtr",
            channel_type=251,
            client_msg_no="profile-1",
            no_persist=True,
            red_dot=False,
            sync_once=True,
        )
