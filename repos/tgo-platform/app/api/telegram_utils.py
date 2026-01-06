"""Telegram Bot API utilities.

This module provides helper functions for interacting with the Telegram Bot API:
- Sending text messages
- Verifying webhook requests (optional secret_token)
- Getting bot information

Docs: https://core.telegram.org/bots/api
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Telegram Bot API base URL
TELEGRAM_API_BASE = "https://api.telegram.org"


async def telegram_send_text(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Send a text message via Telegram Bot API.

    Args:
        bot_token: Bot token from @BotFather
        chat_id: Target chat ID (user, group, or channel)
        text: Message text (max 4096 characters)
        parse_mode: Optional parsing mode (Markdown, MarkdownV2, HTML)
        timeout: Request timeout in seconds

    Returns:
        Telegram API response as dict

    Raises:
        httpx.HTTPStatusError: If the request fails
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:4096],  # Telegram text limit
    }
    
    if parse_mode:
        payload["parse_mode"] = parse_mode

    timeout_seconds = timeout or settings.request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if not result.get("ok"):
            logger.error(
                "[TELEGRAM] sendMessage failed: %s",
                result.get("description", "Unknown error")
            )
        
        return result


async def telegram_send_photo(
    bot_token: str,
    chat_id: str,
    photo: str | bytes,
    caption: str | None = None,
    parse_mode: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Send a photo via Telegram Bot API.

    Args:
        bot_token: Bot token from @BotFather
        chat_id: Target chat ID
        photo: Photo to send (URL as string, or raw bytes)
        caption: Optional photo caption
        parse_mode: Optional parsing mode for caption
        timeout: Request timeout in seconds

    Returns:
        Telegram API response as dict
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendPhoto"
    
    data: dict[str, Any] = {
        "chat_id": chat_id,
    }
    if caption:
        data["caption"] = caption[:1024]
    if parse_mode:
        data["parse_mode"] = parse_mode

    timeout_seconds = timeout or settings.request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        if isinstance(photo, bytes):
            # Send as file (multipart)
            files = {"photo": ("image.jpg", photo, "image/jpeg")}
            response = await client.post(url, data=data, files=files)
        else:
            # Send as URL (string)
            data["photo"] = photo
            response = await client.post(url, data=data)
            
        response.raise_for_status()
        result = response.json()
        
        if not result.get("ok"):
            logger.error(
                "[TELEGRAM] sendPhoto failed: %s",
                result.get("description", "Unknown error")
            )
        
        return result


async def telegram_get_file(
    bot_token: str,
    file_id: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Get file information from Telegram.

    Args:
        bot_token: Bot token
        file_id: File ID to get info for
        timeout: Request timeout

    Returns:
        Telegram File object (includes file_path)
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getFile"
    payload = {"file_id": file_id}
    timeout_seconds = timeout or settings.request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        return result


async def telegram_download_file(
    bot_token: str,
    file_path: str,
    timeout: int | None = None,
) -> bytes:
    """Download a file from Telegram.

    Args:
        bot_token: Bot token
        file_path: File path obtained from getFile
        timeout: Request timeout

    Returns:
        File content as bytes
    """
    url = f"{TELEGRAM_API_BASE}/file/bot{bot_token}/{file_path}"
    timeout_seconds = timeout or settings.request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def telegram_get_me(
    bot_token: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Get information about the bot.

    Args:
        bot_token: Bot token from @BotFather
        timeout: Request timeout in seconds

    Returns:
        Bot information as dict (id, is_bot, first_name, username, etc.)

    Raises:
        httpx.HTTPStatusError: If the request fails
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getMe"
    timeout_seconds = timeout or settings.request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def telegram_set_webhook(
    bot_token: str,
    webhook_url: str,
    secret_token: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Set the webhook URL for the bot.

    This configures Telegram to send updates to the specified URL.
    Should be called when platform is enabled or bot_token is updated.

    Args:
        bot_token: Bot token from @BotFather
        webhook_url: HTTPS URL for receiving updates
        secret_token: Optional secret token for webhook verification
        timeout: Request timeout in seconds

    Returns:
        Telegram API response

    Raises:
        httpx.HTTPStatusError: If the request fails
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/setWebhook"
    timeout_seconds = timeout or settings.request_timeout_seconds

    payload: dict[str, Any] = {
        "url": webhook_url,
    }
    
    if secret_token:
        payload["secret_token"] = secret_token

    logger.info("[TELEGRAM] Setting webhook: %s", webhook_url)

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if result.get("ok"):
            logger.info("[TELEGRAM] Webhook set successfully")
        else:
            logger.error(
                "[TELEGRAM] Failed to set webhook: %s",
                result.get("description", "Unknown error")
            )
        
        return result


async def telegram_delete_webhook(
    bot_token: str,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Delete the webhook (disable webhook mode).

    Should be called when platform is disabled.

    Args:
        bot_token: Bot token from @BotFather
        timeout: Request timeout in seconds

    Returns:
        Telegram API response
    """
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/deleteWebhook"
    timeout_seconds = timeout or settings.request_timeout_seconds

    logger.info("[TELEGRAM] Deleting webhook")

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url)
        response.raise_for_status()
        return response.json()


def telegram_verify_secret_token(
    request_secret_token: str,
    expected_secret_token: str,
) -> bool:
    """Verify the X-Telegram-Bot-Api-Secret-Token header.

    When setting up a webhook, you can provide a secret_token parameter.
    Telegram will include this token in the X-Telegram-Bot-Api-Secret-Token
    header of every webhook request.

    Args:
        request_secret_token: Token from request header
        expected_secret_token: Expected token from platform config

    Returns:
        True if tokens match, False otherwise
    """
    if not expected_secret_token:
        # No secret configured, skip verification
        return True
    
    return hmac.compare_digest(request_secret_token or "", expected_secret_token)


def extract_message_from_update(update: dict[str, Any]) -> dict[str, Any] | None:
    """Extract message data from a Telegram Update object.

    Telegram sends different types of updates. This function extracts
    the message from various update types.

    Args:
        update: Telegram Update object

    Returns:
        Message dict or None if no message found
    """
    # Check for regular message
    if "message" in update:
        return update["message"]
    
    # Check for edited message
    if "edited_message" in update:
        return update["edited_message"]
    
    # Check for channel post
    if "channel_post" in update:
        return update["channel_post"]
    
    # Check for edited channel post
    if "edited_channel_post" in update:
        return update["edited_channel_post"]
    
    # Check for callback query (button click)
    if "callback_query" in update:
        callback = update["callback_query"]
        if "message" in callback:
            return callback["message"]
    
    return None


def extract_text_from_message(message: dict[str, Any]) -> str:
    """Extract text content from a Telegram message.

    Args:
        message: Telegram Message object

    Returns:
        Text content or description of non-text content
    """
    # Regular text message
    if "text" in message:
        return message["text"]
    
    # Caption for media messages
    if "caption" in message:
        return message["caption"]
    
    # Photo
    if "photo" in message:
        return "[photo]"
    
    # Document
    if "document" in message:
        doc = message["document"]
        return f"[document] {doc.get('file_name', '')}"
    
    # Voice message
    if "voice" in message:
        return "[voice message]"
    
    # Video
    if "video" in message:
        return "[video]"
    
    # Audio
    if "audio" in message:
        audio = message["audio"]
        return f"[audio] {audio.get('title', audio.get('file_name', ''))}"
    
    # Sticker
    if "sticker" in message:
        sticker = message["sticker"]
        return f"[sticker] {sticker.get('emoji', '')}"
    
    # Location
    if "location" in message:
        loc = message["location"]
        return f"[location] {loc.get('latitude')}, {loc.get('longitude')}"
    
    # Contact
    if "contact" in message:
        contact = message["contact"]
        return f"[contact] {contact.get('first_name', '')} {contact.get('phone_number', '')}"
    
    # Poll
    if "poll" in message:
        poll = message["poll"]
        return f"[poll] {poll.get('question', '')}"
    
    return "[unsupported message type]"


def get_chat_type(message: dict[str, Any]) -> str:
    """Get the chat type from a message.

    Args:
        message: Telegram Message object

    Returns:
        Chat type: private, group, supergroup, or channel
    """
    chat = message.get("chat", {})
    return chat.get("type", "private")


def get_sender_info(message: dict[str, Any]) -> tuple[str, str | None, str | None]:
    """Extract sender information from a message.

    Args:
        message: Telegram Message object

    Returns:
        Tuple of (user_id, username, display_name)
    """
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", ""))
    username = from_user.get("username")
    
    # Build display name
    first_name = from_user.get("first_name", "")
    last_name = from_user.get("last_name", "")
    display_name = f"{first_name} {last_name}".strip() or username or user_id
    
    return user_id, username, display_name
