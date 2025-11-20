"""Seed default platform types into ai_platform_types table (idempotent).

This runs on service startup and performs an upsert by unique key `type` to
avoid duplicate rows while keeping names/icons up to date.
"""
from __future__ import annotations

from typing import List, Dict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import startup_log
from app.models.platform import PlatformTypeDefinition


SEED_PLATFORM_TYPES: List[Dict[str, object]] = [
    # Supported platform types
    {
        "type": "wecom",
        "name": "微信客服",
        "name_en": "WeCom",
        "is_supported": True,
    },
    {
        "type": "website",
        "name": "网站小部件",
        "name_en": "Website",
        "is_supported": True,
    },
    {
        "type": "email",
        "name": "邮件",
        "name_en": "Email",
        "is_supported": True,
    },
    {
        "type": "custom",
        "name": "自定义",
        "name_en": "Custom",
        "is_supported": True,
    },
    # Other platform types from PlatformType enum (currently not supported)
    {
        "type": "wechat",
        "name": "微信公众号",
        "name_en": "WeChat Official Account",
        "is_supported": False,
    },
    {
        "type": "whatsapp",
        "name": "WhatsApp",
        "name_en": "WhatsApp",
        "is_supported": False,
    },
    {
        "type": "telegram",
        "name": "Telegram",
        "name_en": "Telegram",
        "is_supported": False,
    },
    {
        "type": "sms",
        "name": "短信",
        "name_en": "SMS",
        "is_supported": False,
    },
    {
        "type": "facebook",
        "name": "Facebook",
        "name_en": "Facebook",
        "is_supported": False,
    },
    {
        "type": "instagram",
        "name": "Instagram",
        "name_en": "Instagram",
        "is_supported": False,
    },
    {
        "type": "twitter",
        "name": "Twitter",
        "name_en": "Twitter",
        "is_supported": False,
    },
    {
        "type": "linkedin",
        "name": "LinkedIn",
        "name_en": "LinkedIn",
        "is_supported": False,
    },
    {
        "type": "discord",
        "name": "Discord",
        "name_en": "Discord",
        "is_supported": False,
    },
    {
        "type": "slack",
        "name": "Slack",
        "name_en": "Slack",
        "is_supported": False,
    },
    {
        "type": "teams",
        "name": "Microsoft Teams",
        "name_en": "Microsoft Teams",
        "is_supported": False,
    },
    {
        "type": "phone",
        "name": "电话",
        "name_en": "Phone",
        "is_supported": False,
    },
    {
        "type": "douyin",
        "name": "抖音",
        "name_en": "Douyin",
        "is_supported": False,
    },
    {
        "type": "tiktok",
        "name": "TikTok",
        "name_en": "TikTok",
        "is_supported": False,
    },
]


def ensure_platform_types_seed() -> None:
    """Ensure default platform types exist; upsert by unique `type`."""
    db: Session = SessionLocal()
    try:
        for row in SEED_PLATFORM_TYPES:
            stmt = insert(PlatformTypeDefinition).values(
                type=row["type"],
                name=row["name"],
                is_supported=row["is_supported"],
                name_en=row.get("name_en"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[PlatformTypeDefinition.type],
                set_={
                    "name": stmt.excluded.name,
                    "is_supported": stmt.excluded.is_supported,
                    "name_en": stmt.excluded.name_en,
                },
            )
            db.execute(stmt)
        db.commit()
        startup_log("✅ Platform types seeded (idempotent)")
    except Exception as e:  # pragma: no cover
        db.rollback()
        startup_log(f"⚠️  Failed to seed platform types: {e}")
    finally:
        db.close()

