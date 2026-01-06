from __future__ import annotations

import hashlib
import logging
import uuid
import xml.etree.ElementTree as ET
import base64
import json
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 32:
        # Invalid padding; return as-is to fail downstream
        return data
    return data[:-pad_len]


def _wecom_decrypt_message(encrypt_b64: str, encoding_aes_key: str, receiveid_expected: str) -> Optional[str]:
    """Decrypt WeCom encrypted message using AES-256-CBC PKCS7.

    Returns the decrypted inner XML string on success, or None on failure.
    """
    try:
        aes_key = base64.b64decode(encoding_aes_key + "=")  # 43 chars -> 32 bytes
        iv = aes_key[:16]
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        ciphertext = base64.b64decode(encrypt_b64)
        padded_plain = decryptor.update(ciphertext) + decryptor.finalize()
        plain = _pkcs7_unpad(padded_plain)
        if len(plain) < 20:
            return None
        # 16 bytes random, 4 bytes msg_len (big-endian), then xml, then receiveid
        msg_len = int.from_bytes(plain[16:20], "big")
        xml_bytes = plain[20:20 + msg_len]
        receiveid = plain[20 + msg_len:].decode("utf-8", errors="ignore")
        if receiveid_expected and receiveid_expected != receiveid:
            return None
        return xml_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return None

from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.base import get_db
from app.db.models import Platform, WeComInbox, WuKongIMInbox, FeishuInbox, DingTalkInbox, TelegramInbox
from app.api.error_utils import error_response, get_request_id
from app.api.schemas import ErrorResponse
from app.api.feishu_utils import feishu_verify_signature, feishu_decrypt_message, feishu_clean_message_text
from app.api.dingtalk_utils import dingtalk_verify_signature
from app.api.telegram_utils import (
    telegram_verify_secret_token,
    extract_message_from_update,
    extract_text_from_message,
    get_chat_type,
    get_sender_info,
)

router = APIRouter()


def _sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def compute_msg_signature(token: str, timestamp: str, nonce: str, msg: str | None = None) -> str:
    """Compute WeCom msg_signature = sha1(sort(token, timestamp, nonce, msg_encrypt_or_echostr)).
    When msg is None (plain mode POST w/o Encrypt), use only token/timestamp/nonce.
    """
    parts = [token, timestamp, nonce]
    if msg is not None:
        parts.append(msg)
    parts.sort()
    return _sha1_hex("".join(parts))



# --- WeCom helpers (moved to dedicated module) ---
from app.api.wecom_utils import build_xml_raw_payload, sync_kf_messages

async def _handle_wecom_webhook(platform: Platform, request: Request, db: AsyncSession) -> dict[str, Any] | Response:
    """Handle WeCom webhook POST callback for a given platform.

    Producer stage: validate request, parse XML, and persist a WeComInbox row.

    Returns a JSON dict or Response to be sent to the client.
    """
    config = platform.config or {}
    token = (config.get("token") or "")

    # Query params for signature verification
    query = request.query_params
    msg_signature = query.get("msg_signature")
    timestamp = query.get("timestamp") or ""
    nonce = query.get("nonce") or ""

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8") if raw_body else ""

    # Very minimal XML parsing (plain mode). Encrypted mode contains <Encrypt>...
    try:
        root = ET.fromstring(body_text)
    except Exception:
        return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_PAYLOAD", message="Invalid XML payload", request_id=get_request_id(request))

    encrypt_node = root.findtext("Encrypt")

    # Verify signature and prepare XML root to parse
    xml_root = root
    decrypted_xml_text = None

    if encrypt_node:
        # Encrypted mode signature includes Encrypt
        if not (token and msg_signature):
            return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_SIGNATURE", message="Missing or invalid signature parameters", request_id=get_request_id(request))
        expected = compute_msg_signature(token, timestamp, nonce, encrypt_node)
        if expected != msg_signature:
            return error_response(status.HTTP_403_FORBIDDEN, code="SIGNATURE_MISMATCH", message="Signature verification failed", request_id=get_request_id(request))

        # Decrypt using encoding_aes_key from config
        encoding_aes_key = (config.get("encoding_aes_key") or "").strip()
        corp_id = (config.get("corp_id") or "").strip()
        if not encoding_aes_key:
            return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, code="ENCRYPTION_CONFIG_MISSING", message="encoding_aes_key is not configured for this WeCom platform")

        decrypted_xml_text = _wecom_decrypt_message(encrypt_node, encoding_aes_key, corp_id)
        if not decrypted_xml_text:
            return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_PAYLOAD", message="Failed to decrypt WeCom message")
        try:
            xml_root = ET.fromstring(decrypted_xml_text)
        except Exception:
            return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_PAYLOAD", message="Decrypted XML is invalid")
    else:
        # Plain mode signature without Encrypt
        if not (token and msg_signature):
            return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_SIGNATURE", message="Missing or invalid signature parameters", request_id=get_request_id(request))
        expected = compute_msg_signature(token, timestamp, nonce)
        if expected != msg_signature:
            return error_response(status.HTTP_403_FORBIDDEN, code="SIGNATURE_MISMATCH", message="Signature verification failed", request_id=get_request_id(request))

    # Extract fields from the appropriate XML root (decrypted or plain)
    msg_type = xml_root.findtext("MsgType") or ""
    from_user = xml_root.findtext("FromUserName") or ""
    content = xml_root.findtext("Content") or ""
    message_id = xml_root.findtext("MsgId") or ""
    create_time_raw = xml_root.findtext("CreateTime") or ""

    # Convert CreateTime (epoch seconds) to timezone-aware datetime
    received_at = None
    try:
        ts = int(create_time_raw)
        received_at = datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        received_at = None

    # Handle event-type callbacks (currently focusing on kf_msg_or_event)

    if (msg_type or "").lower() == "event":
        # Specifically handle KF event notification: kf_msg_or_event -> trigger sync, do not store event itself
        token_val = xml_root.findtext("Token") or ""
        open_kf_id_for_cursor = xml_root.findtext("OpenKfId") or ""
        open_kf_id_for_cursor = open_kf_id_for_cursor or (xml_root.findtext("ToUserName") or "")

        try:
            cfg = platform.config or {}
            corp_id = (cfg.get("corp_id") or "").strip()
            app_secret = (cfg.get("app_secret") or "").strip()
            # Fire-and-forget style sync; but await to complete current batch with a safety loop
            if token_val and corp_id and app_secret and open_kf_id_for_cursor:
                await sync_kf_messages(corp_id=corp_id, app_secret=app_secret, event_token=token_val, open_kf_id=open_kf_id_for_cursor, platform_id=platform.id, db=db)
            else:
                logging.warning("[WECOM] KF event missing required fields (token/corp_id/app_secret/open_kf_id)")
        except Exception as e:
            logging.error("[WECOM] KF event sync failed: %s", e)
        # Always acknowledge the event quickly
        return {"ok": True}

    # Store inbound message into wecom_inbox (producer stage)
    try:
        raw_payload = build_xml_raw_payload(
            raw_xml=body_text,
            decrypted_xml=decrypted_xml_text,
            parsed={
                "MsgType": msg_type,
                "FromUserName": from_user,
                "MsgId": message_id,
                "CreateTime": create_time_raw,
                "Content": content,
            },
        )

        # Extract OpenKfId if present in callback (may be absent for internal messages)
        open_kfid_val = xml_root.findtext("OpenKfId") or None

        # Store inbound text message
        inbox_record = WeComInbox(
            platform_id=platform.id,
            message_id=message_id or "",
            source_type="wecom_kf",  # WeCom Customer Service (客服)
            from_user=from_user,
            open_kfid=open_kfid_val,
            msg_type=msg_type,
            content=content or "",
            is_from_colleague=True,
            raw_payload=raw_payload,
            status="pending",
            received_at=received_at,
        )
        db.add(inbox_record)
        await db.commit()
    except IntegrityError as e:
        # Duplicate delivery; already stored. Treat as success.
        print(f"[WECOM] Duplicate message detected for {platform.id}: {e}")
        await db.rollback()
    except Exception as e:
        print(f"[WECOM] Store raw message failed for {platform.id}: {e}")
        await db.rollback()
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Immediate 200 OK; WeCom expects a fast response.
    return {"ok": True}


async def _handle_wecom_bot_webhook(platform: Platform, request: Request, db: AsyncSession) -> dict[str, Any] | Response:
    """Handle WeCom Bot (企业微信群机器人/智能机器人) webhook POST callback.

    WeCom Bot uses JSON format (not XML like regular WeCom):
    - Request body: {"encrypt": "..."} in JSON format
    - Verify msg_signature using token, timestamp, nonce, and encrypt
    - Decrypt the encrypted message to get JSON content
    - Store the message in WeComInbox for async processing

    Docs: https://developer.work.weixin.qq.com/document/path/100719

    Config structure:
    {
        "token": "...",
        "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...",
        "encoding_aes_key": "..."
    }
    """
    config = platform.config or {}
    token = (config.get("token") or "").strip()

    # Query params for signature verification
    query = request.query_params
    msg_signature = query.get("msg_signature")
    timestamp = query.get("timestamp") or ""
    nonce = query.get("nonce") or ""

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8") if raw_body else ""

    logging.info("[WECOM_BOT] Received callback: platform_id=%s, msg_signature=%s, timestamp=%s, nonce=%s, body_length=%d",
                 platform.id, msg_signature, timestamp, nonce, len(body_text))
    logging.debug("[WECOM_BOT] Raw body: %s", body_text[:500] if body_text else "(empty)")

    # WeCom Bot uses JSON format: {"encrypt": "..."}
    try:
        body_json = json.loads(body_text)
    except Exception as e:
        logging.error("[WECOM_BOT] Failed to parse JSON: %s, body=%s", e, body_text[:200] if body_text else "(empty)")
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Invalid JSON payload",
            request_id=get_request_id(request),
        )

    encrypt_content = body_json.get("encrypt") or ""
    logging.info("[WECOM_BOT] encrypt field present: %s, length=%d", bool(encrypt_content), len(encrypt_content))

    decrypted_json = None
    msg_data = {}

    if encrypt_content:
        # Encrypted mode: verify signature and decrypt
        if not (token and msg_signature):
            logging.warning("[WECOM_BOT] Missing signature params: token=%s, msg_signature=%s", bool(token), bool(msg_signature))
            return error_response(
                status.HTTP_400_BAD_REQUEST,
                code="INVALID_SIGNATURE",
                message="Missing or invalid signature parameters",
                request_id=get_request_id(request),
            )

        # Signature = sha1(sort(token, timestamp, nonce, encrypt))
        expected = compute_msg_signature(token, timestamp, nonce, encrypt_content)
        if expected != msg_signature:
            logging.warning("[WECOM_BOT] Signature mismatch: expected=%s, got=%s", expected, msg_signature)
            return error_response(
                status.HTTP_403_FORBIDDEN,
                code="SIGNATURE_MISMATCH",
                message="Signature verification failed",
                request_id=get_request_id(request),
            )

        # Decrypt using encoding_aes_key from config
        encoding_aes_key = (config.get("encoding_aes_key") or "").strip()

        if not encoding_aes_key:
            logging.error("[WECOM_BOT] encoding_aes_key not configured for platform %s", platform.id)
            return error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="ENCRYPTION_CONFIG_MISSING",
                message="encoding_aes_key is not configured for this WeCom Bot platform",
            )

        # For wecom_bot (智能机器人), receiveid can be empty or corp_id
        corp_id = (config.get("corp_id") or "").strip()
        logging.info("[WECOM_BOT] Attempting to decrypt with corp_id=%s", corp_id[:8] + "..." if corp_id else "(empty)")

        # Try decryption with corp_id first, then empty string
        decrypted_text = _wecom_decrypt_message(encrypt_content, encoding_aes_key, corp_id)
        if not decrypted_text:
            decrypted_text = _wecom_decrypt_message(encrypt_content, encoding_aes_key, "")
        if not decrypted_text:
            logging.error("[WECOM_BOT] Failed to decrypt message, encrypt_len=%d, encoding_aes_key_len=%d",
                          len(encrypt_content), len(encoding_aes_key))
            return error_response(
                status.HTTP_400_BAD_REQUEST,
                code="INVALID_PAYLOAD",
                message="Failed to decrypt WeCom Bot message",
            )

        logging.info("[WECOM_BOT] Decrypted text: %s", decrypted_text[:500] if decrypted_text else "(empty)")

        # Decrypted content is JSON for WeCom Bot
        try:
            msg_data = json.loads(decrypted_text)
            decrypted_json = decrypted_text
        except Exception as e:
            logging.warning("[WECOM_BOT] Decrypted content is not JSON, treating as plain text: %s", e)
            # Fallback: treat as plain text message
            msg_data = {"Content": decrypted_text, "MsgType": "text"}
            decrypted_json = decrypted_text
    else:
        # Plain mode (no encryption) - body is the message directly
        msg_data = body_json

    # Extract fields from the message JSON
    # WeCom Bot (智能机器人) message format:
    # {
    #   "msgid": "...",
    #   "aibotid": "...",
    #   "chatid": "...",
    #   "chattype": "group",
    #   "from": {"userid": "..."},
    #   "msgtype": "text",
    #   "response_url": "https://qyapi.weixin.qq.com/cgi-bin/aibot/response?response_code=...",
    #   "text": {"content": "@bot 消息内容"}
    # }
    msg_type = str(msg_data.get("msgtype") or msg_data.get("MsgType") or "text").lower()

    logging.debug("[WECOM_BOT] msg_data: %s", msg_data)

    # Extract sender info (lowercase field names)
    from_info = msg_data.get("from") or msg_data.get("From") or {}
    if isinstance(from_info, dict):
        from_user = from_info.get("userid") or from_info.get("UserId") or from_info.get("name") or from_info.get("Name") or ""
    else:
        from_user = str(from_info)

    # Extract content based on message type (lowercase field names)
    content = ""
    if msg_type == "text":
        text_obj = msg_data.get("text") or msg_data.get("Text") or {}
        if isinstance(text_obj, dict):
            content = text_obj.get("content") or text_obj.get("Content") or ""
        else:
            content = str(text_obj)
    elif msg_type == "image":
        image_obj = msg_data.get("image") or msg_data.get("Image") or {}
        content = f"[image] {image_obj.get('imageurl', image_obj.get('ImageUrl', ''))}"
    elif msg_type == "event":
        event_obj = msg_data.get("event") or msg_data.get("Event") or {}
        content = f"[event] {event_obj}"
    elif msg_type == "attachment":
        # Handle attachment messages
        attachment_obj = msg_data.get("attachment") or msg_data.get("Attachment") or {}
        content = f"[attachment] {attachment_obj}"
    else:
        # Other types: mixed, etc.
        content = f"[{msg_type}]"

    # Extract message metadata (lowercase field names)
    message_id = str(msg_data.get("msgid") or msg_data.get("MsgId") or "")
    create_time_raw = msg_data.get("create_time") or msg_data.get("CreateTime") or 0
    # response_url is required for replying to the message
    response_url = msg_data.get("response_url") or ""
    chat_id = msg_data.get("chatid") or msg_data.get("ChatId") or ""
    chat_type = msg_data.get("chattype") or msg_data.get("ChatType") or ""
    aibot_id = msg_data.get("aibotid") or ""

    # Convert CreateTime (epoch seconds) to timezone-aware datetime
    received_at = None
    try:
        ts = int(create_time_raw)
        if ts > 0:
            received_at = datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        received_at = None

    logging.info("[WECOM_BOT] Parsed message: msg_type=%s, from_user=%s, content_len=%d, message_id=%s, chat_id=%s",
                 msg_type, from_user, len(content), message_id, chat_id)

    # Store inbound message into wecom_inbox (producer stage)
    try:
        raw_payload = {
            "raw_json": body_text,
            "decrypted_json": decrypted_json,
            "parsed": msg_data,
            "platform_type": "wecom_bot",
            "chat_id": chat_id,
            "chat_type": chat_type,
            "aibot_id": aibot_id,
            "response_url": response_url,  # Required for replying to the message
        }

        inbox_record = WeComInbox(
            platform_id=platform.id,
            message_id=message_id or str(uuid.uuid4()),  # Generate ID if not provided
            source_type="wecom_bot",  # WeCom Bot (群机器人)
            from_user=from_user,
            open_kfid=chat_id or None,  # Use chat_id as open_kfid for wecom_bot
            msg_type=msg_type or "text",
            content=content or "",
            is_from_colleague=False,
            raw_payload=raw_payload,
            status="pending",
            received_at=received_at,
        )
        db.add(inbox_record)
        await db.commit()
        logging.info("[WECOM_BOT] Stored message: id=%s, platform_id=%s", inbox_record.id, platform.id)
    except IntegrityError as e:
        # Duplicate delivery; already stored. Treat as success.
        logging.info("[WECOM_BOT] Duplicate message detected for %s: %s", platform.id, e)
        await db.rollback()
    except Exception as e:
        logging.error("[WECOM_BOT] Store raw message failed for %s: %s", platform.id, e)
        await db.rollback()
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Immediate 200 OK; WeCom Bot expects a fast response.
    return {"ok": True}


async def _handle_feishu_bot_webhook(
    platform: Platform,
    request: Request,
    db: AsyncSession,
) -> dict[str, Any] | Response:
    """Handle Feishu Bot (飞书机器人) webhook POST callback.

    Feishu Bot uses JSON format:
    - URL verification: {"challenge": "...", "token": "...", "type": "url_verification"}
    - Event callback: {"encrypt": "..."} or plain JSON with event data

    Config structure:
    {
        "app_id": "cli_xxx",
        "app_secret": "xxx",
        "verification_token": "xxx",
        "encrypt_key": "xxx"  (optional)
    }

    Docs: https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case
    """
    config = platform.config or {}
    verification_token = (config.get("verification_token") or "").strip()
    encrypt_key = (config.get("encrypt_key") or "").strip()

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8") if raw_body else ""

    logging.info("[FEISHU_BOT] Received callback: platform_id=%s, body_length=%d", platform.id, len(body_text))
    logging.debug("[FEISHU_BOT] Raw body: %s", body_text[:500] if body_text else "(empty)")

    # Parse JSON body
    try:
        body_json = json.loads(body_text)
    except Exception as e:
        logging.error("[FEISHU_BOT] Failed to parse JSON: %s, body=%s", e, body_text[:200] if body_text else "(empty)")
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Invalid JSON payload",
            request_id=get_request_id(request),
        )

    # Check if this is an encrypted message
    encrypt_content = body_json.get("encrypt")
    event_data = body_json

    if encrypt_content:
        # Decrypt the message
        if not encrypt_key:
            logging.error("[FEISHU_BOT] encrypt_key not configured for platform %s", platform.id)
            return error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="ENCRYPTION_CONFIG_MISSING",
                message="encrypt_key is not configured for this Feishu Bot platform",
            )

        decrypted_text = feishu_decrypt_message(encrypt_content, encrypt_key)
        if not decrypted_text:
            logging.error("[FEISHU_BOT] Failed to decrypt message")
            return error_response(
                status.HTTP_400_BAD_REQUEST,
                code="INVALID_PAYLOAD",
                message="Failed to decrypt Feishu Bot message",
            )

        logging.debug("[FEISHU_BOT] Decrypted text: %s", decrypted_text[:500] if decrypted_text else "(empty)")

        try:
            event_data = json.loads(decrypted_text)
        except Exception as e:
            logging.error("[FEISHU_BOT] Failed to parse decrypted JSON: %s", e)
            return error_response(
                status.HTTP_400_BAD_REQUEST,
                code="INVALID_PAYLOAD",
                message="Decrypted content is not valid JSON",
            )

    # Handle URL verification challenge
    if event_data.get("type") == "url_verification":
        challenge = event_data.get("challenge", "")
        token = event_data.get("token", "")
        logging.info("[FEISHU_BOT] URL verification challenge for platform %s", platform.id)

        # Verify token if configured
        if verification_token and token != verification_token:
            logging.warning("[FEISHU_BOT] Token mismatch: expected=%s, got=%s", verification_token, token)
            return error_response(
                status.HTTP_403_FORBIDDEN,
                code="TOKEN_MISMATCH",
                message="Verification token mismatch",
            )

        return {"challenge": challenge}

    # Verify signature if X-Lark-Signature header is present
    signature = request.headers.get("X-Lark-Signature") or ""
    timestamp = request.headers.get("X-Lark-Request-Timestamp") or ""
    nonce = request.headers.get("X-Lark-Request-Nonce") or ""

    if signature and encrypt_key:
        if not feishu_verify_signature(timestamp, nonce, encrypt_key, body_text, signature):
            logging.warning("[FEISHU_BOT] Signature verification failed")
            return error_response(
                status.HTTP_403_FORBIDDEN,
                code="SIGNATURE_MISMATCH",
                message="Signature verification failed",
            )

    # Handle event callback
    schema = event_data.get("schema") or ""
    header = event_data.get("header") or {}
    event = event_data.get("event") or {}

    event_type = header.get("event_type") or ""
    logging.info("[FEISHU_BOT] Event type: %s, schema: %s", event_type, schema)

    # Only process message receive events
    if event_type != "im.message.receive_v1":
        logging.info("[FEISHU_BOT] Ignoring non-message event: %s", event_type)
        return {"ok": True}

    # Extract message data
    message = event.get("message") or {}
    sender = event.get("sender") or {}

    message_id = message.get("message_id") or ""
    chat_id = message.get("chat_id") or ""
    chat_type = message.get("chat_type") or "p2p"  # p2p or group
    msg_type = message.get("message_type") or "text"
    create_time = message.get("create_time") or ""

    # Sender info
    sender_id = sender.get("sender_id") or {}
    from_user = sender_id.get("open_id") or sender_id.get("user_id") or sender_id.get("union_id") or ""
    from_user_type = "open_id"
    if sender_id.get("user_id"):
        from_user_type = "user_id"
    elif sender_id.get("union_id"):
        from_user_type = "union_id"

    # Extract content based on message type
    content_str = message.get("content") or "{}"
    content = ""
    try:
        content_json = json.loads(content_str)
        if msg_type == "text":
            raw_text = content_json.get("text") or ""
            content = feishu_clean_message_text(raw_text)
        elif msg_type == "post":
            # Rich text - extract title or first text element
            content = content_json.get("title") or str(content_json)
        elif msg_type == "image":
            content = f"[image] {content_json.get('image_key', '')}"
        elif msg_type == "file":
            content = f"[file] {content_json.get('file_key', '')}"
        else:
            content = f"[{msg_type}] {content_str[:200]}"
    except Exception:
        content = content_str

    # Convert create_time (milliseconds) to datetime
    received_at = None
    try:
        ts = int(create_time)
        if ts > 0:
            # Feishu uses milliseconds
            received_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    except Exception:
        received_at = None

    logging.info("[FEISHU_BOT] Parsed message: message_id=%s, from_user=%s, chat_type=%s, msg_type=%s, content_len=%d",
                 message_id, from_user, chat_type, msg_type, len(content))

    if not message_id:
        logging.warning("[FEISHU_BOT] Missing message_id, cannot store")
        return {"ok": True}

    # Store inbound message into feishu_inbox
    try:
        raw_payload = {
            "raw_json": body_text,
            "decrypted_json": decrypted_text if encrypt_content else None,
            "event_data": event_data,
            "message_id": message_id,  # Important for reply API
        }

        inbox_record = FeishuInbox(
            platform_id=platform.id,
            message_id=message_id,
            from_user=from_user,
            from_user_type=from_user_type,
            chat_id=chat_id or None,
            chat_type=chat_type,
            msg_type=msg_type,
            content=content or "",
            raw_payload=raw_payload,
            status="pending",
            received_at=received_at,
        )
        db.add(inbox_record)
        await db.commit()
        logging.info("[FEISHU_BOT] Stored message: id=%s, platform_id=%s", inbox_record.id, platform.id)
    except IntegrityError as e:
        logging.info("[FEISHU_BOT] Duplicate message detected for %s: %s", platform.id, e)
        await db.rollback()
    except Exception as e:
        logging.error("[FEISHU_BOT] Store raw message failed for %s: %s", platform.id, e)
        await db.rollback()
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {"ok": True}


async def _handle_dingtalk_bot_webhook(
    platform: Platform,
    request: Request,
    db: AsyncSession,
) -> dict[str, Any] | Response:
    """Handle DingTalk Bot (钉钉机器人) webhook POST callback.

    DingTalk Bot uses JSON format with signature verification:
    - X-DingTalk-Timestamp: Timestamp in milliseconds
    - X-DingTalk-Sign: HMAC-SHA256 signature

    Config structure:
    {
        "app_key": "xxx",
        "app_secret": "xxx",
        "robot_code": "xxx",
        "aes_key": "xxx",  (optional, for encrypted messages)
        "token": "xxx"     (optional)
    }

    Docs: https://open.dingtalk.com/document/orgapp/receive-message
    """
    config = platform.config or {}
    app_secret = (config.get("app_secret") or "").strip()

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8") if raw_body else ""

    logging.info("[DINGTALK_BOT] Received callback: platform_id=%s, body_length=%d", platform.id, len(body_text))
    logging.debug("[DINGTALK_BOT] Raw body: %s", body_text[:5000] if body_text else "(empty)")

    # Verify signature if app_secret is configured
    timestamp = request.headers.get("X-DingTalk-Timestamp") or request.headers.get("timestamp") or ""
    sign = request.headers.get("X-DingTalk-Sign") or request.headers.get("sign") or ""
    print("request.headers---->", request.headers)
    if app_secret and timestamp and sign:
        if not dingtalk_verify_signature(timestamp, sign, app_secret):
            logging.warning("[DINGTALK_BOT] Signature verification failed")
            return error_response(
                status.HTTP_403_FORBIDDEN,
                code="SIGNATURE_MISMATCH",
                message="Signature verification failed",
                request_id=get_request_id(request),
            )

    # Parse JSON body
    try:
        body_json = json.loads(body_text)
    except Exception as e:
        logging.error("[DINGTALK_BOT] Failed to parse JSON: %s, body=%s", e, body_text[:200] if body_text else "(empty)")
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Invalid JSON payload",
            request_id=get_request_id(request),
        )

    # Extract message data
    # DingTalk message structure:
    # {
    #   "conversationId": "xxx",
    #   "conversationType": "1" or "2",
    #   "msgId": "xxx",
    #   "msgtype": "text",
    #   "text": {"content": "..."},
    #   "senderId": "xxx",
    #   "senderNick": "xxx",
    #   "sessionWebhook": "https://...",
    #   "sessionWebhookExpiredTime": 1234567890000,
    #   ...
    # }

    conversation_id = body_json.get("conversationId") or ""
    conversation_type = str(body_json.get("conversationType") or "1")  # 1=single, 2=group
    msg_id = body_json.get("msgId") or ""
    msg_type = body_json.get("msgtype") or "text"
    sender_id = body_json.get("senderId") or body_json.get("senderStaffId") or ""
    sender_nick = body_json.get("senderNick") or ""
    session_webhook = body_json.get("sessionWebhook") or ""
    session_webhook_expired_time = body_json.get("sessionWebhookExpiredTime")
    create_at = body_json.get("createAt")  # Timestamp in milliseconds

    # Extract content based on message type
    content = ""
    if msg_type == "text":
        text_obj = body_json.get("text") or {}
        content = text_obj.get("content") or ""
    elif msg_type == "picture":
        picture_obj = body_json.get("picture") or {}
        content = f"[picture] {picture_obj.get('picURL', '')}"
    elif msg_type == "richText":
        rich_text = body_json.get("richText") or []
        content = f"[richText] {json.dumps(rich_text, ensure_ascii=False)[:500]}"
    elif msg_type == "audio":
        audio_obj = body_json.get("audio") or {}
        content = f"[audio] duration={audio_obj.get('duration', 0)}"
    elif msg_type == "file":
        file_obj = body_json.get("file") or {}
        content = f"[file] {file_obj.get('fileName', '')}"
    else:
        content = f"[{msg_type}]"

    # Convert createAt (milliseconds) to datetime
    received_at = None
    try:
        if create_at:
            ts = int(create_at)
            if ts > 0:
                received_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    except Exception:
        received_at = None

    logging.info("[DINGTALK_BOT] Parsed message: msg_id=%s, sender=%s, conv_type=%s, msg_type=%s, content_len=%d",
                 msg_id, sender_id, conversation_type, msg_type, len(content))

    if not msg_id:
        # Generate a message ID if not provided
        msg_id = str(uuid.uuid4())
        logging.warning("[DINGTALK_BOT] Missing msgId, generated: %s", msg_id)

    if not sender_id:
        logging.warning("[DINGTALK_BOT] Missing senderId, cannot store message")
        return {"ok": True}

    # Store inbound message into dingtalk_inbox
    try:
        raw_payload = {
            "raw_json": body_text,
            "body_json": body_json,
            "session_webhook": session_webhook,  # Important for replying
        }

        inbox_record = DingTalkInbox(
            platform_id=platform.id,
            message_id=msg_id,
            from_user=sender_id,
            sender_nick=sender_nick or None,
            conversation_id=conversation_id or None,
            conversation_type=conversation_type,
            msg_type=msg_type,
            content=content or "",
            session_webhook=session_webhook or None,
            session_webhook_expired_time=session_webhook_expired_time,
            raw_payload=raw_payload,
            status="pending",
            received_at=received_at,
        )
        db.add(inbox_record)
        await db.commit()
        logging.info("[DINGTALK_BOT] Stored message: id=%s, platform_id=%s", inbox_record.id, platform.id)
    except IntegrityError as e:
        logging.info("[DINGTALK_BOT] Duplicate message detected for %s: %s", platform.id, e)
        await db.rollback()
    except Exception as e:
        logging.error("[DINGTALK_BOT] Store raw message failed for %s: %s", platform.id, e)
        await db.rollback()
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {"ok": True}


async def _handle_wukongim_webhook(
    platform: Platform,
    request: Request,
    db: AsyncSession,
    messages: Optional[list[dict[str, Any]]] = None,
    event: Optional[str] = None,
) -> dict[str, Any] | Response:
    """Handle WuKongIM webhook POST callback for a website platform.

    According to WuKongIM docs:
    - The event is provided via query parameter `event` (e.g., msg.notify)
    - The request body is a JSON array of message objects

    Producer stage: iterate messages and store a WuKongIMInbox row for each.
    """
    event = event or request.query_params.get("event")
    if event != "msg.notify":
        # Ignore non-message events but reply OK to acknowledge
        return {"ok": True}

    # Body is a JSON array of messages
    if messages is None:
        try:
            messages = await request.json()
        except Exception:
            return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_PAYLOAD", message="Invalid JSON payload", request_id=get_request_id(request))

    if not isinstance(messages, list):
        return error_response(status.HTTP_400_BAD_REQUEST, code="INVALID_PAYLOAD", message="Expected an array of messages", request_id=get_request_id(request))

    for message in messages:
        if not isinstance(message, dict):
            continue  # skip invalid entries
        try:
            message_id = str(message.get("message_id"))
            client_msg_no = message.get("client_msg_no")
            from_uid = str(message.get("from_uid") or "")
            channel_id = str(message.get("channel_id") or "")
            channel_type = int(message.get("channel_type") or 0)
            message_seq = int(message.get("message_seq")) if message.get("message_seq") is not None else 0
            timestamp = int(message.get("timestamp") or 0)
            payload_b64 = str(message.get("payload") or "")
            platform_open_id = message.get("platform_open_id")  # Extract platform_open_id
        except Exception:
            # Skip this message if fields are malformed
            continue

        # Skip messages sent by staff/customer service (from_uid suffix "-staff")
        if from_uid and from_uid.endswith("-staff"):
            logging.info("[WUKONGIM] Skipping staff message: from_uid=%s message_id=%s", from_uid, message_id)
            continue

        # Required minimal fields
        if not (message_id and from_uid and channel_id and channel_type and payload_b64):
            continue

        try:
            # Store decoded payload (plain text/JSON) instead of base64
            try:
                content_bytes = base64.b64decode(payload_b64 or "") if payload_b64 else b""
                decoded_payload = content_bytes.decode("utf-8", errors="replace")
            except Exception:
                decoded_payload = ""

            inbox_record = WuKongIMInbox(
                platform_id=platform.id,
                message_id=message_id,
                client_msg_no=client_msg_no,
                from_uid=from_uid,
                channel_id=channel_id,
                channel_type=channel_type,
                message_seq=message_seq,
                timestamp=timestamp,
                payload=decoded_payload,
                platform_open_id=platform_open_id,
                raw_body=message,
                status="pending",
                retry_count=0,
                fetched_at=datetime.now(timezone.utc),
            )
            db.add(inbox_record)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Duplicate; treat as success for that one message
            continue
        except Exception:
            await db.rollback()
            # If one message fails to store, continue with others; overall ack OK
            continue

    return {"ok": True}



async def _handle_telegram_webhook(
    platform: Platform,
    request: Request,
    db: AsyncSession,
) -> dict[str, Any] | Response:
    """Handle Telegram Bot webhook POST callback.

    Telegram sends updates as JSON to the webhook URL.
    Updates contain messages, edited_messages, channel_posts, etc.

    Config structure:
    {
        "bot_token": "123456:ABC-DEF...",
        "webhook_secret": "optional-secret-token"
    }

    Docs: https://core.telegram.org/bots/api#update
    """
    config = platform.config or {}
    webhook_secret = (config.get("webhook_secret") or "").strip()

    # Verify secret token if configured
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or ""
    if webhook_secret and not telegram_verify_secret_token(secret_header, webhook_secret):
        logging.warning("[TELEGRAM] Secret token verification failed for platform %s", platform.id)
        return error_response(
            status.HTTP_403_FORBIDDEN,
            code="SECRET_TOKEN_MISMATCH",
            message="Secret token verification failed",
            request_id=get_request_id(request),
        )

    raw_body = await request.body()
    body_text = raw_body.decode("utf-8") if raw_body else ""

    logging.info("[TELEGRAM] Received webhook: platform_id=%s, body_length=%d", platform.id, len(body_text))
    logging.debug("[TELEGRAM] Raw body: %s", body_text[:500] if body_text else "(empty)")

    # Parse JSON body
    try:
        update = json.loads(body_text)
    except Exception as e:
        logging.error("[TELEGRAM] Failed to parse JSON: %s, body=%s", e, body_text[:200] if body_text else "(empty)")
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            code="INVALID_PAYLOAD",
            message="Invalid JSON payload",
            request_id=get_request_id(request),
        )

    # Extract update_id for deduplication
    update_id = update.get("update_id")

    # Extract message from the update
    message = extract_message_from_update(update)
    if not message:
        logging.info("[TELEGRAM] No message in update, ignoring (update_id=%s)", update_id)
        return {"ok": True}

    # Extract message data
    message_id = str(message.get("message_id", ""))
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    chat_type = get_chat_type(message)

    # Get sender info
    from_user_id, from_username, from_display_name = get_sender_info(message)

    # Extract content
    content = extract_text_from_message(message)
    msg_type = "text"
    if "photo" in message:
        msg_type = "photo"
    elif "document" in message:
        msg_type = "document"
    elif "voice" in message:
        msg_type = "voice"
    elif "video" in message:
        msg_type = "video"
    elif "audio" in message:
        msg_type = "audio"
    elif "sticker" in message:
        msg_type = "sticker"
    elif "location" in message:
        msg_type = "location"
    elif "contact" in message:
        msg_type = "contact"
    elif "poll" in message:
        msg_type = "poll"

    # Convert message.date (Unix timestamp) to datetime
    received_at = None
    try:
        msg_date = message.get("date")
        if msg_date:
            received_at = datetime.fromtimestamp(int(msg_date), tz=timezone.utc)
    except Exception:
        received_at = None

    logging.info(
        "[TELEGRAM] Parsed message: message_id=%s, chat_id=%s, chat_type=%s, from_user=%s, content_len=%d",
        message_id, chat_id, chat_type, from_user_id, len(content)
    )

    if not message_id or not chat_id:
        logging.warning("[TELEGRAM] Missing message_id or chat_id")
        return {"ok": True}

    if not from_user_id:
        logging.warning("[TELEGRAM] Missing from_user, cannot store message")
        return {"ok": True}

    # Store inbound message into telegram_inbox
    try:
        raw_payload = {
            "update": update,
            "message": message,
        }

        inbox_record = TelegramInbox(
            platform_id=platform.id,
            message_id=message_id,
            update_id=update_id,
            from_user=from_user_id,
            from_username=from_username,
            from_display_name=from_display_name,
            chat_id=chat_id,
            chat_type=chat_type,
            msg_type=msg_type,
            content=content or "",
            raw_payload=raw_payload,
            status="pending",
            received_at=received_at,
        )
        db.add(inbox_record)
        await db.commit()
        logging.info("[TELEGRAM] Stored message: id=%s, platform_id=%s", inbox_record.id, platform.id)
    except IntegrityError as e:
        logging.info("[TELEGRAM] Duplicate message detected for %s: %s", platform.id, e)
        await db.rollback()
    except Exception as e:
        logging.error("[TELEGRAM] Store raw message failed for %s: %s", platform.id, e)
        await db.rollback()
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {"ok": True}


@router.post("/v1/platforms/callback/{platform_api_key}", responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}, 501: {"model": ErrorResponse}})
async def platforms_callback(platform_api_key: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Unified platform callback endpoint for WeCom and WuKongIM.

    - For WeCom: validate signature, parse XML, store to wecom_inbox
    - For WuKongIM (platform type 'website'): read `event` from query, parse body array, store to wukongim_inbox
    """
    # Lookup platform by api_key
    platform = await db.scalar(
        select(Platform).where(Platform.api_key == platform_api_key, Platform.is_active.is_(True))
    )
    if not platform:
        logging.warning("Callback for unknown platform: %s", platform_api_key)
        return error_response(status.HTTP_404_NOT_FOUND, code="PLATFORM_NOT_FOUND", message="Platform not found", request_id=get_request_id(request))

    platform_type = (platform.type or "").lower()
    logging.info("[CALLBACK] Routing callback for platform_id=%s, type=%s, api_key=%s",
                 platform.id, platform_type, platform_api_key[:20] + "...")

    # Platform-type-specific routing
    if platform_type == "wecom":
        return await _handle_wecom_webhook(platform=platform, request=request, db=db)
    if platform_type == "wecom_bot":
        return await _handle_wecom_bot_webhook(platform=platform, request=request, db=db)
    if platform_type == "feishu_bot":
        return await _handle_feishu_bot_webhook(platform=platform, request=request, db=db)
    if platform_type == "dingtalk_bot":
        return await _handle_dingtalk_bot_webhook(platform=platform, request=request, db=db)
    if platform_type == "website":
        return await _handle_wukongim_webhook(platform=platform, request=request, db=db)
    if platform_type == "telegram":
        return await _handle_telegram_webhook(platform=platform, request=request, db=db)

    # Unsupported platform type for this endpoint
    return error_response(status.HTTP_404_NOT_FOUND, code="PLATFORM_TYPE_UNSUPPORTED", message=f"Unsupported platform type: {platform.type}", request_id=get_request_id(request))

