"""SQLAlchemy ORM models."""

from app.models.platform import Platform, PlatformType, PlatformTypeDefinition
from app.models.project import Project
from app.models.system_setup import SystemSetup
from app.models.staff import Staff, StaffRole, StaffStatus
from app.models.tag import Tag, TagCategory
from app.models.visitor import Visitor, VisitorServiceStatus, UNASSIGNED_STATUSES
from app.models.visitor_ai_profile import VisitorAIProfile
from app.models.visitor_ai_insight import VisitorAIInsight
from app.models.visitor_system_info import VisitorSystemInfo
from app.models.visitor_activity import VisitorActivity
from app.models.visitor_tag import VisitorTag
from app.models.channel_member import ChannelMember
from app.models.chat_file import ChatFile
from app.models.visitor_customer_update import VisitorCustomerUpdate
from app.models.ai_provider import AIProvider
from app.models.ai_model import AIModel
from app.models.project_ai_config import ProjectAIConfig
from app.models.project_onboarding import ProjectOnboardingProgress
from app.models.permission import Permission, RolePermission, ProjectRolePermission
from app.models.visitor_assignment_rule import VisitorAssignmentRule, DEFAULT_ASSIGNMENT_PROMPT
from app.models.visitor_assignment_history import VisitorAssignmentHistory, AssignmentSource
from app.models.visitor_session import VisitorSession, SessionStatus
from app.models.visitor_waiting_queue import (
    VisitorWaitingQueue,
    WaitingStatus,
    QueueSource,
    QueueUrgency,
    URGENCY_PRIORITY_MAP,
)
from app.models.channel_memory_clearance import ChannelMemoryClearance, ClearanceUserType
from app.models.store_credential import StoreCredential

__all__ = [
    # Models
    "Project",
    "Platform",
    "PlatformTypeDefinition",
    "Staff",
    "Visitor",
    "VisitorServiceStatus",
    "UNASSIGNED_STATUSES",
    "VisitorAIProfile",
    "VisitorAIInsight",
    "VisitorSystemInfo",
    "VisitorActivity",
    "VisitorCustomerUpdate",
    "Tag",
    "VisitorTag",
    "ChannelMember",
    "ChatFile",
    "AIProvider",
    "AIModel",
    "ProjectAIConfig",
    "ProjectOnboardingProgress",
    "SystemSetup",
    "Permission",
    "RolePermission",
    "ProjectRolePermission",
    "VisitorAssignmentRule",
    "DEFAULT_ASSIGNMENT_PROMPT",
    "VisitorAssignmentHistory",
    "VisitorSession",
    "VisitorWaitingQueue",
    "URGENCY_PRIORITY_MAP",
    "ChannelMemoryClearance",
    "StoreCredential",
    # Enums
    "PlatformType",
    "StaffRole",
    "StaffStatus",
    "AssignmentSource",
    "SessionStatus",
    "WaitingStatus",
    "QueueSource",
    "QueueUrgency",
    "TagCategory",
    "ClearanceUserType",
]
