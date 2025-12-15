"""WuKongIM integration schemas."""

from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from app.schemas.base import BaseSchema


class WuKongIMUserRegistration(BaseSchema):
    """Schema for WuKongIM user registration/login."""

    uid: str = Field(..., description="User unique ID")
    token: str = Field(..., description="Authentication token")
    device_flag: int = Field(
        default=1,
        description="Device flag: 0=app, 1=web, 2=pc"
    )
    device_level: int = Field(
        default=1,
        description="Device level: 0=secondary, 1=primary"
    )


class WuKongIMOnlineStatusRequest(BaseSchema):
    """Schema for checking user online status."""

    uids: List[str] = Field(..., description="List of user IDs to check")


class WuKongIMOnlineStatusResponse(BaseSchema):
    """Schema for online status response."""

    online_uids: List[str] = Field(..., description="List of online user IDs")


class WuKongIMSystemAccountsRequest(BaseSchema):
    """Schema for system accounts management."""

    uids: List[str] = Field(..., description="List of user IDs")


class WuKongIMDeviceKickRequest(BaseSchema):
    """Schema for kicking user devices."""

    uid: str = Field(..., description="User ID to kick")
    device_flag: int = Field(
        default=-1,
        description="Device to kick: -1=all, 0=app, 1=web, 2=pc"
    )


class WuKongIMIntegrationStatus(BaseSchema):
    """Schema for WuKongIM integration status."""

    enabled: bool = Field(..., description="Whether WuKongIM integration is enabled")
    service_url: str = Field(..., description="WuKongIM service URL")
    last_sync: Optional[str] = Field(None, description="Last synchronization timestamp")
    error_count: int = Field(default=0, description="Number of recent errors")
    last_error: Optional[str] = Field(None, description="Last error message")


# Conversation-related schemas
class WuKongIMMessageHeader(BaseSchema):
    """Schema for WuKongIM message header."""

    no_persist: int = Field(..., description="Whether to persist message (0=persist, 1=no persist)")
    red_dot: int = Field(..., description="Whether to show red dot (0=no, 1=yes)")
    sync_once: int = Field(..., description="Whether write diffusion (0=no, 1=yes)")



class WuKongIMSettingFlags(BaseSchema):
    """Parsed flags from WuKongIM message `setting` field for frontend consumption."""
    receipt: bool = Field(..., description="Receipt enabled (bit 7, 1<<7)")
    signal: bool = Field(..., description="Signal encryption enabled (bit 5, 1<<5)")
    no_encrypt: bool = Field(..., description="No encryption (bit 4, 1<<4)")
    topic: bool = Field(..., description="Has topic (bit 3, 1<<3)")
    stream: bool = Field(..., description="Stream enabled (bit 1, 1<<1)")

class WuKongIMMessage(BaseSchema):
    """Schema for WuKongIM message."""

    header: WuKongIMMessageHeader = Field(..., description="Message header")
    setting: int = Field(..., description="Message settings (uint8)")
    message_id: int = Field(..., description="Global unique message ID")
    client_msg_no: str = Field(..., description="Client message number (UUID)")
    message_seq: int = Field(..., description="Message sequence number")
    from_uid: str = Field(..., description="Sender user ID")
    channel_id: str = Field(..., description="Channel ID")
    channel_type: int = Field(..., description="Channel type (1=personal, 2=group)")
    timestamp: int = Field(..., description="Message timestamp (10-digit seconds)")
    payload: Dict[str, Any] = Field(..., description="Decoded JSON message content")
    end: Optional[int] = Field(None, description="Stream end flag (0=not ended, 1=ended)")
    end_reason: Optional[int] = Field(None, description="Stream end reason code")
    error: Optional[str] = Field(None, description="Error message")
    stream_data: Optional[str] = Field(None, description="Decoded stream data (base64 decoded)")

    @computed_field  # type: ignore[misc]
    @property
    def message_id_str(self) -> str:
        """String representation of message_id to avoid JS int64 precision issues."""
        try:
            return str(self.message_id)
        except Exception:
            return ""

    @computed_field  # type: ignore[misc]
    @property
    def setting_flags(self) -> WuKongIMSettingFlags:
        """Parsed boolean flags from `setting` bitmask."""
        s = int(self.setting or 0)
        return WuKongIMSettingFlags(
            receipt=bool(s & (1 << 7)),
            signal=bool(s & (1 << 5)),
            no_encrypt=bool(s & (1 << 4)),
            topic=bool(s & (1 << 3)),
            stream=bool(s & (1 << 1)),
        )


class WuKongIMConversation(BaseSchema):
    """Schema for WuKongIM conversation."""

    channel_id: str = Field(..., description="Channel ID")
    channel_type: int = Field(..., description="Channel type (1=personal, 2=group, 3=customer_service)")
    unread: int = Field(..., description="Unread message count")
    timestamp: int = Field(..., description="Timestamp (10-digit seconds)")
    last_msg_seq: int = Field(..., description="Last message sequence number")
    last_client_msg_no: str = Field(..., description="Last client message number")
    version: int = Field(..., description="Data version number")
    recents: List[WuKongIMMessage] = Field(..., description="Recent messages")


class WuKongIMConversationSyncRequest(BaseSchema):
    """Schema for conversation synchronization request."""

    last_msg_seqs: Optional[str] = Field(
        None,
        description="Last message sequences string (format: channelID:channelType:last_msg_seq|...)"
    )
    msg_count: int = Field(
        default=20,
        description="Max message count per conversation"
    )


class WuKongIMConversationSyncResponse(BaseSchema):
    """Schema for conversation synchronization response."""

    conversations: List[WuKongIMConversation] = Field(..., description="List of conversations")


class ChannelInfo(BaseSchema):
    """Channel information schema for conversation response."""
    
    name: str = Field(..., description="Channel display name")
    avatar: str = Field(..., description="Channel avatar URL")
    channel_id: str = Field(..., description="WuKongIM channel identifier")
    channel_type: int = Field(..., description="Channel type: 1 (personal), 251 (customer service)")
    entity_type: str = Field(
        ..., description="Entity type: 'visitor', 'staff', 'agent', or 'team'"
    )
    extra: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional entity-specific data"
    )


class WuKongIMConversationWithChannelsResponse(BaseSchema):
    """Schema for conversation synchronization response with channel details."""

    conversations: List[WuKongIMConversation] = Field(..., description="List of conversations")
    channels: List[ChannelInfo] = Field(
        default_factory=list,
        description="List of channel information for each conversation"
    )


class WuKongIMSetUnreadRequest(BaseSchema):
    """Schema for setting conversation unread count."""

    channel_id: str = Field(..., description="Channel ID")
    channel_type: int = Field(..., description="Channel type")
    unread: int = Field(..., description="Unread message count")


class WuKongIMDeleteConversationRequest(BaseSchema):
    """Schema for deleting conversation."""

    uid: str = Field(..., description="Current login user UID")
    channel_id: str = Field(..., description="Channel ID")
    channel_type: int = Field(..., description="Channel type")


# Channel message synchronization schemas
class WuKongIMChannelMessageSyncRequest(BaseSchema):
    """Schema for channel message synchronization request."""

    channel_id: str = Field(..., description="Channel ID")
    channel_type: int = Field(..., description="Channel type (1=personal, 2=group)")
    start_message_seq: int = Field(
        default=0,
        description="Start message sequence number (inclusive)"
    )
    end_message_seq: int = Field(
        default=0,
        description="End message sequence number (exclusive)"
    )
    limit: int = Field(
        default=100,
        description="Message count limit",
        ge=1,
        le=1000
    )
    pull_mode: int = Field(
        default=1,
        description="Pull mode (0=down, 1=up)"
    )


class WuKongIMChannelMessageSyncResponse(BaseSchema):
    """Schema for channel message synchronization response."""

    start_message_seq: int = Field(..., description="Query start message sequence")
    end_message_seq: int = Field(..., description="Query end message sequence")
    more: int = Field(..., description="Whether there are more messages (0=no, 1=yes)")
    messages: List[WuKongIMMessage] = Field(..., description="List of messages")


class WuKongIMRouteResponse(BaseSchema):
    """Schema for WuKongIM route (WebSocket connection address) response."""

    tcp_addr: str = Field(..., description="TCP connection address (format: IP:PORT)")
    ws_addr: str = Field(..., description="WebSocket connection address (format: ws://IP:PORT)")
    wss_addr: Optional[str] = Field(None, description="WebSocket Secure connection address (format: wss//IP:PORT)")


class WuKongIMMessageSendResponse(BaseSchema):
    """Schema for message send response."""
    
    message_id: int = Field(..., description="Global unique message ID")
    client_msg_no: str = Field(..., description="Client message number (UUID)")


class WuKongIMChannelLastMessage(BaseSchema):
    """Schema for channel last message response."""
    
    message_id: int = Field(..., description="Global unique message ID")
    message_seq: int = Field(..., description="Message sequence number")
    timestamp: int = Field(..., description="Message timestamp (10-digit seconds)")
    from_uid: Optional[str] = Field(None, description="Sender user ID")
    payload: Optional[Dict[str, Any]] = Field(None, description="Message payload")


class WuKongIMSearchResult(BaseSchema):
    """Schema for a single search result item."""
    
    message_id: int = Field(..., description="Global unique message ID")
    message_seq: int = Field(..., description="Message sequence number")
    from_uid: str = Field(..., description="Sender user ID")
    channel_id: str = Field(..., description="Channel ID")
    channel_type: int = Field(..., description="Channel type")
    timestamp: int = Field(..., description="Message timestamp")
    payload: Dict[str, Any] = Field(..., description="Message payload")
    highlights: Optional[List[str]] = Field(None, description="Highlighted text fragments")


class WuKongIMSearchMessagesResponse(BaseSchema):
    """Schema for message search response."""
    
    total: int = Field(..., description="Total number of matching messages")
    messages: List[WuKongIMSearchResult] = Field(default_factory=list, description="List of matching messages")
