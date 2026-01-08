"""
Slack Bot API utilities for tgo-platform.

This module provides helper functions for interacting with the Slack API,
including sending messages, uploading files, and retrieving user information.
"""

import logging
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


async def slack_send_text(
    bot_token: str,
    channel: str,
    text: str,
    thread_ts: Optional[str] = None,
) -> dict:
    """
    Send a text message to a Slack channel or DM.

    Args:
        bot_token: Slack Bot Token (xoxb-...)
        channel: Channel ID or user ID for DM
        text: Message text
        thread_ts: Optional thread timestamp for replying in thread

    Returns:
        Slack API response dict
    """
    try:
        client = WebClient(token=bot_token)
        response = client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
        )
        logger.info(f"[SLACK] Message sent to {channel}")
        return response.data
    except SlackApiError as e:
        logger.error(f"[SLACK] Failed to send message: {e.response['error']}")
        raise


async def slack_send_file(
    bot_token: str,
    channel: str,
    file_bytes: bytes,
    filename: str,
    title: Optional[str] = None,
    initial_comment: Optional[str] = None,
    thread_ts: Optional[str] = None,
) -> dict:
    """
    Upload and send a file to a Slack channel or DM.

    Args:
        bot_token: Slack Bot Token (xoxb-...)
        channel: Channel ID or user ID for DM
        file_bytes: File content as bytes
        filename: Filename to display
        title: Optional file title
        initial_comment: Optional message to accompany the file
        thread_ts: Optional thread timestamp

    Returns:
        Slack API response dict
    """
    try:
        client = WebClient(token=bot_token)
        # Use files_upload_v2 (the new async upload method)
        response = client.files_upload_v2(
            channel=channel,
            file=file_bytes,
            filename=filename,
            title=title or filename,
            initial_comment=initial_comment,
            thread_ts=thread_ts,
        )
        logger.info(f"[SLACK] File '{filename}' uploaded to {channel}")
        return response.data
    except SlackApiError as e:
        logger.error(f"[SLACK] Failed to upload file: {e.response['error']}")
        raise


async def slack_get_user_info(
    bot_token: str,
    user_id: str,
) -> dict:
    """
    Get user information from Slack.

    Args:
        bot_token: Slack Bot Token (xoxb-...)
        user_id: Slack user ID (U...)

    Returns:
        User info dict containing name, email, avatar, etc.
    """
    try:
        client = WebClient(token=bot_token)
        response = client.users_info(user=user_id)
        user = response.data.get("user", {})
        profile = user.get("profile", {})
        return {
            "id": user.get("id"),
            "name": user.get("name"),
            "real_name": user.get("real_name") or profile.get("real_name"),
            "display_name": profile.get("display_name") or user.get("name"),
            "email": profile.get("email"),
            "avatar": profile.get("image_192") or profile.get("image_72"),
            "is_bot": user.get("is_bot", False),
        }
    except SlackApiError as e:
        logger.error(f"[SLACK] Failed to get user info: {e.response['error']}")
        raise


async def slack_download_file(
    bot_token: str,
    file_url: str,
) -> bytes:
    """
    Download a file from Slack (private URL).

    Slack file URLs are private and require authorization.

    Args:
        bot_token: Slack Bot Token (xoxb-...)
        file_url: Private file URL (url_private)

    Returns:
        File content as bytes
    """
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                file_url,
                headers={"Authorization": f"Bearer {bot_token}"},
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.error(f"[SLACK] Failed to download file: {e}")
        raise
async def slack_get_dm_channel(
    bot_token: str,
    user_id: str,
) -> str:
    """
    Open a DM channel with a user and return the channel ID.
    
    Slack's files_upload_v2 and other methods often require a real channel ID
    (starting with D, C, G) rather than a user ID (starting with U).
    
    Args:
        bot_token: Slack Bot Token
        user_id: Slack User ID
        
    Returns:
        Channel ID (starting with D...)
    """
    try:
        client = WebClient(token=bot_token)
        response = client.conversations_open(users=user_id)
        channel_id = response.data.get("channel", {}).get("id")
        if not channel_id:
            logger.error(f"[SLACK] Failed to resolve channel ID for user {user_id}")
            return user_id # Fallback
        return channel_id
    except SlackApiError as e:
        logger.error(f"[SLACK] Error opening DM with {user_id}: {e.response['error']}")
        return user_id # Fallback
