from enum import IntEnum, Enum

# WuKongIM channel types
CHANNEL_TYPE_CUSTOMER_SERVICE = 251
CHANNEL_TYPE_PROJECT_STAFF = 249  # 项目坐席群组频道
SETUP_DEFAULT_AGENT_MODEL = "default"

# member_type
MEMBER_TYPE_STAFF = "staff"
MEMBER_TYPE_VISITOR = "visitor"


class MessageType(IntEnum):
    """WuKongIM message type constants."""
    # Standard message types (1-999)
    TEXT = 1
    IMAGE = 2
    FILE = 3
    VOICE = 4
    VIDEO = 5

    # System message types (1000-2000 reserved for system notifications)
    STAFF_ASSIGNED = 1000
    SESSION_CLOSED = 1001
    SESSION_TRANSFERRED = 1002
    MEMORY_CLEARED = 1003
