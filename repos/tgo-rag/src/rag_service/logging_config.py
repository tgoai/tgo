"""
Centralized logging configuration for TGO RAG Service.

This module provides a unified logging interface with:
- Structured logging using Python's standard library logging
- JSON output for production, human-readable for development
- Automatic context propagation (request_id, project_id, etc.)
- Consistent log level filtering across all modules
- Simple API: get_logger(__name__)

Usage:
    from rag_service.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("Processing started", extra={"project_id": project_id, "file_count": 10})
    logger.error("Processing failed", extra={"error": str(e)}, exc_info=True)
"""

import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Context variables for request tracking across async operations
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
project_id_ctx: ContextVar[Optional[str]] = ContextVar("project_id", default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

# Global flag to track if logging has been configured
_logging_configured = False


class ContextFilter(logging.Filter):
    """
    Logging filter that automatically adds context variables to log records.

    Injects request_id, project_id, and user_id from context variables if available.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context variables to the log record."""
        # Add context variables if they exist
        request_id = request_id_ctx.get()
        if request_id:
            record.request_id = request_id

        project_id = project_id_ctx.get()
        if project_id:
            record.project_id = project_id

        user_id = user_id_ctx.get()
        if user_id:
            record.user_id = user_id

        return True


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging output.

    Formats log records as JSON with timestamp, level, logger name, message,
    and any additional context or extra fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        # Build the base log entry
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }

        # Add context variables if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "project_id"):
            log_data["project_id"] = record.project_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # Add any extra fields passed via extra={} parameter
        if hasattr(record, "__dict__"):
            # Standard logging attributes to exclude
            exclude_attrs = {
                "name", "msg", "args", "created", "filename", "funcName", "levelname",
                "levelno", "lineno", "module", "msecs", "message", "pathname", "process",
                "processName", "relativeCreated", "thread", "threadName", "exc_info",
                "exc_text", "stack_info", "request_id", "project_id", "user_id"
            }

            for key, value in record.__dict__.items():
                if key not in exclude_attrs and not key.startswith("_"):
                    log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        return json.dumps(log_data)


class ConsoleFormatter(logging.Formatter):
    """
    Custom console formatter for human-readable development output.

    Formats log records with colors and structured key-value pairs.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record for console output."""
        # Get color for log level
        color = self.COLORS.get(record.levelname, "")

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Build the base message
        parts = [
            f"{timestamp}",
            f"{color}[{record.levelname.lower():8}]{self.RESET}",
            f"{self.BOLD}{record.getMessage()}{self.RESET}",
        ]

        # Collect context and extra fields
        extra_fields = {}

        # Add context variables
        if hasattr(record, "request_id"):
            extra_fields["request_id"] = record.request_id
        if hasattr(record, "project_id"):
            extra_fields["project_id"] = record.project_id
        if hasattr(record, "user_id"):
            extra_fields["user_id"] = record.user_id

        # Add extra fields
        exclude_attrs = {
            "name", "msg", "args", "created", "filename", "funcName", "levelname",
            "levelno", "lineno", "module", "msecs", "message", "pathname", "process",
            "processName", "relativeCreated", "thread", "threadName", "exc_info",
            "exc_text", "stack_info", "request_id", "project_id", "user_id"
        }

        for key, value in record.__dict__.items():
            if key not in exclude_attrs and not key.startswith("_"):
                extra_fields[key] = value

        # Format extra fields as key=value pairs
        if extra_fields:
            extra_str = " ".join(f"{k}={v}" for k, v in extra_fields.items())
            parts.append(extra_str)

        message = " ".join(parts)

        # Add exception info if present
        if record.exc_info:
            message += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return message


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = True,
    force_reconfigure: bool = False
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, use JSON output (production). If False, use console output (development)
        force_reconfigure: If True, reconfigure even if already configured
    """
    global _logging_configured

    if _logging_configured and not force_reconfigure:
        return

    # Normalize log level
    log_level = log_level.upper()
    level = getattr(logging, log_level, logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()

    # Clear existing handlers if reconfiguring
    if force_reconfigure:
        root_logger.handlers.clear()

    # Set log level
    root_logger.setLevel(level)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Add context filter to inject context variables
    context_filter = ContextFilter()
    handler.addFilter(context_filter)

    # Set formatter based on output mode
    if json_output:
        formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter()

    handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(handler)

    # Prevent propagation to avoid duplicate logs
    root_logger.propagate = False

    _logging_configured = True


class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom logger adapter that provides backward compatibility with structlog-style logging.

    Allows both standard logging style:
        logger.info("message", extra={"key": "value"})

    And structlog-style (for backward compatibility):
        logger.info("message", key="value")
    """

    def process(self, msg, kwargs):
        """Process the logging call to handle both styles."""
        # Extract any keyword arguments that aren't standard logging kwargs
        # Note: We need to be careful about reserved kwargs that logging methods use internally
        standard_kwargs = {
            'extra', 'exc_info', 'stack_info', 'stacklevel',
            # Internal logging parameters that should not be overridden
            'level', 'pathname', 'lineno', 'msg', 'args', 'func'
        }

        # Collect non-standard kwargs as extra fields
        extra_fields = {}
        keys_to_remove = []

        for key, value in kwargs.items():
            if key not in standard_kwargs:
                extra_fields[key] = value
                keys_to_remove.append(key)

        # Remove non-standard kwargs from kwargs dict
        for key in keys_to_remove:
            del kwargs[key]

        # Merge with existing extra dict if present
        if 'extra' in kwargs:
            if isinstance(kwargs['extra'], dict):
                kwargs['extra'].update(extra_fields)
            else:
                kwargs['extra'] = extra_fields
        elif extra_fields:
            kwargs['extra'] = extra_fields

        return msg, kwargs


def get_logger(name: str) -> LoggerAdapter:
    """
    Get a configured logger instance.

    This is the main API for getting loggers throughout the application.
    The logger will automatically include context variables (request_id, project_id, etc.)

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured LoggerAdapter instance that supports both standard logging
        and structlog-style keyword arguments

    Example:
        logger = get_logger(__name__)
        # Both styles work:
        logger.info("Processing file", file_id=file_id, status="started")
        logger.info("Processing file", extra={"file_id": file_id, "status": "started"})
    """
    # Ensure logging is configured (will be no-op if already configured)
    if not _logging_configured:
        # Auto-configure with defaults if not yet configured
        configure_logging()

    base_logger = logging.getLogger(name)
    return LoggerAdapter(base_logger, {})


def set_request_context(
    request_id: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> None:
    """
    Set context variables for the current async context.

    These values will be automatically included in all log entries within this context.

    Args:
        request_id: Unique request identifier
        project_id: Project identifier
        user_id: User identifier

    Example:
        set_request_context(request_id="req-123", project_id="proj-456")
        logger.info("Processing")  # Will include request_id and project_id
    """
    if request_id is not None:
        request_id_ctx.set(request_id)
    if project_id is not None:
        project_id_ctx.set(project_id)
    if user_id is not None:
        user_id_ctx.set(user_id)


def clear_request_context() -> None:
    """
    Clear all context variables for the current async context.

    Useful for cleanup after request processing.
    """
    request_id_ctx.set(None)
    project_id_ctx.set(None)
    user_id_ctx.set(None)


def init_logging_from_settings() -> None:
    """
    Initialize logging using application settings.

    This should be called once at application startup.
    Reads configuration from settings and configures logging accordingly.
    """
    from .config import get_settings

    settings = get_settings()

    # Determine output format based on environment
    json_output = settings.environment.lower() != "development"

    configure_logging(
        log_level=settings.log_level,
        json_output=json_output,
        force_reconfigure=True
    )

