"""SQLAlchemy ORM models."""

from app.models.assignment import AssignmentType, VisitorAssignment
from app.models.platform import Platform, PlatformType, PlatformTypeDefinition
from app.models.project import Project
from app.models.system_setup import SystemSetup
from app.models.staff import Staff, StaffRole, StaffStatus
from app.models.tag import Tag, TagCategory
from app.models.visitor import Visitor
from app.models.visitor_ai_profile import VisitorAIProfile
from app.models.visitor_ai_insight import VisitorAIInsight
from app.models.visitor_system_info import VisitorSystemInfo
from app.models.visitor_activity import VisitorActivity
from app.models.visitor_tag import VisitorTag
from app.models.channel_member import ChannelMember
from app.models.chat_file import ChatFile
from app.models.manual_service_request import ManualServiceRequest
from app.models.visitor_customer_update import VisitorCustomerUpdate
from app.models.ai_provider import AIProvider
from app.models.ai_model import AIModel
from app.models.project_ai_config import ProjectAIConfig

__all__ = [
    # Models
    "Project",
    "Platform",
    "PlatformTypeDefinition",
    "Staff",
    "Visitor",
    "VisitorAssignment",
    "VisitorAIProfile",
    "VisitorAIInsight",
    "VisitorSystemInfo",
    "VisitorActivity",
    "ManualServiceRequest",
    "VisitorCustomerUpdate",
    "Tag",
    "VisitorTag",
    "ChannelMember",
    "ChatFile",
    "AIProvider",
    "AIModel",
    "ProjectAIConfig",
    "SystemSetup",
    # Enums
    "PlatformType",
    "StaffRole",
    "StaffStatus",
    "AssignmentType",
    "TagCategory",
]
