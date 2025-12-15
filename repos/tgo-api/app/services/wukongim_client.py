"""WuKongIM client for instant messaging integration."""

import base64
import binascii
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.wukongim import (
    WuKongIMRouteResponse,
    WuKongIMMessageSendResponse,
    WuKongIMChannelLastMessage,
    WuKongIMConversation,
    WuKongIMChannelMessageSyncResponse,
    WuKongIMMessage,
    WuKongIMSearchMessagesResponse,
    WuKongIMSearchResult,
)

logger = logging.getLogger(__name__)


class MessageType:
    """WuKongIM message type constants.
    
    Standard message types (1-999):
        - TEXT (1): Plain text message
    
    System message types (1000-2000):
        - STAFF_ASSIGNED (1000): Staff assigned to visitor notification
        - SESSION_CLOSED (1001): Session closed notification
        - SESSION_TRANSFERRED (1002): Session transferred notification
    """
    # Standard message types
    TEXT = 1
    
    # System message types (1000-2000 reserved for system notifications)
    STAFF_ASSIGNED = 1000
    SESSION_CLOSED = 1001
    SESSION_TRANSFERRED = 1002


class EventType:
    """WuKongIM event type constants.
    
    Event types for real-time notifications:
        - VISITOR_PROFILE_UPDATED: Visitor profile has been updated
        - QUEUE_UPDATED: Waiting queue has been updated (new visitor waiting)
    """
    VISITOR_PROFILE_UPDATED = "visitor.profile.updated"
    QUEUE_UPDATED = "queue.updated"


class WuKongIMClient:
    """Client for WuKongIM instant messaging service."""

    def __init__(self):
        """Initialize WuKongIM client."""
        self.base_url = settings.WUKONGIM_SERVICE_URL.rstrip("/")
        self.timeout = settings.WUKONGIM_SERVICE_TIMEOUT
        self.enabled = settings.WUKONGIM_ENABLED

    def _decode_message_payload(self, payload: str) -> Dict[str, Any]:
        """
        Decode base64-encoded message payload to JSON object.

        Args:
            payload: Base64-encoded message content

        Returns:
            Decoded JSON object or fallback structure
        """
        try:
            # Decode base64 string
            decoded_bytes = base64.b64decode(payload)
            decoded_str = decoded_bytes.decode('utf-8')

            # Parse JSON
            json_payload = json.loads(decoded_str)

            logger.debug(f"Successfully decoded message payload")
            return json_payload

        except (binascii.Error, UnicodeDecodeError) as e:
            logger.warning(f"Failed to decode base64 payload: {e}")
            # Return original payload in a structured format
            return {"raw_payload": payload, "decode_error": "base64_decode_failed"}

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from decoded payload: {e}")
            # Return decoded string in a structured format
            try:
                decoded_str = base64.b64decode(payload).decode('utf-8')
                return {"raw_content": decoded_str, "decode_error": "json_parse_failed"}
            except Exception:
                return {"raw_payload": payload, "decode_error": "complete_decode_failed"}

        except Exception as e:
            logger.error(f"Unexpected error decoding payload: {e}")
            return {"raw_payload": payload, "decode_error": "unexpected_error"}

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to WuKongIM service."""
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled, skipping request")
            return {}

        url = f"{self.base_url}{endpoint}"

        logger.debug(f"WuKongIM request: {method} {url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                )

                logger.debug(f"WuKongIM response: {response.status_code}")

                # WuKongIM API returns 200 for success, other codes for errors
                if response.status_code == 200:
                    # Some endpoints return empty response body on success
                    try:
                        return response.json() if response.text else {}
                    except Exception:
                        return {}
                else:
                    # Handle error responses
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("msg", f"WuKongIM error: {response.status_code}")
                    except Exception:
                        error_msg = f"WuKongIM HTTP error: {response.status_code}"

                    logger.error(f"WuKongIM error response: {response.status_code} - {error_msg}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"WuKongIM service error: {error_msg}"
                    )

        except httpx.TimeoutException:
            logger.error(f"WuKongIM request timeout: {method} {url}")
            raise HTTPException(
                status_code=500,
                detail="WuKongIM service timeout"
            )
        except httpx.RequestError as e:
            logger.error(f"WuKongIM request error: {e}")
            raise HTTPException(
                status_code=500,
                detail="WuKongIM service unavailable"
            )

    async def send_event(
        self,
        *,
        channel_id: str,
        channel_type: int,
        event_type: str,
        data: Any,
        client_msg_no: Optional[str] = None,
        from_uid: Optional[str] = None,
        force: bool = True,
    ) -> Dict[str, Any]:
        """Send a custom event through WuKongIM (streaming/text or custom)."""
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_event")
            return {}

        if isinstance(data, (dict, list)):
            serialized_data = json.dumps(data, ensure_ascii=False)
        elif data is None:
            serialized_data = ""
        else:
            serialized_data = str(data)

        request_data: Dict[str, Any] = {
            "channel_id": channel_id,
            "channel_type": channel_type,
            "event": {
                "id": client_msg_no,
                "type": event_type,
                "data": serialized_data,
                "timestamp": int(datetime.now().timestamp()),
            },
        }

        if client_msg_no:
            request_data["client_msg_no"] = client_msg_no
        if from_uid:
            request_data["from_uid"] = from_uid

        logger.debug(
            "Sending WuKongIM event",
            extra={
                "from_uid": from_uid,
                "channel_id": channel_id,
                "event_type": event_type,
            },
        )

        params = {
            "force": "1" if force else "0",
        }

        return await self._make_request(
            method="POST",
            endpoint="/event",
            json_data=request_data,
            params=params,
        )


    async def send_message(
        self,
        *,
        payload: Dict[str, Any],
        from_uid: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_type: Optional[int] = None,
        client_msg_no: Optional[str] = None,
        subscribers: Optional[List[str]] = None,
        no_persist: bool = False,
        red_dot: bool = True,
        sync_once: bool = False,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a message through WuKongIM (/message/send API).

        This is a low-level method that directly maps to WuKongIM's /message/send API.
        For sending text messages, consider using send_text_message() instead.

        Args:
            payload: Message payload dict (will be JSON encoded and base64 encoded internally)
            from_uid: Sender UID
            channel_id: Channel ID
            channel_type: Channel type (1=personal, 2=group, 251=customer_service)
            client_msg_no: Client-provided message ID for correlation
            subscribers: Specific subscribers to send message to
            no_persist: Whether message should not be persisted (default False = persist)
            red_dot: Whether to show red dot notification (default True = show)
            sync_once: Whether message should be synced only once (default False = normal sync)

        Returns:
            Response with message_id, message_seq, client_msg_no
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_message")
            return None

        # Encode payload to base64
        payload_encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

        request_data: Dict[str, Any] = {
            "payload": payload_encoded,
        }

        # Add optional parameters if provided
        if from_uid is not None:
            request_data["from_uid"] = from_uid
        if channel_id is not None:
            request_data["channel_id"] = channel_id
        if channel_type is not None:
            request_data["channel_type"] = channel_type
        if client_msg_no is not None:
            request_data["client_msg_no"] = client_msg_no
        if subscribers is not None:
            request_data["subscribers"] = subscribers

        # Build header if any non-default values
        header: Dict[str, int] = {}
        if no_persist:
            header["no_persist"] = 1
        if not red_dot:
            header["red_dot"] = 0
        if sync_once:
            header["sync_once"] = 1
        if header:
            request_data["header"] = header

        logger.info(
            "Sending WuKongIM message",
            extra={
                "from_uid": from_uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
                "client_msg_no": client_msg_no,
                "has_subscribers": subscribers is not None,
            }
        )

        result = await self._make_request(
            method="POST",
            endpoint="/message/send",
            json_data=request_data,
        )
        logger.debug("WuKongIM send_message result: %s", result)
        # WuKongIM API returns {"data": {...}, "status": 200}, extract data field
        if result and "data" in result:
            return WuKongIMMessageSendResponse(**result["data"])
        return None

    async def send_text_message(
        self,
        *,
        from_uid: str,
        channel_id: str,
        channel_type: int,
        content: str,
        extra: Optional[Dict[str, Any]] = None,
        client_msg_no: Optional[str] = None,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a plain text message through WuKongIM.

        This is a convenience method for sending text messages.
        For more control, use send_message() directly.

        Args:
            from_uid: Sender UID
            channel_id: Channel ID
            channel_type: Channel type (1=personal, 2=group, 251=customer_service)
            content: Message text content
            extra: Optional extra JSON data to include in payload
            client_msg_no: Optional client-provided id to correlate webhook callbacks

        Returns:
            WuKongIMMessageSendResponse with message_id, message_seq, client_msg_no
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_text_message")
            return None

        # Build payload for text message
        payload: Dict[str, Any] = {
            "type": MessageType.TEXT,
            "content": content,
        }
        if extra:
            payload["extra"] = extra

        return await self.send_message(
            payload=payload,
            from_uid=from_uid,
            channel_id=channel_id,
            channel_type=channel_type,
            client_msg_no=client_msg_no or str(uuid4()),
        )

    async def send_staff_assigned_message(
        self,
        *,
        from_uid: str,
        channel_id: str,
        channel_type: int,
        staff_uid: str,
        staff_name: str,
        client_msg_no: Optional[str] = None,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a system message when a staff member is assigned to a visitor.

        System message types are defined in range 1000-2000.
        Type 1000: Staff assigned notification.

        Args:
            from_uid: Sender UID (typically system or staff UID)
            channel_id: Channel ID
            channel_type: Channel type (251=customer_service)
            staff_uid: The assigned staff's UID
            staff_name: The assigned staff's display name
            client_msg_no: Optional client-provided id to correlate webhook callbacks

        Returns:
            Response with message_id, message_seq, client_msg_no
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_staff_assigned_message")
            return None

        # System message: Staff assigned
        payload: Dict[str, Any] = {
            "type": MessageType.STAFF_ASSIGNED,
            "content": "You have been connected to customer service. Agent {0} will assist you.",
            "extra": [
                {"uid": staff_uid, "name": staff_name},
            ],
        }

        logger.info(
            "Sending staff assigned system message",
            extra={
                "from_uid": from_uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
                "staff_uid": staff_uid,
                "staff_name": staff_name,
            }
        )

        return await self.send_message(
            payload=payload,
            from_uid=from_uid,
            channel_id=channel_id,
            channel_type=channel_type,
            client_msg_no=client_msg_no or str(uuid4()),
        )

    async def send_session_closed_message(
        self,
        *,
        from_uid: str,
        channel_id: str,
        channel_type: int,
        staff_uid: Optional[str] = None,
        staff_name: Optional[str] = None,
        client_msg_no: Optional[str] = None,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a system message when a session is closed.

        System message types are defined in range 1000-2000.
        Type 1001: Session closed notification.

        Args:
            from_uid: Sender UID (typically system or staff UID)
            channel_id: Channel ID
            channel_type: Channel type (251=customer_service)
            staff_uid: The staff's UID who closed the session (optional)
            staff_name: The staff's display name (optional)
            client_msg_no: Optional client-provided id to correlate webhook callbacks

        Returns:
            WuKongIMMessageSendResponse with message_id, message_seq, client_msg_no
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_session_closed_message")
            return None

        # System message: Session closed
        if staff_uid and staff_name:
            payload: Dict[str, Any] = {
                "type": MessageType.SESSION_CLOSED,
                "content": "Session ended. Agent {0} has completed the service.",
                "extra": [
                    {"uid": staff_uid, "name": staff_name},
                ],
            }
        else:
            payload = {
                "type": MessageType.SESSION_CLOSED,
                "content": "Session ended.",
                "extra": [],
            }

        logger.info(
            "Sending session closed system message",
            extra={
                "from_uid": from_uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
                "staff_uid": staff_uid,
                "staff_name": staff_name,
            }
        )

        return await self.send_message(
            payload=payload,
            from_uid=from_uid,
            channel_id=channel_id,
            channel_type=channel_type,
            client_msg_no=client_msg_no or str(uuid4()),
        )

    async def send_session_transferred_message(
        self,
        *,
        from_uid: str,
        channel_id: str,
        channel_type: int,
        from_staff_uid: str,
        from_staff_name: str,
        to_staff_uid: str,
        to_staff_name: str,
        client_msg_no: Optional[str] = None,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a system message when a session is transferred to another staff.

        System message types are defined in range 1000-2000.
        Type 1002: Session transferred notification.

        Args:
            from_uid: Sender UID (typically system or staff UID)
            channel_id: Channel ID
            channel_type: Channel type (251=customer_service)
            from_staff_uid: The original staff's UID
            from_staff_name: The original staff's display name
            to_staff_uid: The new staff's UID
            to_staff_name: The new staff's display name
            client_msg_no: Optional client-provided id to correlate webhook callbacks

        Returns:
            WuKongIMMessageSendResponse with message_id, client_msg_no
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_session_transferred_message")
            return None

        # System message: Session transferred
        payload: Dict[str, Any] = {
            "type": MessageType.SESSION_TRANSFERRED,
            "content": "Session transferred. Agent {0} has transferred you to Agent {1}.",
            "extra": [
                {"uid": from_staff_uid, "name": from_staff_name},
                {"uid": to_staff_uid, "name": to_staff_name},
            ],
        }

        logger.info(
            "Sending session transferred system message",
            extra={
                "from_uid": from_uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
                "from_staff_uid": from_staff_uid,
                "from_staff_name": from_staff_name,
                "to_staff_uid": to_staff_uid,
                "to_staff_name": to_staff_name,
            }
        )

        return await self.send_message(
            payload=payload,
            from_uid=from_uid,
            channel_id=channel_id,
            channel_type=channel_type,
            client_msg_no=client_msg_no or str(uuid4()),
        )

    async def send_visitor_profile_updated(
        self,
        *,
        visitor_id: str,
        channel_id: str,
        channel_type: int,
        client_msg_no: Optional[str] = None,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a visitor profile updated event.

        This event notifies all channel subscribers that the visitor's profile
        has been updated (e.g., tags, AI insights, system info changed).

        Args:
            visitor_id: The visitor's UUID string
            channel_id: Channel ID
            channel_type: Channel type (251=customer_service)
            client_msg_no: Optional client-provided id for correlation

        Returns:
            WuKongIMMessageSendResponse or None if disabled
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_visitor_profile_updated")
            return None

        event_type = EventType.VISITOR_PROFILE_UPDATED
        data = {
            "visitor_id": visitor_id,
            "channel_id": channel_id,
            "channel_type": channel_type,
        }

        logger.info(
            "Sending visitor profile updated event",
            extra={
                "visitor_id": visitor_id,
                "channel_id": channel_id,
                "channel_type": channel_type,
            }
        )

        return await self.send_event(
            client_msg_no=client_msg_no or f"profile-update-{uuid4().hex}",
            channel_id=channel_id,
            channel_type=channel_type,
            event_type=event_type,
            data=data,
            force=False,
        )

    async def send_queue_updated_event(
        self,
        *,
        channel_id: str,
        channel_type: int,
        project_id: str,
        waiting_count: int,
        client_msg_no: Optional[str] = None,
    ) -> Optional[WuKongIMMessageSendResponse]:
        """Send a waiting queue updated event to notify staff of pending visitors.

        This is sent to the project staff channel when a visitor enters the queue.

        Args:
            channel_id: Project staff channel ID (format: {project_id}-prj)
            channel_type: Channel type (249 for project staff channel)
            project_id: Project ID
            waiting_count: Current number of visitors waiting in queue
            client_msg_no: Optional client-provided id for correlation

        Returns:
            WuKongIMMessageSendResponse or None if disabled
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping send_queue_updated_event")
            return None

        event_type = EventType.QUEUE_UPDATED
        data = {
            "project_id": project_id,
            "waiting_count": waiting_count,
        }

        logger.info(
            "Sending queue updated event",
            extra={
                "channel_id": channel_id,
                "channel_type": channel_type,
                "project_id": project_id,
                "waiting_count": waiting_count,
            }
        )

        return await self.send_event(
            client_msg_no=client_msg_no or f"queue-update-{uuid4().hex}",
            channel_id=channel_id,
            channel_type=channel_type,
            event_type=event_type,
            data=data,
            force=True,
        )

    async def get_channel_last_message(
        self,
        *,
        channel_id: str,
        channel_type: int,
        login_uid: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the last message of a channel.

        Args:
            channel_id: Channel ID
            channel_type: Channel type (1=personal, 2=group, 251=customer_service)
            login_uid: Login user ID (required for personal channels, channel_type=1)

        Returns:
            Last message info or None if channel not found or no messages
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping get_channel_last_message")
            return None

        params: Dict[str, Any] = {
            "channel_id": channel_id,
            "channel_type": channel_type,
        }
        if login_uid:
            params["login_uid"] = login_uid

        logger.debug(
            "Getting channel last message",
            extra={
                "channel_id": channel_id,
                "channel_type": channel_type,
            }
        )

        try:
            response = await self._request("GET", "/channel/last_message", params=params)
            return response
        except Exception as e:
            # 404 means no messages, return None
            logger.debug(f"Failed to get channel last message: {e}")
            return None

    async def create_channel(
        self,
        *,
        channel_id: str,
        channel_type: int,
        subscribers: List[str],
    ) -> Dict[str, Any]:
        """Create or update a WuKongIM channel.

        Args:
            channel_id: The channel identifier (e.g., base64-encoded composite id)
            channel_type: Channel type (1=personal, 2=group, 3=customer_service)
            subscribers: List of subscriber UIDs to include in the channel

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping create_channel")
            return {}

        request_data: Dict[str, Any] = {
            "channel_id": channel_id,
            "channel_type": channel_type,
            "subscribers": subscribers or [],
        }

        logger.info(
            "Creating/updating WuKongIM channel",
            extra={
                "channel_id": channel_id,
                "channel_type": channel_type,
                "subscribers_count": len(subscribers or []),
            },
        )

        result = await self._make_request(
            method="POST",
            endpoint="/channel",
            json_data=request_data,
        )

        logger.debug("WuKongIM create_channel result: %s", result)
        return result

    async def add_channel_subscribers(
        self,
        *,
        channel_id: str,
        channel_type: int,
        subscribers: List[str],
        reset: bool = False,
    ) -> Dict[str, Any]:
        """Add subscribers to a WuKongIM channel.

        This method is idempotent - adding the same subscriber multiple times is safe.
        If the channel doesn't exist, it will be created automatically.

        Args:
            channel_id: The channel identifier
            channel_type: Channel type (cannot be 1/person channel)
            subscribers: List of subscriber UIDs to add
            reset: Whether to reset existing subscribers (default False)

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping add_channel_subscribers")
            return {}

        if not subscribers:
            logger.debug("No subscribers provided; skipping add_channel_subscribers")
            return {}

        request_data: Dict[str, Any] = {
            "channel_id": channel_id,
            "channel_type": channel_type,
            "subscribers": subscribers,
            "reset": 1 if reset else 0,
        }

        logger.info(
            "Adding subscribers to WuKongIM channel",
            extra={
                "channel_id": channel_id,
                "channel_type": channel_type,
                "subscribers_count": len(subscribers),
                "reset": reset,
            },
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/channel/subscriber_add",
                json_data=request_data,
            )

            logger.debug("WuKongIM add_channel_subscribers result: %s", result)
            return result
        except Exception as e:
            logger.error(
                f"Failed to add subscribers to channel {channel_id}: {e}",
                extra={
                    "channel_id": channel_id,
                    "channel_type": channel_type,
                    "subscribers": subscribers,
                },
            )
            raise

    async def remove_channel_subscribers(
        self,
        *,
        channel_id: str,
        channel_type: int,
        subscribers: List[str],
    ) -> Dict[str, Any]:
        """Remove subscribers from a WuKongIM channel.

        This method is idempotent - removing non-existent subscribers is safe.

        Args:
            channel_id: The channel identifier
            channel_type: Channel type (cannot be 1/person channel)
            subscribers: List of subscriber UIDs to remove

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping remove_channel_subscribers")
            return {}

        if not subscribers:
            logger.debug("No subscribers provided; skipping remove_channel_subscribers")
            return {}

        request_data: Dict[str, Any] = {
            "channel_id": channel_id,
            "channel_type": channel_type,
            "subscribers": subscribers,
        }

        logger.info(
            "Removing subscribers from WuKongIM channel",
            extra={
                "channel_id": channel_id,
                "channel_type": channel_type,
                "subscribers_count": len(subscribers),
            },
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/channel/subscriber_remove",
                json_data=request_data,
            )

            logger.debug("WuKongIM remove_channel_subscribers result: %s", result)
            return result
        except Exception as e:
            logger.error(
                f"Failed to remove subscribers from channel {channel_id}: {e}",
                extra={
                    "channel_id": channel_id,
                    "channel_type": channel_type,
                    "subscribers": subscribers,
                },
            )
            raise

    async def remove_all_channel_subscribers(
        self,
        *,
        channel_id: str,
        channel_type: int,
    ) -> Dict[str, Any]:
        """Remove all subscribers from a WuKongIM channel.

        This method removes all subscribers from a channel. Not supported for 
        person channels (channel_type=1). Will also delete all related 
        conversations and tags.

        Args:
            channel_id: The channel identifier
            channel_type: Channel type (cannot be 1/person channel)

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled; skipping remove_all_channel_subscribers")
            return {}

        request_data: Dict[str, Any] = {
            "channel_id": channel_id,
            "channel_type": channel_type,
        }

        logger.info(
            "Removing all subscribers from WuKongIM channel",
            extra={
                "channel_id": channel_id,
                "channel_type": channel_type,
            },
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/channel/subscriber_remove_all",
                json_data=request_data,
            )

            logger.info(
                f"Successfully removed all subscribers from channel {channel_id}",
                extra={
                    "channel_id": channel_id,
                    "channel_type": channel_type,
                },
            )
            return result
        except Exception as e:
            logger.error(
                f"Failed to remove all subscribers from channel {channel_id}: {e}",
                extra={
                    "channel_id": channel_id,
                    "channel_type": channel_type,
                },
            )
            raise

    async def search_user_messages(
        self,
        *,
        uid: str,
        keyword: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        payload_types: Optional[List[int]] = None,
        from_uid: Optional[str] = None,
        channel_id: Optional[str] = None,
        channel_type: Optional[int] = None,
        topic: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        highlights: Optional[List[str]] = None,
    ) -> WuKongIMSearchMessagesResponse:
        """
        Search messages for a given user via WuKongIM search plugin.

        Args:
            uid: WuKongIM user identifier performing the search
            keyword: Text to search for within payload.content
            page: 1-indexed page number
            limit: Page size
            payload_types: Optional list of message payload types to filter
            from_uid: Restrict to messages from a specific sender UID
            channel_id: Restrict to a specific channel
            channel_type: Channel type filter
            topic: Topic filter
            start_time: Start timestamp (inclusive)
            end_time: End timestamp (inclusive)
            highlights: Highlight fields (defaults to payload.content when keyword provided)

        Returns:
            WuKongIMSearchMessagesResponse containing message search results.
        """
        if not self.enabled:
            logger.debug("WuKongIM integration disabled; skipping message search")
            return WuKongIMSearchMessagesResponse(messages=[], total=0)

        request_data: Dict[str, Any] = {
            "uid": uid,
            "limit": max(1, min(limit, 100)),
            "page": max(page, 1),
        }

        payload_filter: Dict[str, Any] = {}
        if keyword:
            payload_filter["content"] = keyword
        if payload_filter:
            request_data["payload"] = payload_filter

        if payload_types:
            request_data["payload_types"] = payload_types
        if from_uid:
            request_data["from_uid"] = from_uid
        if channel_id:
            request_data["channel_id"] = channel_id
        if channel_type is not None:
            request_data["channel_type"] = channel_type
        if topic:
            request_data["topic"] = topic
        if start_time:
            request_data["start_time"] = start_time
        if end_time:
            request_data["end_time"] = end_time

        if highlights is not None:
            request_data["highlights"] = highlights
        elif keyword:
            request_data["highlights"] = ["payload.content"]

        response = await self._make_request(
            method="POST",
            endpoint="/plugins/wk.plugin.search/usersearch",
            json_data=request_data,
        )

        raw_messages = response.get("messages") or []
        processed_messages: List[WuKongIMSearchResult] = []
        for raw in raw_messages:
            item = dict(raw) if isinstance(raw, dict) else {}
            payload_raw = item.get("payload")
            if isinstance(payload_raw, str):
                item["payload"] = self._decode_message_payload(payload_raw)

            processed_messages.append(WuKongIMSearchResult(**item))

        total = response.get("total", len(processed_messages))
        return WuKongIMSearchMessagesResponse(messages=processed_messages, total=total)


    async def register_or_login_user(
        self,
        uid: str,
        token: Optional[str] = None,
        device_flag: Optional[int] = None,
        device_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Register or login user to WuKongIM.

        Args:
            uid: User unique ID (staff username or ID)
            token: Authentication token (if None, generates UUID)
            device_flag: Device type (0=app, 1=web, 2=pc)
            device_level: Device level (0=secondary, 1=primary)

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return {}

        # Use provided values or defaults from settings
        token = token or str(uuid4())
        device_flag = device_flag if device_flag is not None else settings.WUKONGIM_DEVICE_FLAG
        device_level = device_level if device_level is not None else settings.WUKONGIM_DEVICE_LEVEL

        request_data = {
            "uid": uid,
            "token": token,
            "device_flag": device_flag,
            "device_level": device_level,
        }

        logger.info(
            f"Registering user with WuKongIM",
            extra={
                "uid": uid,
                "device_flag": device_flag,
                "device_level": device_level,
            }
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/user/token",
                json_data=request_data,
            )

            logger.info(f"Successfully registered user {uid} with WuKongIM")
            return result

        except Exception as e:
            logger.error(
                f"Failed to register user {uid} with WuKongIM: {e}",
                extra={"uid": uid, "error": str(e)}
            )
            # Re-raise the exception to be handled by the caller
            raise

    async def check_user_online_status(self, uids: list[str]) -> list[str]:
        """
        Check online status of users.

        Args:
            uids: List of user IDs to check

        Returns:
            List of online user IDs
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return []

        if not uids:
            return []

        logger.debug(f"Checking online status for {len(uids)} users")

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/user/onlinestatus",
                json_data=uids,
            )

            online_uids = result if isinstance(result, list) else []
            logger.debug(f"Found {len(online_uids)} online users")
            return online_uids

        except Exception as e:
            logger.error(f"Failed to check user online status: {e}")
            # Return empty list on error to avoid breaking the main flow
            return []

    async def add_system_accounts(self, uids: list[str]) -> Dict[str, Any]:
        """
        Add system accounts with full messaging permissions.

        Args:
            uids: List of user IDs to add as system accounts

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return {}

        if not uids:
            return {}

        request_data = {"uids": uids}

        logger.info(f"Adding {len(uids)} system accounts to WuKongIM")

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/user/systemuids_add",
                json_data=request_data,
            )

            logger.info(f"Successfully added {len(uids)} system accounts")
            return result

        except Exception as e:
            logger.error(f"Failed to add system accounts: {e}")
            raise

    async def remove_system_accounts(self, uids: list[str]) -> Dict[str, Any]:
        """
        Remove system accounts.

        Args:
            uids: List of user IDs to remove from system accounts

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return {}

        if not uids:
            return {}

        request_data = {"uids": uids}

        logger.info(f"Removing {len(uids)} system accounts from WuKongIM")

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/user/systemuids_remove",
                json_data=request_data,
            )

            logger.info(f"Successfully removed {len(uids)} system accounts")
            return result

        except Exception as e:
            logger.error(f"Failed to remove system accounts: {e}")
            raise

    async def kick_user_device(
        self,
        uid: str,
        device_flag: int = -1,
    ) -> Dict[str, Any]:
        """
        Kick user device from login.

        Args:
            uid: User ID to kick
            device_flag: Device to kick (-1=all, 0=app, 1=web, 2=pc)

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return {}

        request_data = {
            "uid": uid,
            "device_flag": device_flag,
        }

        logger.info(f"Kicking user {uid} device {device_flag} from WuKongIM")

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/user/device_quit",
                json_data=request_data,
            )

            logger.info(f"Successfully kicked user {uid} device {device_flag}")
            return result

        except Exception as e:
            logger.error(f"Failed to kick user device: {e}")
            raise

    async def sync_conversations(
        self,
        uid: str,
        version: int = 0,
        last_msg_seqs: Optional[str] = None,
        msg_count: int = 20,
    ) -> List[WuKongIMConversation]:
        """
        Synchronize recent conversations for a user.

        Args:
            uid: User unique ID
            version: Client's max conversation version (0 if no local data)
            last_msg_seqs: Last message sequences string (optional for incremental sync)
            msg_count: Max message count per conversation

        Returns:
            List of WuKongIMConversation with recent messages
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return []

        request_data = {
            "uid": uid,
            "version": version,
            "msg_count": msg_count,
        }

        if last_msg_seqs:
            request_data["last_msg_seqs"] = last_msg_seqs

        logger.info(
            f"Syncing conversations for user {uid}",
            extra={
                "uid": uid,
                "version": version,
                "msg_count": msg_count,
                "has_last_msg_seqs": bool(last_msg_seqs),
            }
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/conversation/sync",
                json_data=request_data,
            )

            conversations = result if isinstance(result, list) else []

            # Decode base64 payloads in recent messages
            for conversation in conversations:
                if "recents" in conversation and isinstance(conversation["recents"], list):
                    for message in conversation["recents"]:
                        if "payload" in message and isinstance(message["payload"], str):
                            # Decode the base64 payload to JSON
                            message["payload"] = self._decode_message_payload(message["payload"])

                        if "stream_data" in message and isinstance(message["stream_data"], str):
                            try:
                                decoded_bytes = base64.b64decode(message["stream_data"])
                                message["stream_data"] = decoded_bytes.decode("utf-8")
                                logger.debug(
                                    "Successfully decoded stream_data for conversation message %s",
                                    message.get("message_id"),
                                )
                            except (binascii.Error, UnicodeDecodeError) as e:
                                logger.warning(
                                    "Failed to decode stream_data for conversation message %s: %s",
                                    message.get("message_id"),
                                    e,
                                )

            logger.info(f"Successfully synced {len(conversations)} conversations for user {uid}")
            # Convert to WuKongIMConversation objects
            return [WuKongIMConversation(**conv) for conv in conversations]

        except Exception as e:
            logger.error(f"Failed to sync conversations for user {uid}: {e}")
            raise

    async def sync_conversations_by_channels(
        self,
        uid: str,
        channels: List[Dict[str, Any]],
        msg_count: int = 20,
    ) -> List[WuKongIMConversation]:
        """
        Synchronize conversations by specified channel collection.

        Args:
            uid: User unique ID
            channels: List of channels to sync, each with {"channel_id": "...", "channel_type": ...}
            msg_count: Max message count per conversation

        Returns:
            List of WuKongIMConversation with recent messages
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return []

        if not channels:
            logger.debug("No channels provided for sync")
            return []

        request_data = {
            "uid": uid,
            "channels": channels,
            "msg_count": msg_count,
        }

        logger.info(
            f"Syncing conversations by channels for user {uid}",
            extra={
                "uid": uid,
                "channel_count": len(channels),
                "msg_count": msg_count,
            }
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/conversation/syncByChannels",
                json_data=request_data,
            )

            conversations = result if isinstance(result, list) else []

            # Decode base64 payloads in recent messages
            for conversation in conversations:
                if "recents" in conversation and isinstance(conversation["recents"], list):
                    for message in conversation["recents"]:
                        if "payload" in message and isinstance(message["payload"], str):
                            # Decode the base64 payload to JSON
                            message["payload"] = self._decode_message_payload(message["payload"])

                        if "stream_data" in message and isinstance(message["stream_data"], str):
                            try:
                                decoded_bytes = base64.b64decode(message["stream_data"])
                                message["stream_data"] = decoded_bytes.decode("utf-8")
                                logger.debug(
                                    "Successfully decoded stream_data for conversation message %s",
                                    message.get("message_id"),
                                )
                            except (binascii.Error, UnicodeDecodeError) as e:
                                logger.warning(
                                    "Failed to decode stream_data for conversation message %s: %s",
                                    message.get("message_id"),
                                    e,
                                )

            logger.info(f"Successfully synced {len(conversations)} conversations by channels for user {uid}")
            # Convert to WuKongIMConversation objects
            return [WuKongIMConversation(**conv) for conv in conversations]

        except Exception as e:
            logger.error(f"Failed to sync conversations by channels for user {uid}: {e}")
            raise

    async def set_conversation_unread(
        self,
        uid: str,
        channel_id: str,
        channel_type: int,
        unread: int,
    ) -> Dict[str, Any]:
        """
        Set unread count for a conversation.

        Args:
            uid: User unique ID
            channel_id: Channel ID
            channel_type: Channel type (1=personal, 2=group, 3=customer_service)
            unread: Unread message count

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return {}

        request_data = {
            "uid": uid,
            "channel_id": channel_id,
            "channel_type": channel_type,
            "unread": unread,
        }

        logger.info(
            f"Setting unread count for user {uid}, channel {channel_id}",
            extra={
                "uid": uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
                "unread": unread,
            }
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/conversations/setUnread",
                json_data=request_data,
            )

            logger.info(f"Successfully set unread count for user {uid}, channel {channel_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to set unread count for user {uid}, channel {channel_id}: {e}")
            raise

    async def delete_conversation(
        self,
        uid: str,
        channel_id: str,
        channel_type: int,
    ) -> Dict[str, Any]:
        """
        Delete a conversation.

        Args:
            uid: User unique ID
            channel_id: Channel ID
            channel_type: Channel type (1=personal, 2=group, 3=customer_service)

        Returns:
            Response from WuKongIM service
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return {}

        request_data = {
            "uid": uid,
            "channel_id": channel_id,
            "channel_type": channel_type,
        }

        logger.info(
            f"Deleting conversation for user {uid}, channel {channel_id}",
            extra={
                "uid": uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
            }
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/conversations/delete",
                json_data=request_data,
            )

            logger.info(f"Successfully deleted conversation for user {uid}, channel {channel_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to delete conversation for user {uid}, channel {channel_id}: {e}")
            raise

    async def sync_channel_messages(
        self,
        login_uid: str,
        channel_id: str,
        channel_type: int,
        start_message_seq: int = 0,
        end_message_seq: int = 0,
        limit: int = 100,
        pull_mode: int = 1,
    ) -> WuKongIMChannelMessageSyncResponse:
        """
        Synchronize messages from a specific channel.

        Args:
            login_uid: Current login user UID
            channel_id: Channel ID
            channel_type: Channel type (1=personal, 2=group)
            start_message_seq: Start message sequence number (inclusive)
            end_message_seq: End message sequence number (exclusive)
            limit: Message count limit
            pull_mode: Pull mode (0=down, 1=up)

        Returns:
            WuKongIMChannelMessageSyncResponse with decoded payloads
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            return WuKongIMChannelMessageSyncResponse(
                start_message_seq=start_message_seq,
                end_message_seq=end_message_seq,
                more=0,
                messages=[]
            )

        request_data = {
            "login_uid": login_uid,
            "channel_id": channel_id,
            "channel_type": channel_type,
            "start_message_seq": start_message_seq,
            "end_message_seq": end_message_seq,
            "limit": limit,
            "pull_mode": pull_mode,
            "stream_v2": 1,
        }

        logger.info(
            f"Syncing channel messages for user {login_uid}",
            extra={
                "login_uid": login_uid,
                "channel_id": channel_id,
                "channel_type": channel_type,
                "start_message_seq": start_message_seq,
                "end_message_seq": end_message_seq,
                "limit": limit,
                "pull_mode": pull_mode,
                "stream_v2": 1,
            }
        )

        try:
            result = await self._make_request(
                method="POST",
                endpoint="/channel/messagesync",
                json_data=request_data,
            )

            # Decode base64 payloads and stream_data in messages
            if "messages" in result and isinstance(result["messages"], list):
                for message in result["messages"]:
                    # Decode the base64 payload to JSON
                    if "payload" in message and isinstance(message["payload"], str):
                        message["payload"] = self._decode_message_payload(message["payload"])

                    # Decode the base64 stream_data if present
                    if "stream_data" in message and isinstance(message["stream_data"], str):
                        try:
                            decoded_bytes = base64.b64decode(message["stream_data"])
                            message["stream_data"] = decoded_bytes.decode('utf-8')
                            logger.debug(f"Successfully decoded stream_data for message {message.get('message_id')}")
                        except (binascii.Error, UnicodeDecodeError) as e:
                            logger.warning(f"Failed to decode stream_data for message {message.get('message_id')}: {e}")
                            # Keep original base64 string if decode fails
                            pass

            message_count = len(result.get("messages", []))
            logger.info(f"Successfully synced {message_count} channel messages for user {login_uid}")
            return WuKongIMChannelMessageSyncResponse(**result)

        except Exception as e:
            logger.error(f"Failed to sync channel messages for user {login_uid}: {e}")
            raise

    async def get_route(self, uid: str) -> WuKongIMRouteResponse:
        """
        Get WebSocket connection address for a user.

        Args:
            uid: User unique ID (staff UID or visitor UID)

        Returns:
            Route response with tcp_addr and ws_addr
        """
        if not self.enabled:
            logger.debug("WuKongIM integration is disabled")
            raise HTTPException(
                status_code=503,
                detail="WuKongIM service is disabled"
            )

        logger.info(f"Getting route for user {uid}")

        try:
            result = await self._make_request(
                method="GET",
                endpoint="/route",
                params={"uid": uid},
            )

            logger.info(f"Successfully retrieved route for user {uid}")
            return WuKongIMRouteResponse(**result)

        except Exception as e:
            logger.error(f"Failed to get route for user {uid}: {e}")
            raise


# Global WuKongIM client instance
wukongim_client = WuKongIMClient()
