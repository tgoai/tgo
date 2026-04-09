"""Development data initialization for easier testing and debugging."""

import logging
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import startup_log
from app.core.security import get_password_hash
from app.models.project import Project
from app.models.staff import Staff, StaffRole, StaffStatus
from app.models.permission import Permission, RolePermission, ProjectRolePermission

logger = logging.getLogger("app.core.dev_data")


# Default permission definitions: (resource, action, description)
DEFAULT_PERMISSIONS: List[Tuple[str, str, str]] = [
    # Staff permissions
    ("staff", "create", "Create new staff members"),
    ("staff", "read", "View staff member details"),
    ("staff", "update", "Update staff member information"),
    ("staff", "delete", "Delete staff members"),
    ("staff", "list", "List all staff members"),
    
    # Visitor permissions
    ("visitors", "create", "Create new visitors"),
    ("visitors", "read", "View visitor details"),
    ("visitors", "update", "Update visitor information"),
    ("visitors", "delete", "Delete visitors"),
    ("visitors", "list", "List all visitors"),
    
    # Visitor Assignment Rules permissions
    ("visitor_assignment_rules", "read", "View visitor assignment rule"),
    ("visitor_assignment_rules", "update", "Update visitor assignment rule"),
    
    # Chat permissions
    ("chat", "read", "Read chat messages"),
    ("chat", "send", "Send chat messages"),
    
    # AI Agents permissions
    ("ai_agents", "create", "Create AI agents"),
    ("ai_agents", "read", "View AI agent details"),
    ("ai_agents", "update", "Update AI agents"),
    ("ai_agents", "delete", "Delete AI agents"),
    ("ai_agents", "list", "List all AI agents"),
    
    # RAG Collections permissions
    ("rag_collections", "create", "Create RAG collections"),
    ("rag_collections", "read", "View RAG collection details"),
    ("rag_collections", "update", "Update RAG collections"),
    ("rag_collections", "delete", "Delete RAG collections"),
    ("rag_collections", "list", "List all RAG collections"),
    
    # RAG Files permissions
    ("rag_files", "create", "Upload RAG files"),
    ("rag_files", "read", "View RAG file details"),
    ("rag_files", "delete", "Delete RAG files"),
    ("rag_files", "list", "List all RAG files"),
    
    # Tags permissions
    ("tags", "create", "Create tags"),
    ("tags", "read", "View tag details"),
    ("tags", "update", "Update tags"),
    ("tags", "delete", "Delete tags"),
    ("tags", "list", "List all tags"),
    
    # Platforms permissions
    ("platforms", "create", "Create platforms"),
    ("platforms", "read", "View platform details"),
    ("platforms", "update", "Update platforms"),
    ("platforms", "delete", "Delete platforms"),
    ("platforms", "list", "List all platforms"),
    
    # Permissions management (admin only by design)
    ("permissions", "read", "View permission definitions"),
    ("permissions", "manage", "Manage role permissions"),
]

# Default GLOBAL permissions for 'user' role - inherited by ALL projects
# When new permissions are added, only update this list
DEFAULT_USER_GLOBAL_PERMISSIONS: List[Tuple[str, str]] = [
    # Users can view staff list but not manage
    ("staff", "read"),
    ("staff", "list"),
    
    # Users have full visitor access
    ("visitors", "create"),
    ("visitors", "read"),
    ("visitors", "update"),
    ("visitors", "list"),
    
    # Users can view visitor assignment rules but not manage
    ("visitor_assignment_rules", "read"),
    
    # Users can chat
    ("chat", "read"),
    ("chat", "send"),
    
    # Users can view AI agents but not manage
    ("ai_agents", "read"),
    ("ai_agents", "list"),
    
    # Users can view RAG but not manage
    ("rag_collections", "read"),
    ("rag_collections", "list"),
    ("rag_files", "read"),
    ("rag_files", "list"),
    
    # Users can manage tags
    ("tags", "create"),
    ("tags", "read"),
    ("tags", "update"),
    ("tags", "delete"),
    ("tags", "list"),
    
    # Users can view platforms but not manage
    ("platforms", "read"),
    ("platforms", "list"),
]


def ensure_permissions_seed(db: Optional[Session] = None) -> None:
    """
    Ensure default permissions are seeded in the database.
    
    This function seeds:
    1. Permission definitions (api_permissions table)
    2. Global role permissions (api_role_permissions table) - inherited by all projects
    
    This function is idempotent - it will only create records that don't exist.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True
    
    try:
        # Step 1: Seed permission definitions
        for resource, action, description in DEFAULT_PERMISSIONS:
            existing = db.query(Permission).filter(
                Permission.resource == resource,
                Permission.action == action,
            ).first()
            
            if not existing:
                permission = Permission(
                    resource=resource,
                    action=action,
                    description=description,
                )
                db.add(permission)
                logger.info(f"Created permission: {resource}:{action}")
        
        db.commit()
        logger.info("Permission definitions seeded successfully")
        
        # Step 2: Seed global role permissions for 'user' role
        # These are inherited by ALL projects automatically
        all_permissions = db.query(Permission).all()
        permission_map = {
            (p.resource, p.action): p.id for p in all_permissions
        }
        
        for resource, action in DEFAULT_USER_GLOBAL_PERMISSIONS:
            permission_id = permission_map.get((resource, action))
            if not permission_id:
                logger.warning(f"Permission not found for global role: {resource}:{action}")
                continue
            
            # Check if global role permission already exists
            existing = db.query(RolePermission).filter(
                RolePermission.role == "user",
                RolePermission.permission_id == permission_id,
            ).first()
            
            if not existing:
                role_permission = RolePermission(
                    role="user",
                    permission_id=permission_id,
                )
                db.add(role_permission)
                logger.debug(f"Created global user role permission: {resource}:{action}")
        
        db.commit()
        logger.info("Global role permissions seeded successfully")
        
    except Exception as e:
        logger.error(f"Failed to seed permissions: {e}")
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


def add_project_role_permission(
    project_id: UUID,
    role: str,
    resource: str,
    action: str,
    db: Optional[Session] = None,
) -> bool:
    """
    Add a project-specific permission for a role.
    
    This adds an ADDITIONAL permission on top of global permissions.
    Projects can only ADD permissions, not remove global ones.
    
    Args:
        project_id: The project ID
        role: The role name (user, agent)
        resource: The resource name
        action: The action name
        db: Optional database session
    
    Returns:
        True if permission was added, False if it already exists
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True
    
    try:
        # Find the permission
        permission = db.query(Permission).filter(
            Permission.resource == resource,
            Permission.action == action,
        ).first()
        
        if not permission:
            logger.warning(f"Permission not found: {resource}:{action}")
            return False
        
        # Check if project role permission already exists
        existing = db.query(ProjectRolePermission).filter(
            ProjectRolePermission.role == role,
            ProjectRolePermission.permission_id == permission.id,
            ProjectRolePermission.project_id == project_id,
        ).first()
        
        if existing:
            return False
        
        # Create project role permission
        project_permission = ProjectRolePermission(
            role=role,
            permission_id=permission.id,
            project_id=project_id,
        )
        db.add(project_permission)
        db.commit()
        
        logger.info(f"Added project permission {resource}:{action} for role {role} in project {project_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add project role permission: {e}")
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


def log_startup_banner() -> None:
    """Log beautiful startup banner."""
    startup_log("╔══════════════════════════════════════════════════════════════╗")
    startup_log("║                    🚀 TGO API Service                        ║")
    startup_log("║                  Core Business Logic Service                 ║")
    startup_log("╚══════════════════════════════════════════════════════════════╝")
    startup_log("")
    startup_log(f"📦 Version: {settings.PROJECT_VERSION}")
    startup_log(f"🌍 Environment: {settings.ENVIRONMENT.upper()}")
    startup_log("")
