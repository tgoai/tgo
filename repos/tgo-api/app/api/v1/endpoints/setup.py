"""Setup endpoints for system initialization."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import generate_api_key, get_password_hash
from app.models import (
    AIProvider,
    ChannelMember,
    Platform,
    PlatformType,
    PlatformTypeDefinition,
    Project,
    Staff,
    SystemSetup,
    Visitor,
    VisitorAssignmentRule,
)
from app.models.staff import StaffRole, StaffStatus
from app.schemas.setup import (
    BatchCreateStaffRequest,
    BatchCreateStaffResponse,
    ConfigureLLMRequest,
    ConfigureLLMResponse,
    CreateAdminRequest,
    CreateAdminResponse,
    SetupCheckResult,
    SetupStatusResponse,
    SkipLLMConfigResponse,
    StaffCreatedItem,
    VerifySetupResponse,
)
from app.services.ai_client import ai_client
from app.services.wukongim_client import wukongim_client
from app.utils.const import (
    CHANNEL_TYPE_CUSTOMER_SERVICE,
    MEMBER_TYPE_STAFF,
    MEMBER_TYPE_VISITOR,
)
from app.utils.crypto import encrypt_str
from app.utils.encoding import build_visitor_channel_id

logger = get_logger("endpoints.setup")

router = APIRouter()


def _get_or_create_system_setup(db: Session) -> SystemSetup:
    """Get the singleton SystemSetup record, creating it if missing.

    This ensures there's always exactly one row representing installation state.
    """
    setup = db.query(SystemSetup).order_by(SystemSetup.created_at.asc()).first()
    if setup is None:
        # Ensure required timestamps are populated explicitly to satisfy
        # NOT NULL constraints even if the database column lacks a default.
        now = datetime.now(timezone.utc)
        setup = SystemSetup(
            is_installed=False,
            admin_created=False,
            llm_configured=False,
            skip_llm_config=False,
            setup_version="v1",
            created_at=now,
            updated_at=now,
        )
        db.add(setup)
        db.commit()
        db.refresh(setup)
    return setup


def _recalculate_install_flags(setup: SystemSetup) -> None:
    """Recalculate and update installation flags on the SystemSetup row.

    Installation is considered complete when:
        admin_created AND (llm_configured OR skip_llm_config)
    """
    is_installed = setup.admin_created and (setup.llm_configured or setup.skip_llm_config)
    if setup.is_installed != is_installed:
        setup.is_installed = is_installed
        if is_installed and setup.setup_completed_at is None:
            setup.setup_completed_at = datetime.now(timezone.utc)


def _check_system_installed(db: Session) -> tuple[bool, bool, bool, bool, bool]:
    """Check installation state from the SystemSetup table.

    Returns:
        tuple[bool, bool, bool, bool, bool]:
            (is_installed, has_admin, has_user_staff, has_llm_config, skip_llm_config)
    """
    setup = _get_or_create_system_setup(db)
    _recalculate_install_flags(setup)
    db.commit()
    db.refresh(setup)
    
    # Check if any non-admin staff (user role) exists
    has_user_staff = db.query(Staff).filter(
        Staff.role == StaffRole.USER.value,
        Staff.deleted_at.is_(None),
    ).first() is not None
    
    return setup.is_installed, setup.admin_created, has_user_staff, setup.llm_configured, setup.skip_llm_config


def _get_setup_completed_time(db: Session) -> Optional[datetime]:
    """Get the timestamp when setup was completed from SystemSetup row."""
    setup = db.query(SystemSetup).order_by(SystemSetup.created_at.asc()).first()
    if not setup:
        return None
    return setup.setup_completed_at


@router.get(
    "/status",
    response_model=SetupStatusResponse,
    summary="Check system installation status",
    description="Check whether the system has completed initial installation and return setup progress."
)
async def get_setup_status(
    db: Session = Depends(get_db),
) -> SetupStatusResponse:
    """
    Check system installation status.

    Returns information about whether the system has been set up, including:
    - Whether an admin account exists
    - Whether any non-admin staff (user role) exists
    - Whether LLM provider is configured
    - When setup was completed (if applicable)
    """
    is_installed, has_admin, has_user_staff, has_llm_config, skip_llm_config = _check_system_installed(db)
    setup_completed_at = _get_setup_completed_time(db) if is_installed else None

    logger.info(
        f"Setup status check: installed={is_installed}, "
        f"has_admin={has_admin}, has_user_staff={has_user_staff}, "
        f"has_llm={has_llm_config}, skip_llm={skip_llm_config}"
    )

    return SetupStatusResponse(
        is_installed=is_installed,
        has_admin=has_admin,
        has_user_staff=has_user_staff,
        has_llm_config=has_llm_config,
        skip_llm_config=skip_llm_config,
        setup_completed_at=setup_completed_at,
    )


# Fixed admin username
ADMIN_USERNAME = "admin"


@router.post(
    "/admin",
    response_model=CreateAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create first admin account",
    description="Create the system's first administrator account and default project. "
                "Username is fixed as 'admin'. This endpoint can only be called once during initial setup."
)
async def create_admin(
    admin_data: CreateAdminRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CreateAdminResponse:
    """
    Create the first admin account.

    This endpoint:
    1. Checks that no admin exists yet
    2. Creates a default project
    3. Creates the first admin staff member (username is fixed as 'admin')
    4. Returns the created admin information

    Can only be called once. Returns 403 if system is already installed.
    """
    # Ensure we have a SystemSetup row and check admin state
    setup = _get_or_create_system_setup(db)

    # Check if admin already exists (idempotent behavior)
    existing_admin = db.query(Staff).filter(
        Staff.username == ADMIN_USERNAME,
        Staff.deleted_at.is_(None)
    ).first()

    if existing_admin:
        # Return existing admin info for idempotency
        project = existing_admin.project
        logger.info(
            f"Admin already exists, returning existing info for idempotency: {ADMIN_USERNAME}"
        )
        return CreateAdminResponse(
            id=existing_admin.id,
            username=ADMIN_USERNAME,
            nickname=existing_admin.nickname,
            project_id=project.id if project else existing_admin.project_id,
            project_name=project.name if project else "Unknown",
            created_at=existing_admin.created_at,
        )

    if setup.is_installed:
        logger.warning(
            f"Attempt to call setup endpoint after installation is complete: {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "System installation is already complete. "
                "Setup endpoints are disabled for security reasons."
            ),
        )

    # Create default project
    api_key = generate_api_key()
    project = Project(
        name=admin_data.project_name,
        api_key=api_key,
    )
    db.add(project)
    db.flush()  # Get project ID without committing

    logger.info(f"Created default project: {project.name} (ID: {project.id})")

    # Create default AI team for this project (required, will rollback on failure)
    try:
        team_data = {
            "name": "Tgo AI Team",
            "is_default": True,
        }
        team_result = await ai_client.create_team(
            project_id=str(project.id),
            team_data=team_data,
        )
        default_team_id = team_result.get("id")
        if not default_team_id:
            raise ValueError("AI service returned empty team ID")
        project.default_team_id = str(default_team_id)
        logger.info(
            "Created default AI team for project",
            extra={
                "project_id": str(project.id),
                "team_id": default_team_id,
            },
        )
    except Exception as e:
        logger.error(
            f"Failed to create default AI team: {e}",
            extra={"project_id": str(project.id)},
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to create default AI team: {e}. Please retry.",
        )

    # Hash password
    password_hash = get_password_hash(admin_data.password)

    # Create admin staff member (username is fixed as 'admin')
    admin = Staff(
        project_id=project.id,
        username=ADMIN_USERNAME,
        password_hash=password_hash,
        nickname=admin_data.nickname or "Administrator",
        name=admin_data.nickname or "Administrator",
        role=StaffRole.ADMIN,  # Admin is a regular user role
        status=StaffStatus.OFFLINE,
    )
    db.add(admin)

    # Create one platform per platform type definition for this project
    platform_type_definitions = db.query(PlatformTypeDefinition).all()
    platforms: list[Platform] = []
    website_platform: Optional[Platform] = None

    if not platform_type_definitions:
        logger.error(
            "No platform type definitions found; skipping automatic platform and visitor creation",
            extra={"project_id": str(project.id)},
        )
    else:
        for pt_def in platform_type_definitions:
            platform = Platform(
                project_id=project.id,
                type=pt_def.type,
                api_key=generate_api_key(),
                config={},
                is_active=False,
            )
            
            if pt_def.type == PlatformType.WEBSITE.value:
                platform.config = {
                    "position": "bottom-right",
                    "welcome_message": "Hello! How can I help you today?",
                    "widget_title": "TGO AI Chatbot",
                }
                platform.is_active = True
                website_platform = platform
            
            db.add(platform)
            platforms.append(platform)

            

        db.flush()  # Ensure platform IDs are available

        logger.info(
            "Created platforms for project from platform type definitions",
            extra={
                "project_id": str(project.id),
                "platform_count": len(platforms),
            },
        )

        # Create a default visitor with AI disabled, only if we have a website platform
        default_visitor: Optional[Visitor] = None
        if website_platform is None:
            logger.error(
                "No 'website' platform type definition found; skipping default visitor and WuKongIM setup",
                extra={"project_id": str(project.id)},
            )
        else:
            default_visitor = Visitor(
                project_id=project.id,
                platform_id=website_platform.id,
                platform_open_id=str(uuid4()),
                nickname="Default Visitor",
                nickname_zh="默认访客",
                ai_disabled=True,
            )
            db.add(default_visitor)
            db.flush()  # Ensure default_visitor.id is available

            logger.info(
                "Created default visitor for project",
                extra={
                    "project_id": str(project.id),
                    "platform_id": str(website_platform.id),
                    "visitor_id": str(default_visitor.id),
                },
            )

            # Prepare WuKongIM channel and members (best-effort, non-fatal on failure)
            channel_id = build_visitor_channel_id(default_visitor.id)
            channel_members = [
                ChannelMember(
                    project_id=project.id,
                    channel_id=channel_id,
                    channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
                    member_id=default_visitor.id,
                    member_type=MEMBER_TYPE_VISITOR,
                ),
                ChannelMember(
                    project_id=project.id,
                    channel_id=channel_id,
                    channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
                    member_id=admin.id,
                    member_type=MEMBER_TYPE_STAFF,
                ),
            ]
            db.add_all(channel_members)

            try:
                # Ensure WuKongIM channel exists with visitor and admin as subscribers
                subscribers = [str(default_visitor.id), f"{admin.id}-staff"]
                await wukongim_client.create_channel(
                    channel_id=channel_id,
                    channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
                    subscribers=subscribers,
                )

                logger.info(
                    "WuKongIM channel created for default visitor during setup",
                    extra={
                        "channel_id": channel_id,
                        "channel_type": CHANNEL_TYPE_CUSTOMER_SERVICE,
                        "visitor_id": str(default_visitor.id),
                        "admin_id": str(admin.id),
                    },
                )

                # Ensure WuKongIM user exists for the visitor (best-effort)
                try:
                    await wukongim_client.register_or_login_user(uid=str(default_visitor.id))
                    logger.info(
                        "WuKongIM user ensured for default visitor",
                        extra={"uid": str(default_visitor.id)},
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to register default visitor on WuKongIM: {e}",
                        extra={"uid": str(default_visitor.id)},
                    )

                # Send a test message as the visitor
                try:
                    await wukongim_client.send_text_message(
                        from_uid=str(default_visitor.id),
                        channel_id=channel_id,
                        channel_type=CHANNEL_TYPE_CUSTOMER_SERVICE,
                        content="this is a test message from the default visitor",
                    )
                    logger.info(
                        "Sent WuKongIM test message for default visitor",
                        extra={
                            "visitor_id": str(default_visitor.id),
                            "channel_id": channel_id,
                            "channel_type": CHANNEL_TYPE_CUSTOMER_SERVICE,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send WuKongIM test message for default visitor: {e}",
                        extra={
                            "visitor_id": str(default_visitor.id),
                            "channel_id": channel_id,
                            "channel_type": CHANNEL_TYPE_CUSTOMER_SERVICE,
                        },
                    )
            except Exception as e:
                # Do not fail admin creation if channel setup fails
                logger.error(
                    f"Failed to setup WuKongIM channel for default visitor during admin setup: {e}",
                    extra={
                        "project_id": str(project.id),
                        "visitor_id": str(default_visitor.id),
                        "channel_id": channel_id,
                    },
                )

    # Update system setup flags
    setup.admin_created = True
    if admin_data.skip_llm_config:
        setup.skip_llm_config = True
    _recalculate_install_flags(setup)

    db.commit()
    db.refresh(admin)
    db.refresh(project)
    db.refresh(setup)

    logger.info(
        f"Created first admin: {ADMIN_USERNAME} (ID: {admin.id}) "
        f"for project {project.name}"
    )

    return CreateAdminResponse(
        id=admin.id,
        username=ADMIN_USERNAME,
        nickname=admin.nickname,
        project_id=project.id,
        project_name=project.name,
        created_at=admin.created_at,
    )


@router.post(
    "/llm-config",
    response_model=ConfigureLLMResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Configure LLM provider",
    description="Configure a Large Language Model provider for the system. "
                "Requires that an admin account has been created first."
)
async def configure_llm(
    llm_data: ConfigureLLMRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ConfigureLLMResponse:
    """
    Configure LLM provider.

    This endpoint:
    1. Checks that an admin/project exists
    2. Creates an AIProvider configuration
    3. Encrypts and stores the API key
    4. Returns the configuration details

    The API key is encrypted before storage for security.
    """
    # Check if admin exists (required before LLM config)
    setup = _get_or_create_system_setup(db)

    if setup.is_installed:
        logger.warning(
            f"Attempt to call setup endpoint after installation is complete: {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "System installation is already complete. "
                "Setup endpoints are disabled for security reasons."
            ),
        )

    has_admin = setup.admin_created

    if not has_admin:
        logger.warning("Attempt to configure LLM before creating admin")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account must be created before configuring LLM provider"
        )

    # Get the first project (created during admin setup)
    project = db.query(Project).filter(Project.deleted_at.is_(None)).first()

    if not project:
        logger.error("No project found despite admin existing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System error: No project found"
        )

    # Validate default_model is in available_models if both provided
    if llm_data.default_model and llm_data.available_models:
        if llm_data.default_model not in llm_data.available_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="default_model must be in available_models list"
            )

    # Create AI Provider configuration
    ai_provider = AIProvider(
        project_id=project.id,
        provider=llm_data.provider,
        name=llm_data.name,
        api_key=encrypt_str(llm_data.api_key),  # Encrypt API key
        api_base_url=llm_data.api_base_url,
        available_models=llm_data.available_models,
        default_model=llm_data.default_model,
        config=llm_data.config,
        is_active=llm_data.is_active,
    )
    db.add(ai_provider)

    # Update system setup flags
    setup.llm_configured = True
    setup.skip_llm_config = False
    _recalculate_install_flags(setup)

    db.commit()
    db.refresh(ai_provider)
    db.refresh(setup)

    logger.info(
        f"Created LLM provider: {ai_provider.provider}/{ai_provider.name} "
        f"(ID: {ai_provider.id}) for project {project.id}"
    )

    return ConfigureLLMResponse(
        id=ai_provider.id,
        provider=ai_provider.provider,
        name=ai_provider.name,
        default_model=ai_provider.default_model,
        is_active=ai_provider.is_active,
        project_id=ai_provider.project_id,
        created_at=ai_provider.created_at,
    )


@router.post(
    "/skip-llm",
    response_model=SkipLLMConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Skip LLM configuration during setup",
    description=(
        "Explicitly skip the LLM configuration step in the installation wizard. "
        "This is useful when you want to complete the installation now and "
        "configure AI providers later via the normal management endpoints."
    ),
)
async def skip_llm_configuration(
    request: Request,
    db: Session = Depends(get_db),
) -> SkipLLMConfigResponse:
    """Skip the LLM configuration step in the setup wizard.

    Preconditions:
    - An admin account must have been created (``SystemSetup.admin_created`` is True)
    - No LLM provider has been configured yet (``SystemSetup.llm_configured`` is False)
    - LLM configuration has not already been skipped (``SystemSetup.skip_llm_config`` is False)

    When successful, this endpoint:
    - Marks ``skip_llm_config`` as True on the SystemSetup row
    - Recalculates installation status using
      ``is_installed = admin_created AND (llm_configured OR skip_llm_config)``
    - Sets ``setup_completed_at`` if installation becomes complete
    """
    setup = _get_or_create_system_setup(db)

    if setup.is_installed:
        logger.warning(
            f"Attempt to call setup endpoint after installation is complete: {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "System installation is already complete. "
                "Setup endpoints are disabled for security reasons."
            ),
        )

    # Preconditions
    if not setup.admin_created:
        logger.warning("Attempt to skip LLM config before admin is created")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account must be created first",
        )

    if setup.llm_configured:
        logger.warning("Attempt to skip LLM config after provider already configured")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM provider already configured",
        )

    if setup.skip_llm_config:
        logger.warning("Attempt to skip LLM config which was already skipped")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM configuration already skipped",
        )

    # Perform skip operation
    setup.skip_llm_config = True
    _recalculate_install_flags(setup)
    db.commit()
    db.refresh(setup)

    logger.info(
        "LLM configuration skipped via /v1/setup/skip-llm; "
        f"is_installed={setup.is_installed}, "
        f"setup_completed_at={setup.setup_completed_at}",
    )

    return SkipLLMConfigResponse(
        message="LLM configuration step skipped successfully",
        is_installed=setup.is_installed,
        setup_completed_at=setup.setup_completed_at,
    )


@router.get(
    "/verify",
    response_model=VerifySetupResponse,
    summary="Verify installation completeness",
    description="Verify that the system installation is complete and all components are properly configured."
)
async def verify_setup(
    db: Session = Depends(get_db),
) -> VerifySetupResponse:
    """
    Verify installation completeness.

    Performs comprehensive health checks including:
    - Database connectivity
    - Admin account existence
    - LLM provider configuration
    - System readiness

    Returns detailed check results and any errors or warnings found.
    """
    checks = {}
    errors = []
    warnings = []

    # Check 1: Database connection
    try:
        db.execute(text("SELECT 1"))
        checks["database_connected"] = SetupCheckResult(
            passed=True,
            message="Database connection is healthy"
        )
    except Exception as e:
        checks["database_connected"] = SetupCheckResult(
            passed=False,
            message=f"Database connection failed: {str(e)}"
        )
        errors.append(f"Database connection error: {str(e)}")

    # Check 2: Admin / LLM / skip flags from SystemSetup
    is_installed, has_admin, has_user_staff, has_llm_config, skip_llm_config = _check_system_installed(db)

    if has_admin:
        admin_count = db.query(Staff).filter(Staff.deleted_at.is_(None)).count()
        checks["admin_exists"] = SetupCheckResult(
            passed=True,
            message=f"Admin account exists ({admin_count} staff member(s) found)",
        )
    else:
        checks["admin_exists"] = SetupCheckResult(
            passed=False,
            message="No admin account found",
        )
        errors.append("Admin account has not been created")

    # Check 3: LLM configured or explicitly skipped
    if has_llm_config:
        llm_count = (
            db.query(AIProvider)
            .filter(
                AIProvider.deleted_at.is_(None),
                AIProvider.is_active == True,
            )
            .count()
        )
        checks["llm_configured"] = SetupCheckResult(
            passed=True,
            message=f"LLM provider configured ({llm_count} active provider(s))",
        )
    elif skip_llm_config:
        checks["llm_configured"] = SetupCheckResult(
            passed=True,
            message="LLM configuration was skipped during setup; no provider configured yet",
        )
        warnings.append(
            "LLM configuration was skipped during setup; you can configure a provider later."
        )
    else:
        checks["llm_configured"] = SetupCheckResult(
            passed=False,
            message="No active LLM provider found",
        )
        errors.append("LLM provider has not been configured")

    # Check 4: Project exists
    project_count = db.query(Project).filter(Project.deleted_at.is_(None)).count()
    if project_count > 0:
        checks["project_exists"] = SetupCheckResult(
            passed=True,
            message=f"Project exists ({project_count} project(s) found)",
        )
    else:
        checks["project_exists"] = SetupCheckResult(
            passed=False,
            message="No project found",
        )
        errors.append("No project has been created")

    # Check 5: Installation status in SystemSetup
    if is_installed:
        checks["installation_status"] = SetupCheckResult(
            passed=True,
            message="Installation is marked as complete in system_setup table",
        )
    else:
        checks["installation_status"] = SetupCheckResult(
            passed=False,
            message="Installation is not marked as complete in system_setup table",
        )
        errors.append("System installation has not been completed in setup wizard")

    # Overall validity
    is_valid = all(check.passed for check in checks.values())

    # Add warnings if partially configured
    if has_admin and not has_llm_config and not skip_llm_config:
        warnings.append("Admin created but LLM provider not configured yet")
    elif has_llm_config and not has_admin:
        warnings.append("LLM provider configured but no admin account exists")
    
    # Warning if no user staff exists
    if has_admin and not has_user_staff:
        warnings.append("No user staff members found; consider adding customer service staff")

    logger.info(
        f"Setup verification: valid={is_valid}, "
        f"errors={len(errors)}, warnings={len(warnings)}",
    )

    return VerifySetupResponse(
        is_valid=is_valid,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


@router.post(
    "/staff",
    response_model=BatchCreateStaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch create staff members during setup",
    description=(
        "Batch create non-admin staff members (user role) during initial system setup. "
        "This endpoint can ONLY be called when the system is NOT yet installed. "
        "Once the system installation is complete (is_installed=True), this endpoint "
        "will be disabled for security reasons. Use the normal staff management "
        "endpoints after installation is complete."
    ),
)
async def batch_create_staff(
    staff_data: BatchCreateStaffRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> BatchCreateStaffResponse:
    """
    Batch create staff members during initial setup.

    SECURITY: This endpoint is ONLY available during setup (before is_installed=True).
    Once the system is installed, this endpoint returns 403 Forbidden.

    This endpoint:
    1. Checks that the system is NOT yet installed
    2. Checks that an admin account exists (required before creating staff)
    3. Creates staff members with 'user' role (not admin)
    4. Skips any usernames that already exist
    5. Returns the list of created staff members

    After installation, use the authenticated staff management endpoints instead.
    """
    # Ensure we have a SystemSetup row and check installation state
    setup = _get_or_create_system_setup(db)

    # CRITICAL: Block this endpoint after installation for security
    if setup.is_installed:
        logger.warning(
            f"SECURITY: Attempt to call batch staff creation after installation: {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "System installation is already complete. "
                "This setup endpoint is disabled for security reasons. "
                "Please use the authenticated staff management endpoints instead."
            ),
        )

    # Check if admin exists (required before creating staff)
    if not setup.admin_created:
        logger.warning("Attempt to create staff before admin account exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account must be created before adding staff members"
        )

    # Get the project (created during admin setup)
    project = db.query(Project).filter(Project.deleted_at.is_(None)).first()
    if not project:
        logger.error("No project found despite admin existing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System error: No project found"
        )

    created_staff = []
    skipped_usernames = []

    for item in staff_data.staff_list:
        # Check if username already exists
        existing = db.query(Staff).filter(
            Staff.username == item.username,
            Staff.deleted_at.is_(None),
        ).first()

        if existing:
            logger.info(f"Staff username already exists, skipping: {item.username}")
            skipped_usernames.append(item.username)
            continue

        # Create staff with user role (NOT admin)
        password_hash = get_password_hash(item.password)
        staff = Staff(
            project_id=project.id,
            username=item.username,
            password_hash=password_hash,
            name=item.name,
            nickname=item.nickname or item.name or item.username,
            description=item.description,
            role=StaffRole.USER,  # Always user role, never admin
            status=StaffStatus.OFFLINE,
        )
        db.add(staff)
        created_staff.append(staff)

    if created_staff:
        # Check if VisitorAssignmentRule exists for this project, create default if not
        existing_rule = db.query(VisitorAssignmentRule).filter(
            VisitorAssignmentRule.project_id == project.id
        ).first()
        
        if not existing_rule:
            # Create default visitor assignment rule
            default_rule = VisitorAssignmentRule(
                project_id=project.id,
                llm_assignment_enabled=False,  # Disable LLM by default, use load balancing
                timezone="Asia/Shanghai",
                service_weekdays=[1, 2, 3, 4, 5],  # Monday to Friday
                service_start_time="09:00",
                service_end_time="18:00",
                max_concurrent_chats=10,
                auto_close_hours=48,
            )
            db.add(default_rule)
            logger.info(
                f"Created default visitor assignment rule for project {project.id}"
            )
        
        db.commit()
        for staff in created_staff:
            db.refresh(staff)

        logger.info(
            f"Batch created {len(created_staff)} staff members during setup, "
            f"skipped {len(skipped_usernames)} existing usernames"
        )

    return BatchCreateStaffResponse(
        created_count=len(created_staff),
        staff_list=[
            StaffCreatedItem(
                id=staff.id,
                username=staff.username,
                name=staff.name,
                nickname=staff.nickname,
                created_at=staff.created_at,
            )
            for staff in created_staff
        ],
        skipped_usernames=skipped_usernames,
    )

