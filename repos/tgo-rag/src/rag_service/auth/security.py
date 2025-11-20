"""
Security utilities for API key management and validation.
"""

import hashlib
import secrets
import time
from typing import Optional
from uuid import UUID

from ..logging_config import get_logger

logger = get_logger(__name__)


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure API key.
    
    Args:
        length: Length of the API key
        
    Returns:
        Secure random API key string
    """
    return secrets.token_urlsafe(length)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        api_key: Plain text API key
        hashed_key: Stored hash
        
    Returns:
        True if API key matches hash
    """
    return hash_api_key(api_key) == hashed_key


class SecurityAuditLogger:
    """Logger for security-related events and audit trails."""
    
    @staticmethod
    def log_api_key_validation(
        api_key_prefix: str,
        project_id: Optional[UUID],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log API key validation attempts for audit purposes.
        
        Args:
            api_key_prefix: First 8 characters of API key for identification
            project_id: Project ID if validation successful
            success: Whether validation was successful
            ip_address: Client IP address
            user_agent: Client user agent
        """
        logger.info(
            "API key validation attempt",
            api_key_prefix=api_key_prefix,
            project_id=str(project_id) if project_id else None,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=time.time()
        )
    
    @staticmethod
    def log_project_access(
        project_id: UUID,
        operation: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log project-scoped operations for audit purposes.
        
        Args:
            project_id: Project ID
            operation: Operation performed (create, read, update, delete, search)
            resource_type: Type of resource (file, collection, document)
            resource_id: ID of the specific resource
            ip_address: Client IP address
        """
        logger.info(
            "Project operation",
            project_id=str(project_id),
            operation=operation,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
            timestamp=time.time()
        )
    
    @staticmethod
    def log_security_violation(
        violation_type: str,
        details: str,
        api_key_prefix: Optional[str] = None,
        project_id: Optional[UUID] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log security violations for monitoring and alerting.
        
        Args:
            violation_type: Type of violation (unauthorized_access, invalid_api_key, etc.)
            details: Detailed description of the violation
            api_key_prefix: API key prefix if relevant
            project_id: Project ID if relevant
            ip_address: Client IP address
        """
        logger.warning(
            "Security violation detected",
            violation_type=violation_type,
            details=details,
            api_key_prefix=api_key_prefix,
            project_id=str(project_id) if project_id else None,
            ip_address=ip_address,
            timestamp=time.time()
        )
