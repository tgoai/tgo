"""Logging configuration."""

import logging
import os

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that includes extra fields automatically."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        # Remove redundant fields added by default
        log_record.pop('levelname', None)
        log_record.pop('name', None)


class StartupFormatter(logging.Formatter):
    """Custom formatter for clean startup messages."""

    def format(self, record):
        # For startup messages, use clean format without timestamp/logger name
        if hasattr(record, 'startup') and record.startup:
            return record.getMessage()
        # For regular messages, use standard format
        return super().format(record)


def setup_logging() -> None:
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Configure console handler - use simple format for readability
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(StartupFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Configure file handler with JSON format (includes all extra fields)
    file_handler = logging.FileHandler("logs/app.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(CustomJsonFormatter(
        fmt="%(timestamp)s %(level)s %(logger)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def startup_log(message: str, level: int = logging.INFO) -> None:
    """Log a startup message with clean formatting."""
    logger = logging.getLogger("startup")
    record = logger.makeRecord(
        logger.name, level, "", 0, message, (), None
    )
    record.startup = True  # Mark as startup message
    logger.handle(record)
