# Centralized Logging System

## Overview

The TGO RAG Service uses a centralized logging system built on **Python's standard library `logging`** that provides:

- **Structured logging** with JSON output for production and human-readable output for development
- **Automatic context propagation** (request_id, project_id, user_id) across async operations
- **Consistent log level filtering** across all modules
- **Simple, unified API** for getting and using loggers
- **Backward compatibility** with structlog-style keyword arguments

## Quick Start

### Basic Usage

```python
from rag_service.logging_config import get_logger

logger = get_logger(__name__)

# Simple logging
logger.info("Processing started")
logger.error("Processing failed", error=str(e))

# Logging with context (structlog-style - backward compatible)
logger.info("File uploaded", file_id=file_id, size_bytes=file_size)
logger.warning("Rate limit approaching", current_count=95, limit=100)

# Standard logging style also works
logger.info("File uploaded", extra={"file_id": file_id, "size_bytes": file_size})
```

### Using Context Variables

Context variables are automatically included in all log entries within the same async context:

```python
from rag_service.logging_config import get_logger, set_request_context

logger = get_logger(__name__)

# Set context at the beginning of request processing
set_request_context(
    request_id="req-123",
    project_id="proj-456",
    user_id="user-789"
)

# All subsequent logs will automatically include these values
logger.info("Processing file")  
# Output: {"event": "Processing file", "request_id": "req-123", "project_id": "proj-456", ...}

logger.error("Failed to process", error="timeout")
# Output: {"event": "Failed to process", "error": "timeout", "request_id": "req-123", ...}
```

## Configuration

### Environment-Based Configuration

The logging system automatically configures itself based on the application settings:

- **Development** (`environment=development`): Human-readable console output with colors
- **Production** (any other environment): JSON output for log aggregation systems

### Log Levels

Configure the log level via the `LOG_LEVEL` environment variable or `settings.log_level`:

```bash
export LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Manual Configuration

For advanced use cases, you can manually configure logging:

```python
from rag_service.logging_config import configure_logging

configure_logging(
    log_level="DEBUG",
    json_output=True,  # False for console output
    force_reconfigure=True
)
```

## API Reference

### `get_logger(name: str)`

Get a configured logger instance. This is the main API for getting loggers.

**Parameters:**
- `name`: Logger name, typically `__name__` of the calling module

**Returns:**
- Configured `logging.LoggerAdapter` instance with backward compatibility support

**Example:**
```python
logger = get_logger(__name__)
# Both styles work:
logger.info("Operation completed", duration_ms=123)  # structlog-style
logger.info("Operation completed", extra={"duration_ms": 123})  # standard logging style
```

### `set_request_context(request_id, project_id, user_id)`

Set context variables for the current async context. These values are automatically included in all log entries.

**Parameters:**
- `request_id` (optional): Unique request identifier
- `project_id` (optional): Project identifier  
- `user_id` (optional): User identifier

**Example:**
```python
set_request_context(request_id="req-abc", project_id="proj-xyz")
```

### `clear_request_context()`

Clear all context variables for the current async context.

**Example:**
```python
clear_request_context()
```

### `init_logging_from_settings()`

Initialize logging using application settings. Called automatically at application startup.

## Usage Examples

### In Routers

```python
from fastapi import APIRouter
from rag_service.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("/files")
async def upload_file(file: UploadFile):
    logger.info("File upload started", filename=file.filename, content_type=file.content_type)
    
    try:
        # Process file
        result = await process_file(file)
        logger.info("File upload completed", file_id=result.id, size=result.size)
        return result
    except Exception as e:
        logger.error("File upload failed", filename=file.filename, error=str(e), exc_info=True)
        raise
```

### In Services

```python
from rag_service.logging_config import get_logger

logger = get_logger(__name__)

class EmbeddingService:
    async def generate_embeddings(self, texts: list[str], project_id: str):
        logger.info("Generating embeddings", text_count=len(texts), project_id=project_id)
        
        try:
            embeddings = await self._call_api(texts)
            logger.info("Embeddings generated", count=len(embeddings), dimensions=len(embeddings[0]))
            return embeddings
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e), exc_info=True)
            raise
```

### In Celery Tasks

```python
from rag_service.logging_config import get_logger, set_request_context
from .celery_app import celery_app

logger = get_logger(__name__)

@celery_app.task
def process_document(file_id: str, project_id: str):
    # Set context for all logs in this task
    set_request_context(project_id=project_id)
    
    logger.info("Document processing started", file_id=file_id)
    
    try:
        # Process document
        result = do_processing(file_id)
        logger.info("Document processing completed", file_id=file_id, chunks=result.chunk_count)
        return result
    except Exception as e:
        logger.error("Document processing failed", file_id=file_id, error=str(e), exc_info=True)
        raise
```

## Log Output Formats

### Development (Console Output)

```
2025-11-19T10:30:45.123456Z [info     ] Processing file started        file_id=abc-123 project_id=proj-456 request_id=req-789
2025-11-19T10:30:45.234567Z [error    ] Processing failed              error=timeout file_id=abc-123
```

### Production (JSON Output)

```json
{"event": "Processing file started", "file_id": "abc-123", "project_id": "proj-456", "request_id": "req-789", "level": "info", "timestamp": "2025-11-19T10:30:45.123456Z", "logger": "rag_service.services.processing"}
{"event": "Processing failed", "error": "timeout", "file_id": "abc-123", "level": "error", "timestamp": "2025-11-19T10:30:45.234567Z", "logger": "rag_service.services.processing"}
```

## Best Practices

1. **Always use `get_logger(__name__)`** instead of `logging.getLogger()` or `structlog.get_logger()`
2. **Include relevant context** in log messages using keyword arguments
3. **Use appropriate log levels**: DEBUG for detailed info, INFO for normal operations, WARNING for issues, ERROR for failures
4. **Set request context early** in request handlers or task functions
5. **Use `exc_info=True`** when logging exceptions to include stack traces
6. **Avoid logging sensitive data** like passwords, API keys, or PII

## Migration Guide

### From structlog to Standard Logging

The logging system has been refactored to use Python's standard library `logging` instead of `structlog`, but **maintains full backward compatibility**. No code changes are required!

**Before (structlog):**
```python
from rag_service.logging_config import get_logger
logger = get_logger(__name__)

logger.info("Processing file", file_id=file_id, status="started")
```

**After (standard logging - same code works!):**
```python
from rag_service.logging_config import get_logger
logger = get_logger(__name__)

# This still works - backward compatible!
logger.info("Processing file", file_id=file_id, status="started")

# Standard logging style also works
logger.info("Processing file", extra={"file_id": file_id, "status": "started"})
```

### From Basic logging.getLogger()

If you were using basic `logging.getLogger()`:

**Before:**
```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Processing file {file_id}")
```

**After:**
```python
from rag_service.logging_config import get_logger
logger = get_logger(__name__)

logger.info("Processing file", file_id=file_id)
```

## Implementation Details

### Architecture

The logging system is built entirely on Python's standard library `logging` module with custom components:

1. **ContextFilter**: A `logging.Filter` that automatically injects context variables (request_id, project_id, user_id) from `contextvars` into log records
2. **JSONFormatter**: A `logging.Formatter` that outputs structured JSON logs for production
3. **ConsoleFormatter**: A `logging.Formatter` that outputs colored, human-readable logs for development
4. **LoggerAdapter**: A custom `logging.LoggerAdapter` that provides backward compatibility with structlog-style keyword arguments

### Why Standard Library Logging?

The refactor from `structlog` to standard library `logging` provides:

- **Simpler dependencies**: No external logging library required
- **Better compatibility**: Works seamlessly with all Python logging ecosystem tools
- **Easier debugging**: Standard logging is familiar to all Python developers
- **Same features**: All structlog features (JSON output, context propagation, structured logging) are maintained
- **Backward compatibility**: Existing code continues to work without changes

### Context Propagation

Context variables use Python's `contextvars` module, which provides async-safe context tracking:

```python
from contextvars import ContextVar

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
project_id_ctx: ContextVar[Optional[str]] = ContextVar("project_id", default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
```

The `ContextFilter` reads these variables and adds them to every log record automatically.

## Troubleshooting

### Logs Not Appearing

1. Check the `LOG_LEVEL` environment variable
2. Ensure logging is initialized (happens automatically in main.py)
3. Verify you're using `get_logger(__name__)` not `logging.getLogger()`

### Context Not Propagating

1. Ensure `set_request_context()` is called before logging
2. Verify you're in the same async context (context variables are async-local)
3. Call `clear_request_context()` at the end of request processing

### Wrong Output Format

1. Check the `environment` setting (development vs production)
2. Manually configure with `configure_logging(json_output=True/False)`

### Reserved Keyword Conflicts

Avoid using these reserved keywords as log field names (they conflict with logging internals):
- `level`, `pathname`, `lineno`, `msg`, `args`, `func`
- Use alternatives like `log_level`, `file_path`, `line_number`, etc.

