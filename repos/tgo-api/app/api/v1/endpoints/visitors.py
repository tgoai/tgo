"""Visitor endpoints."""

import hashlib
import mimetypes
import os
import re
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.security import verify_token

from app.services.wukongim_client import wukongim_client
from app.services.visitor_notifications import notify_visitor_profile_updated
from app.utils.intent import localize_visitor_response_intent
from app.utils.const import CHANNEL_TYPE_CUSTOMER_SERVICE, MEMBER_TYPE_VISITOR
from app.utils.request import get_client_ip, get_client_language
from app.services.geoip_service import geoip_service
from app.utils.encoding import (
    build_visitor_channel_id,
    parse_visitor_channel_id,
)


from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_current_active_user, get_user_language, UserLanguage, require_permission
from app.models import (
    Platform,
    Staff,
    Visitor,
    VisitorActivity,
    VisitorSystemInfo,
    VisitorTag,
    ChannelMember,
)
from app.schemas import (
    VisitorAIInsightResponse,
    VisitorAIProfileResponse,
    VisitorActivityResponse,
    VisitorAttributesUpdate,
    VisitorAvatarUploadResponse,
    VisitorCreate,
    VisitorListParams,
    VisitorListResponse,
    VisitorResponse,
    VisitorBasicResponse,
    VisitorSystemInfoRequest,
    VisitorSystemInfoResponse,
    VisitorUpdate,
    TagResponse,
    VisitorActivityCreateRequest,
    VisitorActivityCreateResponse,
)
from app.schemas.visitor import set_visitor_display_nickname, set_visitor_list_display_nickname
from app.schemas.tag import set_tag_list_display_name

from app.schemas.wukongim import WuKongIMChannelMessageSyncResponse


class VisitorRegisterRequest(BaseModel):
    platform_api_key: str
    # Optional visitor identifier on the platform (maps to Visitor.platform_open_id)
    platform_open_id: Optional[str] = None
    # Optional profile fields (aligned with VisitorBase)
    name: Optional[str] = None
    nickname: Optional[str] = Field(None, description="Visitor nickname in English")
    nickname_zh: Optional[str] = Field(None, description="Visitor nickname in Chinese")
    avatar_url: Optional[str] = Field(None, description="Visitor avatar URL")
    phone_number: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None
    custom_attributes: dict[str, Optional[str]] = {}
    system_info: Optional[VisitorSystemInfoRequest] = Field(
        None,
        description="Visitor system metadata payload (browser, OS, timestamps, etc.)",
    )
    timezone: Optional[str] = Field(
        None,
        max_length=50,
        description="Visitor timezone (e.g., 'Asia/Shanghai', 'America/New_York')",
    )
    language: Optional[str] = Field(
        None,
        max_length=10,
        description="Visitor preferred language code (e.g., 'en', 'zh-CN')",
    )
    ip_address: Optional[str] = Field(
        None,
        max_length=45,
        description="Visitor IP address (if not provided, will be extracted from request headers)",
    )


class VisitorRegisterResponse(VisitorResponse):
    channel_id: str
    channel_type: int = 2
    im_token: str

logger = get_logger("endpoints.visitors")
router = APIRouter()

# Predefined array of realistic visitor names for default visitor generation
DEFAULT_VISITOR_NAMES = [
    "Alex Chen",
    "Sarah Johnson",
    "Michael Zhang",
    "Emma Wilson",
    "David Kumar",
    "Jessica Martinez",
    "Ryan O'Connor",
    "Sophia Lee",
    "James Anderson",
    "Olivia Brown",
    "Daniel Garcia",
    "Isabella Rodriguez",
    "Matthew Taylor",
    "Ava Thompson",
    "Christopher White",
    "Mia Harris",
    "Andrew Clark",
    "Emily Lewis",
    "Joshua Walker",
    "Charlotte Hall",
    "Kevin Young",
    "Amelia Allen",
    "Brandon King",
    "Harper Wright",
    "Tyler Scott",
    "Evelyn Green",
    "Justin Adams",
    "Abigail Baker",
    "Nathan Nelson",
    "Ella Carter",
]

# Chinese nickname components
CUSTOMER_SERVICE_ADJECTIVES_ZH = [
    "星光",
    "温暖",
    "清晨",
    "晴空",
    "暖阳",
    "微风",
    "云端",
    "静谧",
    "灵动",
    "璀璨",
    "悠然",
    "暮色",
]

CUSTOMER_SERVICE_NOUNS_ZH = [
    "海豚",
    "星猫",
    "向日葵",
    "松果",
    "雨燕",
    "晨露",
    "珊瑚",
    "雪狐",
    "轻舟",
    "薰衣草",
    "流萤",
    "橄榄树",
]

# English nickname components
CUSTOMER_SERVICE_ADJECTIVES_EN = [
    "Starry",
    "Warm",
    "Morning",
    "Sunny",
    "Bright",
    "Breezy",
    "Cloud",
    "Quiet",
    "Swift",
    "Shiny",
    "Calm",
    "Twilight",
]

CUSTOMER_SERVICE_NOUNS_EN = [
    "Dolphin",
    "Cat",
    "Sunflower",
    "Pine",
    "Swallow",
    "Dew",
    "Coral",
    "Fox",
    "Boat",
    "Lavender",
    "Firefly",
    "Olive",
]


def _generate_default_visitor_name(visitor_id: str) -> str:
    """
    Generate a deterministic visitor name based on the visitor_id.

    Args:
        visitor_id: The string ID of the visitor

    Returns:
        A name selected from the DEFAULT_VISITOR_NAMES array
    """
    # Convert string to bytes and hash it
    id_bytes = visitor_id.encode('utf-8')
    hash_digest = hashlib.sha256(id_bytes).digest()

    # Convert first 4 bytes to an integer for indexing
    index = int.from_bytes(hash_digest[:4], byteorder='big') % len(DEFAULT_VISITOR_NAMES)

    return DEFAULT_VISITOR_NAMES[index]


def _generate_customer_service_nickname(identifier: Optional[str]) -> tuple[str, str]:
    """
    Generate friendly fallback nicknames for visitor-facing scenarios.

    Combines curated adjective/noun pairs for flavor and adds a short suffix
    derived from the identifier to keep names stable yet varied.

    Returns:
        A tuple of (english_nickname, chinese_nickname)
    """
    base_identifier = (identifier or "").strip()
    if not base_identifier:
        base_identifier = datetime.utcnow().isoformat()

    digest = hashlib.sha256(base_identifier.encode("utf-8")).digest()

    # English nickname
    adjective_en = CUSTOMER_SERVICE_ADJECTIVES_EN[digest[0] % len(CUSTOMER_SERVICE_ADJECTIVES_EN)]
    noun_en = CUSTOMER_SERVICE_NOUNS_EN[digest[1] % len(CUSTOMER_SERVICE_NOUNS_EN)]

    # Chinese nickname
    adjective_zh = CUSTOMER_SERVICE_ADJECTIVES_ZH[digest[0] % len(CUSTOMER_SERVICE_ADJECTIVES_ZH)]
    noun_zh = CUSTOMER_SERVICE_NOUNS_ZH[digest[1] % len(CUSTOMER_SERVICE_NOUNS_ZH)]

    suffix_value = int.from_bytes(digest[2:4], byteorder="big")
    suffix = format(suffix_value, "x").upper()[:3]

    nickname_en = f"{adjective_en}{noun_en}{suffix}"
    nickname_zh = f"{adjective_zh}{noun_zh}{suffix}"

    return nickname_en, nickname_zh


def _resolve_visitor_nickname(
    provided_nickname: Optional[str],
    provided_nickname_zh: Optional[str],
    identifier: Optional[str],
) -> tuple[str, str]:
    """
    Return cleaned nicknames or generate defaults when blank.

    Args:
        provided_nickname: English nickname from request
        provided_nickname_zh: Chinese nickname from request
        identifier: Identifier used to generate deterministic nicknames

    Returns:
        A tuple of (english_nickname, chinese_nickname)
    """
    nickname_en = (provided_nickname or "").strip()
    nickname_zh = (provided_nickname_zh or "").strip()

    # If both are provided, return them
    if nickname_en and nickname_zh:
        return nickname_en, nickname_zh

    # Generate defaults for missing nicknames
    generated_en, generated_zh = _generate_customer_service_nickname(identifier)

    return nickname_en or generated_en, nickname_zh or generated_zh


async def _ensure_visitor_channel(
    db: Session,
    visitor: Visitor,
    platform: Platform,
) -> None:
    """
    Ensure WuKongIM channel exists for a visitor.

    This function creates the channel and channel member records if they don't exist.
    It's idempotent - safe to call multiple times for the same visitor.
    
    Only the visitor is added as initial subscriber. Staff will be added
    when they are assigned to the visitor via transfer_to_staff.

    Args:
        db: Database session
        visitor: Visitor object
        platform: Platform object

    Raises:
        Exception: If WuKongIM channel creation fails (logged but not raised)
    """
    channel_id = build_visitor_channel_id(visitor.id)

    try:
        # Only visitor as initial subscriber
        subscribers = [str(visitor.id)]

        # Check if visitor is already a channel member
        existing_visitor_member = (
            db.query(ChannelMember)
            .filter(
                ChannelMember.project_id == platform.project_id,
                ChannelMember.channel_id == channel_id,
                ChannelMember.member_id == visitor.id,
                ChannelMember.deleted_at.is_(None),
            )
            .first()
        )

        # Add visitor as channel member if not exists
        if not existing_visitor_member:
            visitor_member = ChannelMember(
                project_id=platform.project_id,
                channel_id=channel_id,
                channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
                member_id=visitor.id,
                member_type=MEMBER_TYPE_VISITOR,
            )
            db.add(visitor_member)

        # Ensure channel exists in WuKongIM and then commit membership
        await wukongim_client.create_channel(
            channel_id=channel_id,
            channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
            subscribers=subscribers,
        )
        if not existing_visitor_member:
            db.commit()

        logger.info(
            "WuKongIM channel ensured for visitor",
            extra={
                "channel_id": channel_id,
                "channel_type": CHANNEL_TYPE_CUSTOMER_SERVICE,
                "subscribers_count": len(subscribers),
                "visitor_id": str(visitor.id),
            },
        )
    except Exception as e:
        # Roll back any pending channel membership inserts if WuKongIM call fails
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(
            f"Failed to create WuKongIM channel for visitor: {e}",
            extra={
                "channel_id": channel_id,
                "channel_type": CHANNEL_TYPE_CUSTOMER_SERVICE,
                "visitor_id": str(visitor.id),
            },
        )
        # Don't raise - visitor is still created, channel can be created later


async def _create_visitor_with_channel(
    db: Session,
    platform: Platform,
    platform_open_id: Optional[str] = None,
    name: Optional[str] = None,
    nickname: Optional[str] = None,
    nickname_zh: Optional[str] = None,
    avatar_url: Optional[str] = None,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    job_title: Optional[str] = None,
    source: Optional[str] = None,
    note: Optional[str] = None,
    custom_attributes: Optional[dict[str, Optional[str]]] = None,
    timezone: Optional[str] = None,
    language: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Visitor:
    """
    Create a new visitor with WuKongIM channel setup.

    This is a shared internal method used by chat_completion_openai_compatible,
    register_visitor, and other endpoints that need visitor auto-registration.

    Args:
        db: Database session
        platform: Platform object
        platform_open_id: Platform open ID for the visitor. If None, visitor.id will be used.
        name: Optional visitor name
        nickname: Optional visitor nickname in English (will be auto-generated if not provided)
        nickname_zh: Optional visitor nickname in Chinese (will be auto-generated if not provided)
        avatar_url: Optional avatar URL
        phone_number: Optional phone number
        email: Optional email
        company: Optional company
        job_title: Optional job title
        source: Optional source
        note: Optional note
        custom_attributes: Optional custom attributes dict
        timezone: Optional visitor timezone (e.g., 'Asia/Shanghai')
        language: Optional visitor language code (e.g., 'en', 'zh-CN')
        ip_address: Optional visitor IP address

    Returns:
        Created Visitor object with WuKongIM channel set up

    Raises:
        Exception: If WuKongIM channel creation fails (logged but not raised)
    """
    # Handle case where platform_open_id is not provided
    # We need to create visitor first to get its ID, then use it as platform_open_id
    use_visitor_id_as_open_id = not platform_open_id
    
    if use_visitor_id_as_open_id:
        # Use a temporary placeholder, will be updated after flush
        initial_platform_open_id = f"pending-{uuid.uuid4().hex}"
    else:
        initial_platform_open_id = platform_open_id
    
    # Resolve nicknames (generate if not provided)
    resolved_nickname, resolved_nickname_zh = _resolve_visitor_nickname(
        nickname, nickname_zh, platform_open_id or None
    )
    
    # Lookup geolocation from IP address
    geo_location = geoip_service.lookup(ip_address)

    # Create visitor record
    visitor = Visitor(
        project_id=platform.project_id,
        platform_id=platform.id,
        platform_open_id=initial_platform_open_id,
        name=name,
        nickname=resolved_nickname,
        nickname_zh=resolved_nickname_zh,
        avatar_url=avatar_url,
        phone_number=phone_number,
        email=email,
        company=company,
        job_title=job_title,
        source=source,
        note=note,
        custom_attributes=custom_attributes or {},
        timezone=timezone,
        language=language,
        ip_address=ip_address,
        geo_country=geo_location.country,
        geo_country_code=geo_location.country_code,
        geo_region=geo_location.region,
        geo_city=geo_location.city,
        geo_isp=geo_location.isp,
    )
    db.add(visitor)
    
    if use_visitor_id_as_open_id:
        # Flush to get visitor ID, then update platform_open_id
        db.flush()
        visitor.platform_open_id = str(visitor.id)
    
    db.commit()
    db.refresh(visitor)

    # Create WuKongIM channel with admin staff members as subscribers
    await _ensure_visitor_channel(db, visitor, platform)

    return visitor


def _upsert_visitor_system_info(
    db: Session,
    visitor: Visitor,
    platform: Platform,
    system_info_payload: Optional[VisitorSystemInfoRequest],
) -> bool:
    """
    Create or update the visitor's system info record based on payload.

    Returns True if any data was applied.
    """
    system_info = visitor.system_info
    created = False
    if not system_info:
        system_info = VisitorSystemInfo(
            project_id=platform.project_id,
            visitor_id=visitor.id,
        )
        db.add(system_info)
        visitor.system_info = system_info
        created = True

    changed = created

    # Always align platform name with current platform
    if system_info.platform != platform.name:
        system_info.platform = platform.name
        changed = True

    # Ensure first_seen_at is set once from server-side clock
    if system_info.first_seen_at is None:
        system_info.first_seen_at = datetime.utcnow()
        changed = True

    info_data = system_info_payload.model_dump(exclude_none=True) if system_info_payload else {}
    for field in ("source_detail", "browser", "operating_system"):
        if field in info_data and getattr(system_info, field) != info_data[field]:
            setattr(system_info, field, info_data[field])
            changed = True

    # Ignore any unsupported fields silently
    return changed



class VisitorMessageSyncRequest(BaseModel):
    """Visitor-facing request to sync channel messages."""
    platform_api_key: Optional[str] = Field(None, description="Platform API key for authentication")
    channel_id: str = Field(..., description="WuKongIM channel identifier")
    channel_type: int = Field(..., description="WuKongIM channel type (1=personal, 251=customer service)")
    start_message_seq: Optional[int] = Field(None, description="Start message sequence (inclusive)")
    end_message_seq: Optional[int] = Field(None, description="End message sequence (exclusive)")
    limit: Optional[int] = Field(100, description="Max messages to return (default 100)")
    pull_mode: Optional[int] = Field(0, description="Pull mode (0=down, 1=up); default 0")


@router.get("", response_model=VisitorListResponse)
async def list_visitors(
    request: Request,
    params: VisitorListParams = Depends(),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:list")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorListResponse:
    """
    List visitors.

    Retrieve a paginated list of visitors with optional filtering by platform,
    online status, and search query. Requires visitors:list permission.
    """
    logger.info(f"User {current_user.username} listing visitors")

    # Build query
    query = db.query(Visitor).filter(
        Visitor.project_id == current_user.project_id,
        Visitor.deleted_at.is_(None)
    )

    # Apply filters
    if params.platform_id:
        query = query.filter(Visitor.platform_id == params.platform_id)
    if params.is_online is not None:
        query = query.filter(Visitor.is_online == params.is_online)
    if params.search:
        search_term = f"%{params.search}%"
        query = query.filter(
            (Visitor.name.ilike(search_term)) |
            (Visitor.nickname.ilike(search_term)) |
            (Visitor.platform_open_id.ilike(search_term))
        )

    # Get total count
    total = query.count()

    # Apply pagination
    visitors = query.offset(params.offset).limit(params.limit).all()

    # Convert to response models
    accept_language = request.headers.get("Accept-Language")
    visitor_responses = [VisitorResponse.model_validate(visitor) for visitor in visitors]
    for vr in visitor_responses:
        localize_visitor_response_intent(vr, accept_language)
    set_visitor_list_display_nickname(visitor_responses, user_language)

    return VisitorListResponse(
        data=visitor_responses,
        pagination={
            "total": total,
            "limit": params.limit,
            "offset": params.offset,
            "has_next": params.offset + params.limit < total,
            "has_prev": params.offset > 0,
        }
    )


@router.post("", response_model=VisitorResponse, status_code=status.HTTP_201_CREATED)
async def create_visitor(
    request: Request,
    visitor_data: VisitorCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:create")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """
    Create visitor.

    Create a new visitor record. Requires either platform_id or platform_type.
    If platform_type is provided, uses the default platform of that type.
    Requires visitors:create permission.
    """
    logger.info(f"User {current_user.username} creating visitor: {visitor_data.platform_open_id}")

    # Determine platform_id
    platform_id = visitor_data.platform_id
    if not platform_id and visitor_data.platform_type:
        # Find default platform of the specified type
        platform = db.query(Platform).filter(
            Platform.project_id == current_user.project_id,
            Platform.type == visitor_data.platform_type,
            Platform.is_active == True,
            Platform.deleted_at.is_(None)
        ).first()

        if not platform:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No active platform found for type: {visitor_data.platform_type}"
            )
        platform_id = platform.id

    if not platform_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either platform_id or platform_type must be provided"
        )

    # Check if visitor already exists for this platform
    existing_visitor = db.query(Visitor).filter(
        Visitor.project_id == current_user.project_id,
        Visitor.platform_id == platform_id,
        Visitor.platform_open_id == visitor_data.platform_open_id,
        Visitor.deleted_at.is_(None)
    ).first()

    if existing_visitor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor already exists for this platform"
        )

    # Get real IP and language (from request body or headers)
    real_ip = get_client_ip(request, visitor_data.ip_address)
    real_language = get_client_language(request, visitor_data.language)
    
    # Lookup geolocation from IP address
    geo_location = geoip_service.lookup(real_ip)
    
    # Create visitor
    visitor = Visitor(
        project_id=current_user.project_id,
        platform_id=platform_id,
        platform_open_id=visitor_data.platform_open_id,
        name=visitor_data.name,
        nickname=visitor_data.nickname,
        nickname_zh=visitor_data.nickname_zh,
        avatar_url=visitor_data.avatar_url,
        phone_number=visitor_data.phone_number,
        email=visitor_data.email,
        company=visitor_data.company,
        job_title=visitor_data.job_title,
        source=visitor_data.source,
        note=visitor_data.note,
        custom_attributes=visitor_data.custom_attributes or {},
        timezone=visitor_data.timezone,
        language=real_language,
        ip_address=real_ip,
        geo_country=geo_location.country,
        geo_country_code=geo_location.country_code,
        geo_region=geo_location.region,
        geo_city=geo_location.city,
        geo_isp=geo_location.isp,
    )

    db.add(visitor)
    db.commit()
    db.refresh(visitor)

    logger.info(f"Created visitor {visitor.id} for platform {platform_id}")

    await notify_visitor_profile_updated(db, visitor)

    response = VisitorResponse.model_validate(visitor)
    localize_visitor_response_intent(response, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(response, user_language)
    return response

@router.post("/register", response_model=VisitorRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_visitor(
    request: Request,
    req: VisitorRegisterRequest,
    db: Session = Depends(get_db),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorRegisterResponse:
    """Register a visitor using a Platform API key (visitor-facing use).

    - Authenticates via platform_api_key
    - Creates or returns an existing visitor bound to the platform/project
    - Returns channel info for messaging integration
    """
    # 1) Validate platform_api_key
    platform = (
        db.query(Platform)
        .filter(
            Platform.api_key == req.platform_api_key,
            Platform.is_active == True,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform API key")

    # 2) Find existing or create new visitor
    normalized_open_id = (req.platform_open_id or "").strip() or None
    visitor: Optional[Visitor] = None
    if normalized_open_id:
        visitor = (
            db.query(Visitor)
            .filter(
                Visitor.platform_open_id == normalized_open_id,
                Visitor.project_id == platform.project_id,
                Visitor.platform_id == platform.id,
                Visitor.deleted_at.is_(None),
            )
            .first()
        )

    profile_changed = False
    is_new_visitor = False

    if not visitor:
        is_new_visitor = True
        # Get real IP and language (from request body or headers)
        real_ip = get_client_ip(request, req.ip_address)
        real_language = get_client_language(request, req.language)

        # Use _create_visitor_with_channel for complete setup
        # If normalized_open_id is None, visitor.id will be used as platform_open_id
        visitor = await _create_visitor_with_channel(
            db=db,
            platform=platform,
            platform_open_id=normalized_open_id,
            name=req.name,
            nickname=req.nickname,
            nickname_zh=req.nickname_zh,
            avatar_url=req.avatar_url,
            phone_number=req.phone_number,
            email=req.email,
            company=req.company,
            job_title=req.job_title,
            source=req.source,
            note=req.note,
            custom_attributes=req.custom_attributes,
            timezone=req.timezone,
            language=real_language,
            ip_address=real_ip,
        )
        profile_changed = True
    else:
        # Update existing visitor with non-None fields provided in request
        update_data = req.model_dump(exclude_unset=True)

        # Handle nickname updates
        if "nickname" in update_data or "nickname_zh" in update_data:
            resolved_nickname, resolved_nickname_zh = _resolve_visitor_nickname(
                update_data.get("nickname"),
                update_data.get("nickname_zh"),
                normalized_open_id or str(visitor.id),
            )
            update_data["nickname"] = resolved_nickname
            update_data["nickname_zh"] = resolved_nickname_zh

        updatable_fields = [
            "name", "nickname", "nickname_zh", "avatar_url", "phone_number", "email",
            "company", "job_title", "source", "note", "custom_attributes",
            "timezone", "language",
        ]
        
        # Handle IP address update (use request body or extract from headers)
        if "ip_address" in update_data:
            real_ip = get_client_ip(request, update_data.get("ip_address"))
            if real_ip:
                update_data["ip_address"] = real_ip
                updatable_fields.append("ip_address")
        
        # Handle language update (use request body or extract from headers)
        if "language" in update_data:
            real_language = get_client_language(request, update_data.get("language"))
            if real_language:
                update_data["language"] = real_language
        any_updated = False
        for field in updatable_fields:
            if field in update_data and update_data[field] is not None:
                setattr(visitor, field, update_data[field])
                any_updated = True
        if any_updated:
            db.commit()
            db.refresh(visitor)
            profile_changed = True

    system_info_changed = _upsert_visitor_system_info(db, visitor, platform, req.system_info)
    if system_info_changed:
        db.commit()
        db.refresh(visitor)
        profile_changed = True

    # 3) Ensure WuKongIM channel exists
    # For new visitors, channel was already created by _create_visitor_with_channel or _ensure_visitor_channel
    # For existing visitors, we need to ensure channel exists
    if not is_new_visitor:
        await _ensure_visitor_channel(db, visitor, platform)

    if profile_changed:
        await notify_visitor_profile_updated(db, visitor)

    # 3c) Register or login visitor to WuKongIM and generate token for IM login
    im_token = str(uuid.uuid4())
    try:
        await wukongim_client.register_or_login_user(
            uid=str(visitor.id),
            token=im_token,
        )
        logger.info(
            "WuKongIM user ensured for visitor",
            extra={"uid": str(visitor.id)},
        )
    except Exception as e:
        logger.error(
            f"Failed to register/login visitor on WuKongIM: {e}",
            extra={"uid": str(visitor.id)},
        )

    # 4) Build response with additional fields
    channel_id = build_visitor_channel_id(visitor.id)
    base_payload = VisitorResponse.model_validate(visitor).model_dump()
    resp = VisitorRegisterResponse.model_validate({
        **base_payload,
        "channel_id": channel_id,
        "channel_type": CHANNEL_TYPE_CUSTOMER_SERVICE,
        "im_token": im_token,
    })
    localize_visitor_response_intent(resp, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(resp, user_language)
    return resp


@router.post(
    "/activities",
    response_model=VisitorActivityCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Visitor: Record Activity",
    description=(
        "Record a visitor activity from the client-side integration. "
        "Authenticate using the platform API key and supply the visitor ID."
    ),
)
async def record_visitor_activity(
    req: VisitorActivityCreateRequest,
    x_platform_api_key: Optional[str] = Header(None, alias="X-Platform-API-Key"),
    db: Session = Depends(get_db),
) -> VisitorActivityCreateResponse:
    """Record a visitor activity with platform API key authentication."""
    api_key = req.platform_api_key or x_platform_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing platform API key")

    platform = (
        db.query(Platform)
        .filter(
            Platform.api_key == api_key,
            Platform.is_active == True,
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform API key")

    visitor = (
        db.query(Visitor)
        .filter(
            Visitor.id == req.visitor_id,
            Visitor.project_id == platform.project_id,
            Visitor.platform_id == platform.id,
            Visitor.deleted_at.is_(None),
        )
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    data = req.model_dump(exclude_unset=True)

    activity: Optional[VisitorActivity] = None
    is_update = req.id is not None
    if is_update:
        activity = (
            db.query(VisitorActivity)
            .filter(
                VisitorActivity.id == req.id,
                VisitorActivity.project_id == platform.project_id,
                VisitorActivity.visitor_id == visitor.id,
                VisitorActivity.deleted_at.is_(None),
            )
            .first()
        )
        if not activity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor activity not found")

    occurred_at = (
        req.occurred_at
        if "occurred_at" in data
        else (activity.occurred_at if activity else datetime.utcnow())
    )
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Activity title cannot be blank")

    context_payload = None
    context_provided = "context" in data
    if context_provided and req.context is not None:
        context_payload = req.context.model_dump(exclude_none=True)

    duration_provided = "duration_seconds" in data
    description_provided = "description" in data

    if not activity:
        activity = VisitorActivity(
            project_id=platform.project_id,
            visitor_id=visitor.id,
            activity_type=req.activity_type.value,
            title=title,
            occurred_at=occurred_at,
        )
        db.add(activity)

    activity.activity_type = req.activity_type.value
    activity.title = title
    activity.occurred_at = occurred_at

    if description_provided or not is_update:
        activity.description = req.description

    if duration_provided or not is_update:
        activity.duration_seconds = req.duration_seconds

    if context_provided:
        activity.context = context_payload
    elif not is_update:
        activity.context = None
    db.commit()
    db.refresh(activity)

    logger.info(
        "Recorded visitor activity",
        extra={
            "visitor_id": str(visitor.id),
            "platform_id": str(platform.id),
            "activity_type": activity.activity_type,
            "operation": "update" if is_update else "create",
        },
    )

    return VisitorActivityCreateResponse(
        id=activity.id,
        activity_type=activity.activity_type,
        title=activity.title,
        description=activity.description,
        occurred_at=activity.occurred_at,
        duration_seconds=activity.duration_seconds,
        context=activity.context,
    )


@router.get("/by-channel", response_model=VisitorResponse)
async def get_visitor_by_channel(
    request: Request,
    channel_id: str,
    channel_type: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:read")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """Get visitor details by channel identifiers. Requires visitors:read permission.

    Logic:
    - channel_type == CHANNEL_TYPE_CUSTOMER_SERVICE (251): channel_id format is "{visitor_uuid}-vtr"
    - channel_type == 1: channel_id is the visitor_id directly
    - otherwise: 400 unsupported channel type
    """
    # Resolve visitor_id from channel info
    if channel_type == CHANNEL_TYPE_CUSTOMER_SERVICE:
        try:
            visitor_uuid = parse_visitor_channel_id(channel_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visitor channel_id format")
    elif channel_type == 1:
        try:
            visitor_uuid = UUID(channel_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid visitor_id in channel")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported channel_type")

    # Query visitor with eager-loaded platform to populate platform_type
    visitor = (
        db.query(Visitor)
        .options(selectinload(Visitor.platform))
        .filter(
            Visitor.id == visitor_uuid,
            Visitor.project_id == current_user.project_id,
            Visitor.deleted_at.is_(None),
        )
        .first()
    )

    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    response = VisitorResponse.model_validate(visitor)
    localize_visitor_response_intent(response, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(response, user_language)
    return response


@router.get("/{visitor_id}/basic", response_model=VisitorBasicResponse)
async def get_visitor_basic(
    visitor_id: UUID,
    db: Session = Depends(get_db),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorBasicResponse:
    """Get basic visitor information without heavy related entities.

    This endpoint is optimized for quick lookups and avoids loading tags, AI data,
    system info, or recent activities. It only loads the platform relation to
    populate platform_type if available.
    """
    visitor = (
        db.query(Visitor)
        .options(selectinload(Visitor.platform))
        .filter(
            Visitor.id == visitor_id,
            Visitor.deleted_at.is_(None),
        )
        .first()
    )

    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    response = VisitorBasicResponse.model_validate(visitor)
    set_visitor_display_nickname(response, user_language)
    return response




@router.get("/{visitor_id}", response_model=VisitorResponse)
async def get_visitor(
    request: Request,
    visitor_id: str,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:read")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """Get visitor details. Requires visitors:read permission."""
    logger.info(f"User {current_user.username} getting visitor: {visitor_id}")

    # Try to parse visitor_id as UUID for database query
    try:
        visitor_uuid = UUID(visitor_id)
    except (ValueError, AttributeError):
        # If visitor_id is not a valid UUID, skip database query
        visitor_uuid = None

    visitor = None
    if visitor_uuid:
        visitor = (
            db.query(Visitor)
            .options(
                selectinload(Visitor.visitor_tags).selectinload(VisitorTag.tag),
                selectinload(Visitor.ai_profile),
                selectinload(Visitor.ai_insight),
                selectinload(Visitor.system_info),
            )
            .filter(
                Visitor.id == visitor_uuid,
                Visitor.project_id == current_user.project_id,
                Visitor.deleted_at.is_(None)
            )
            .first()
        )
    if not visitor:
        # Generate a default visitor response instead of returning 404
        logger.info(f"Visitor {visitor_id} not found, generating default visitor response")

        # Generate deterministic name based on visitor_id
        default_name = _generate_default_visitor_name(visitor_id)

        # Get the first platform for the project as a default
        default_platform = (
            db.query(Platform)
            .filter(
                Platform.project_id == current_user.project_id,
                Platform.deleted_at.is_(None)
            )
            .first()
        )

        # Use a fallback platform_id if no platform exists
        default_platform_id = default_platform.id if default_platform else current_user.project_id

        # Convert visitor_id to UUID for the response schema
        # If visitor_id is already a valid UUID, use it; otherwise generate a deterministic UUID
        if visitor_uuid:
            response_id = visitor_uuid
        else:
            # Generate a deterministic UUID from the string visitor_id
            id_hash = hashlib.sha256(visitor_id.encode('utf-8')).digest()
            # Use first 16 bytes of hash to create a UUID
            response_id = UUID(bytes=id_hash[:16])

        # Create default visitor response with generated data
        now = datetime.utcnow()
        default_visitor_response = VisitorResponse(
            id=response_id,
            project_id=current_user.project_id,
            platform_id=default_platform_id,
            platform_open_id=f"default_{visitor_id}",
            name=default_name,
            nickname=None,
            nickname_zh=None,
            avatar_url=None,
            phone_number=None,
            email=None,
            company=None,
            job_title=None,
            source=None,
            note=None,
            custom_attributes={},
            first_visit_time=now,
            last_visit_time=now,
            last_offline_time=None,
            is_online=False,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            platform_type=(default_platform.type if default_platform else None),
            tags=[],
            ai_profile=None,
            ai_insights=None,
            system_info=None,
            recent_activities=[],
        )

        set_visitor_display_nickname(default_visitor_response, user_language)
        return default_visitor_response

    active_tags = [
        vt.tag
        for vt in visitor.visitor_tags
        if vt.deleted_at is None and vt.tag and vt.tag.deleted_at is None
    ]
    tag_responses = [TagResponse.model_validate(tag) for tag in active_tags]
    set_tag_list_display_name(tag_responses, user_language)

    ai_profile_response = (
        VisitorAIProfileResponse.model_validate(visitor.ai_profile)
        if visitor.ai_profile
        else None
    )
    ai_insight_response = (
        VisitorAIInsightResponse.model_validate(visitor.ai_insight)
        if visitor.ai_insight
        else None
    )
    system_info_response = (
        VisitorSystemInfoResponse.model_validate(visitor.system_info)
        if visitor.system_info
        else None
    )

    recent_activities = (
        db.query(VisitorActivity)
        .filter(
            VisitorActivity.visitor_id == visitor.id,
            VisitorActivity.project_id == current_user.project_id,
            VisitorActivity.deleted_at.is_(None)
        )
        .order_by(VisitorActivity.occurred_at.desc())
        .limit(10)
        .all()
    )
    recent_activity_responses = [
        VisitorActivityResponse.model_validate(activity)
        for activity in recent_activities
    ]

    visitor_payload = VisitorResponse.model_validate(visitor)
    response = visitor_payload.model_copy(
        update={
            "tags": tag_responses,
            "ai_profile": ai_profile_response,
            "ai_insights": ai_insight_response,
            "system_info": system_info_response,
            "recent_activities": recent_activity_responses,
        }
    )
    set_visitor_display_nickname(response, user_language)
    return response


@router.put("/{visitor_id}/attributes", response_model=VisitorResponse)
async def set_visitor_attributes(
    request: Request,
    visitor_id: UUID,
    attributes: VisitorAttributesUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:update")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """Set visitor profile attributes including custom fields. Requires visitors:update permission."""
    logger.info(f"User {current_user.username} setting attributes for visitor: {visitor_id}")

    visitor_query = db.query(Visitor).filter(
        Visitor.id == visitor_id,
        Visitor.project_id == current_user.project_id,
    )
    visitor = visitor_query.filter(Visitor.deleted_at.is_(None)).first()

    created_new = False
    restored_deleted = False
    if not visitor:
        soft_deleted = visitor_query.first()
        if soft_deleted:
            visitor = soft_deleted
            visitor.deleted_at = None
            restored_deleted = True
        else:
            platform = (
                db.query(Platform)
                .filter(
                    Platform.project_id == current_user.project_id,
                    Platform.is_active == True,
                    Platform.deleted_at.is_(None)
                )
                .order_by(Platform.created_at)
                .first()
            )

            if not platform:
                # Use unknown platform fallback when no active platform is available
                from app.core.config import settings
                unknown_platform_id = UUID(settings.UNKNOWN_PLATFORM_ID)
                logger.warning(
                    f"No active platform found for project {current_user.project_id}, "
                    f"using unknown platform fallback: {settings.UNKNOWN_PLATFORM_NAME} ({unknown_platform_id})"
                )
                platform_id = unknown_platform_id
            else:
                platform_id = platform.id

            visitor = Visitor(
                id=visitor_id,
                project_id=current_user.project_id,
                platform_id=platform_id,
                platform_open_id=str(visitor_id),
            )
            db.add(visitor)
            created_new = True
    else:
        # Check if the visitor's platform still exists
        visitor_platform = (
            db.query(Platform)
            .filter(
                Platform.id == visitor.platform_id,
                Platform.deleted_at.is_(None)
            )
            .first()
        )

        if not visitor_platform:
            # Platform doesn't exist or was deleted, use unknown platform fallback
            from app.core.config import settings
            unknown_platform_id = UUID(settings.UNKNOWN_PLATFORM_ID)
            logger.warning(
                f"Platform {visitor.platform_id} not found for visitor {visitor.id}, "
                f"using unknown platform fallback: {settings.UNKNOWN_PLATFORM_NAME} ({unknown_platform_id})"
            )
            visitor.platform_id = unknown_platform_id

    update_data = attributes.model_dump(exclude_unset=True)
    custom_attributes = update_data.pop("custom_attributes", None)

    for field, value in update_data.items():
        setattr(visitor, field, value)

    if custom_attributes is not None:
        visitor.custom_attributes = custom_attributes or {}

    visitor.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(visitor)

    if created_new:
        action = "Created"
    elif restored_deleted:
        action = "Restored"
    else:
        action = "Updated"
    logger.info(f"{action} attributes for visitor {visitor.id}")

    await notify_visitor_profile_updated(db, visitor)

    response = VisitorResponse.model_validate(visitor)
    localize_visitor_response_intent(response, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(response, user_language)
    return response



@router.patch("/{visitor_id}", response_model=VisitorResponse)
async def update_visitor(
    request: Request,
    visitor_id: UUID,
    visitor_data: VisitorUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:update")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """
    Update visitor.

    Update visitor information including contact details and activity status.
    Requires visitors:update permission.
    """
    logger.info(f"User {current_user.username} updating visitor: {visitor_id}")

    visitor = db.query(Visitor).filter(
        Visitor.id == visitor_id,
        Visitor.project_id == current_user.project_id,
        Visitor.deleted_at.is_(None)
    ).first()

    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )

    # Update fields
    update_data = visitor_data.model_dump(exclude_unset=True)
    custom_attributes = update_data.pop("custom_attributes", None)

    for field, value in update_data.items():
        setattr(visitor, field, value)

    if custom_attributes is not None:
        visitor.custom_attributes = custom_attributes or {}

    visitor.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(visitor)

    logger.info(f"Updated visitor {visitor.id}")

    await notify_visitor_profile_updated(db, visitor)

    response = VisitorResponse.model_validate(visitor)
    localize_visitor_response_intent(response, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(response, user_language)
    return response



@router.post("/{visitor_id}/enable-ai", response_model=VisitorResponse)
async def enable_ai_for_visitor(
    request: Request,
    visitor_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:update")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """Enable AI for a visitor (set ai_disabled=False). Requires visitors:update permission."""
    logger.info("User %s enabling AI for visitor %s", current_user.username, str(visitor_id))

    visitor = (
        db.query(Visitor)
        .filter(
            Visitor.id == visitor_id,
            Visitor.project_id == current_user.project_id,
            Visitor.deleted_at.is_(None),
        )
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    visitor.ai_disabled = False
    visitor.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(visitor)

    logger.info("AI enabled for visitor %s by user %s", str(visitor.id), current_user.username)
    await notify_visitor_profile_updated(db, visitor)
    response = VisitorResponse.model_validate(visitor)
    localize_visitor_response_intent(response, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(response, user_language)
    return response


@router.post("/{visitor_id}/disable-ai", response_model=VisitorResponse)
async def disable_ai_for_visitor(
    request: Request,
    visitor_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:update")),
    user_language: UserLanguage = Depends(get_user_language),
) -> VisitorResponse:
    """Disable AI for a visitor (set ai_disabled=True). Requires visitors:update permission."""
    logger.info("User %s disabling AI for visitor %s", current_user.username, str(visitor_id))

    visitor = (
        db.query(Visitor)
        .filter(
            Visitor.id == visitor_id,
            Visitor.project_id == current_user.project_id,
            Visitor.deleted_at.is_(None),
        )
        .first()
    )
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    visitor.ai_disabled = True
    visitor.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(visitor)

    logger.info("AI disabled for visitor %s by user %s", str(visitor.id), current_user.username)
    await notify_visitor_profile_updated(db, visitor)
    response = VisitorResponse.model_validate(visitor)
    localize_visitor_response_intent(response, request.headers.get("Accept-Language"))
    set_visitor_display_nickname(response, user_language)
    return response


@router.delete("/{visitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visitor(
    visitor_id: UUID,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_permission("visitors:delete")),
) -> None:
    """
    Delete visitor (soft delete).

    Soft delete a visitor record. This also removes all associated assignments and tags.
    Requires visitors:delete permission.
    """
    logger.info(f"User {current_user.username} deleting visitor: {visitor_id}")

    visitor = db.query(Visitor).filter(
        Visitor.id == visitor_id,
        Visitor.project_id == current_user.project_id,
        Visitor.deleted_at.is_(None)
    ).first()

    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )

    # Soft delete
    visitor.deleted_at = datetime.utcnow()
    visitor.updated_at = datetime.utcnow()

    db.commit()

    logger.info(f"Deleted visitor {visitor.id}")

    return None



@router.post(
    "/messages/sync",
    response_model=WuKongIMChannelMessageSyncResponse,
    summary="Visitor: Sync Channel Messages",
    description="Visitor-facing endpoint to retrieve historical messages from a channel."
)
async def sync_visitor_channel_messages(
    req: VisitorMessageSyncRequest,
    db: Session = Depends(get_db),
    x_platform_api_key: Optional[str] = Header(None, alias="X-Platform-API-Key"),
) -> WuKongIMChannelMessageSyncResponse:
    """Retrieve historical messages for a channel using platform API key authentication."""
    # 1) Authenticate platform via API key (body param or header)
    api_key = req.platform_api_key or x_platform_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing platform_api_key")

    platform = (
        db.query(Platform)
        .filter(
            Platform.api_key == api_key,
            Platform.is_active.is_(True),
            Platform.deleted_at.is_(None),
        )
        .first()
    )
    if not platform:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform_api_key")

    # 2) Authorize access to the channel and determine login_uid (visitor UID)
    login_uid: Optional[str] = None

    if req.channel_type == CHANNEL_TYPE_CUSTOMER_SERVICE:
        try:
            visitor_uuid = parse_visitor_channel_id(req.channel_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel_id format")

        visitor = (
            db.query(Visitor)
            .filter(Visitor.id == visitor_uuid, Visitor.deleted_at.is_(None))
            .first()
        )
        if not visitor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")
        if visitor.platform_id != platform.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this channel is forbidden for this platform")

        login_uid = str(visitor.id)

    elif req.channel_type == 1:
        # Personal channel: channel_id should be a visitor UUID (not a staff UID)
        if req.channel_id.endswith("-staff"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff personal channels are not accessible to visitors")
        try:
            visitor_uuid = UUID(req.channel_id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid channel_id format for personal channel")

        visitor = (
            db.query(Visitor)
            .filter(Visitor.id == visitor_uuid, Visitor.deleted_at.is_(None))
            .first()
        )
        if not visitor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")
        if visitor.platform_id != platform.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this visitor is forbidden for this platform")

        login_uid = str(visitor.id)

    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported channel_type")

    # Defaults and bounds
    start_seq = req.start_message_seq if req.start_message_seq is not None else 0
    end_seq = req.end_message_seq if req.end_message_seq is not None else 0
    limit = req.limit if req.limit is not None else 100
    pull_mode = req.pull_mode if req.pull_mode is not None else 0

    logger.info(
        "Visitor messages sync request",
        extra={
            "platform_id": str(platform.id),
            "channel_id": req.channel_id,
            "channel_type": req.channel_type,
            "start_message_seq": start_seq,
            "end_message_seq": end_seq,
            "limit": limit,
            "pull_mode": pull_mode,
        },
    )

    try:
        result = await wukongim_client.sync_channel_messages(
            login_uid=login_uid,
            channel_id=req.channel_id,
            channel_type=req.channel_type,
            start_message_seq=start_seq,
            end_message_seq=end_seq,
            limit=limit,
            pull_mode=pull_mode,
        )
        msg_count = len(result.messages)
        logger.info(
            "Visitor messages sync success",
            extra={"platform_id": str(platform.id), "channel_id": req.channel_id, "channel_type": req.channel_type, "messages": msg_count},
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync channel messages for visitor: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to sync channel messages")


# ============================================================================
# Visitor Avatar Upload Endpoints
# ============================================================================

# Allowed image types for avatar upload
AVATAR_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}
AVATAR_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
AVATAR_MAX_SIZE_MB = 5  # 5MB limit for avatar


def _sanitize_avatar_filename(name: str, limit: int = 100) -> str:
    """Sanitize filename for avatar upload."""
    name = name.replace("\\", "_").replace("/", "_").replace("..", ".")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if len(name) <= limit:
        return name
    # Preserve extension if present
    if "." in name:
        base, ext = name.rsplit(".", 1)
        base = base[: max(1, limit - len(ext) - 1)]
        return f"{base}.{ext}"
    return name[:limit]


@router.post(
    "/{visitor_id}/avatar",
    response_model=VisitorAvatarUploadResponse,
    summary="Upload visitor avatar",
    description="""
    Upload an avatar image for a visitor.

    **Authentication**: JWT (Staff) authentication required.
    - Use `Authorization: Bearer <token>` header

    **File Requirements**:
    - Allowed formats: JPEG, PNG, GIF, WebP
    - Maximum size: 5MB

    **Storage**:
    - Files are stored locally on the server
    - The `avatar_url` field is updated with a relative path (e.g., `/v1/visitors/{visitor_id}/avatar`)
    """,
    tags=["Visitors"],
)
async def upload_visitor_avatar(
    visitor_id: UUID,
    file: UploadFile = File(..., description="Avatar image file"),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user),
) -> VisitorAvatarUploadResponse:
    """Upload an avatar image for a visitor."""
    # 1) Query visitor
    visitor = (
        db.query(Visitor)
        .filter(Visitor.id == visitor_id, Visitor.deleted_at.is_(None))
        .first()
    )
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )

    # 2) Authorization check: Staff must belong to the same project
    if visitor.project_id != current_user.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this visitor"
        )

    # 4) Validate file type and extension
    original_name = file.filename or "avatar.jpg"
    sanitized_name = _sanitize_avatar_filename(original_name)
    ext = sanitized_name.rsplit(".", 1)[-1].lower() if "." in sanitized_name else ""
    mime = file.content_type or mimetypes.guess_type(sanitized_name)[0] or "application/octet-stream"

    if ext not in AVATAR_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(AVATAR_ALLOWED_EXTENSIONS)}"
        )

    if mime not in AVATAR_ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type not allowed. Allowed types: {', '.join(AVATAR_ALLOWED_MIME_TYPES)}"
        )

    max_bytes = AVATAR_MAX_SIZE_MB * 1024 * 1024

    # 5) Build storage path
    ts_ms = int(time.time() * 1000)
    rand = secrets.token_hex(4)
    fname = f"{ts_ms}_{rand}.{ext}"

    # Path: uploads/avatars/{project_id}/{visitor_id}/{filename}
    rel_path = f"avatars/{visitor.project_id}/{visitor_id}/{fname}"
    base_dir = Path(settings.UPLOAD_BASE_DIR).resolve()
    dest_path = base_dir / rel_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 6) Save file in chunks with size validation
    total = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    try:
                        out.flush()
                        out.close()
                    finally:
                        try:
                            os.unlink(dest_path)
                        except Exception:
                            pass
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size: {AVATAR_MAX_SIZE_MB}MB"
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        # Cleanup on failure
        try:
            if dest_path.exists():
                os.unlink(dest_path)
        except Exception:
            pass
        logger.error(f"Failed to save avatar file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save avatar file"
        )

    # 7) Delete old avatar file if exists (local file only, not external URL)
    old_avatar_url = visitor.avatar_url
    if old_avatar_url and old_avatar_url.startswith("/v1/visitors/"):
        # Extract old file path and try to delete
        try:
            # Old avatar is stored in same structure
            old_files = list((base_dir / f"avatars/{visitor.project_id}/{visitor_id}").glob("*"))
            for old_file in old_files:
                if old_file.name != fname and old_file.is_file():
                    os.unlink(old_file)
        except Exception as e:
            logger.warning(f"Failed to delete old avatar file: {e}")

    # 8) Update visitor avatar_url with relative path (stored in DB)
    # Use relative URL path that can be served by the API
    relative_avatar_url = f"/v1/visitors/{visitor_id}/avatar"
    visitor.avatar_url = relative_avatar_url
    db.commit()
    db.refresh(visitor)

    # Build absolute URL for response
    absolute_avatar_url = f"{settings.API_BASE_URL.rstrip('/')}{relative_avatar_url}"

    logger.info(
        "Visitor avatar uploaded",
        extra={
            "visitor_id": str(visitor_id),
            "file_size": total,
            "file_type": mime,
        }
    )

    return VisitorAvatarUploadResponse(
        visitor_id=visitor_id,
        avatar_url=absolute_avatar_url,
        file_name=original_name,
        file_size=total,
        file_type=mime,
        uploaded_at=visitor.updated_at,
    )


@router.get(
    "/{visitor_id}/avatar",
    summary="Get visitor avatar",
    description="""
    Retrieve the avatar image for a visitor.

    **Public Access**: This endpoint allows public access to serve avatar images.
    If the visitor has no avatar or an external URL, returns 404.
    """,
    tags=["Visitors"],
    responses={
        200: {"content": {"image/*": {}}, "description": "Avatar image file"},
        404: {"description": "Avatar not found"},
    },
)
async def get_visitor_avatar(
    visitor_id: UUID,
    db: Session = Depends(get_db),
):
    """Get visitor avatar image file."""
    # 1) Query visitor
    visitor = (
        db.query(Visitor)
        .filter(Visitor.id == visitor_id, Visitor.deleted_at.is_(None))
        .first()
    )
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor not found"
        )

    # 2) Check if avatar exists and is a local file
    avatar_url = visitor.avatar_url
    if not avatar_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor has no avatar"
        )

    # If avatar is an external URL (https://...), redirect or return 404
    if avatar_url.startswith("http://") or avatar_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar is hosted externally. Use the avatar_url field directly."
        )

    # 3) Find the avatar file on disk
    base_dir = Path(settings.UPLOAD_BASE_DIR).resolve()
    avatar_dir = base_dir / f"avatars/{visitor.project_id}/{visitor_id}"

    if not avatar_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar file not found"
        )

    # Get the most recent avatar file
    avatar_files = sorted(avatar_dir.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not avatar_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar file not found"
        )

    avatar_file = avatar_files[0]

    # 4) Ensure file path stays under base directory (security)
    try:
        avatar_file.resolve().relative_to(base_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid file path"
        )

    if not avatar_file.exists() or not avatar_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar file not found"
        )

    # 5) Determine content type
    ext = avatar_file.suffix.lower().lstrip(".")
    content_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(avatar_file),
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400",  # Cache for 1 day
        },
    )
