# Logging Refactor: From structlog to Standard Library

## Summary

Successfully refactored the TGO RAG Service logging system from `structlog` to Python's standard library `logging` module while maintaining **100% backward compatibility**. All existing code continues to work without any modifications.

## What Changed

### Core Implementation

**Before:**
- Used `structlog` library for structured logging
- Required external dependency
- Used structlog processors and renderers

**After:**
- Uses Python's standard library `logging` module exclusively
- No external logging dependencies required
- Custom formatters and filters provide same functionality

### Key Components

1. **ContextFilter** (`logging.Filter`)
   - Automatically injects context variables (request_id, project_id, user_id) into log records
   - Uses Python's `contextvars` for async-safe context tracking

2. **JSONFormatter** (`logging.Formatter`)
   - Outputs structured JSON logs for production environments
   - Includes timestamp, level, logger name, message, context, and extra fields
   - Formats exceptions with type, message, and traceback

3. **ConsoleFormatter** (`logging.Formatter`)
   - Outputs colored, human-readable logs for development
   - Includes timestamp, colored log level, message, and key=value pairs
   - ANSI color codes for different log levels

4. **LoggerAdapter** (`logging.LoggerAdapter`)
   - Provides backward compatibility with structlog-style keyword arguments
   - Allows both `logger.info("msg", key=value)` and `logger.info("msg", extra={"key": value})`
   - Automatically converts keyword args to `extra` dict

### Files Modified

- **src/rag_service/logging_config.py** - Complete rewrite using standard library
- **docs/LOGGING.md** - Updated documentation
- **tests/test_logging_config.py** - Tests remain compatible (no changes needed)

### Files Created

- **test_logging_refactor.py** - Comprehensive test suite for the refactored system
- **docs/LOGGING_STDLIB_REFACTOR.md** - This document

## Benefits

### 1. Simplified Dependencies
- Removed `structlog` dependency
- Uses only Python standard library
- Easier to maintain and debug

### 2. Better Compatibility
- Works with all Python logging ecosystem tools
- Compatible with standard logging handlers and filters
- Easier integration with third-party libraries

### 3. Familiar API
- Standard `logging` module is familiar to all Python developers
- Easier onboarding for new team members
- Better IDE support and autocomplete

### 4. Same Features
- ✅ JSON output for production
- ✅ Console output for development
- ✅ Automatic context propagation
- ✅ Structured logging with key-value pairs
- ✅ Exception logging with tracebacks
- ✅ Consistent log level filtering

### 5. Backward Compatibility
- ✅ All existing log statements work without changes
- ✅ Supports both structlog-style and standard logging style
- ✅ No breaking changes

## Usage Examples

### Structlog-Style (Backward Compatible)

```python
from rag_service.logging_config import get_logger

logger = get_logger(__name__)

# This still works exactly as before!
logger.info("Processing file", file_id="abc-123", size=1024)
logger.error("Processing failed", error="timeout", exc_info=True)
```

### Standard Logging Style

```python
from rag_service.logging_config import get_logger

logger = get_logger(__name__)

# Standard logging style also works
logger.info("Processing file", extra={"file_id": "abc-123", "size": 1024})
logger.error("Processing failed", extra={"error": "timeout"}, exc_info=True)
```

### Context Propagation

```python
from rag_service.logging_config import get_logger, set_request_context

logger = get_logger(__name__)

# Set context once
set_request_context(request_id="req-123", project_id="proj-456")

# All subsequent logs automatically include context
logger.info("Processing started")  
# Output includes: request_id=req-123 project_id=proj-456

logger.error("Processing failed")
# Output includes: request_id=req-123 project_id=proj-456
```

## Output Formats

### Development (Console)

```
2025-11-19 04:00:43 [info    ] Processing file file_id=abc-123 size=1024 request_id=req-123
2025-11-19 04:00:43 [error   ] Processing failed error=timeout request_id=req-123
```

### Production (JSON)

```json
{"timestamp": "2025-11-19T04:00:43.400212+00:00", "level": "info", "logger": "rag_service.services.processing", "event": "Processing file", "file_id": "abc-123", "size": 1024, "request_id": "req-123"}
{"timestamp": "2025-11-19T04:00:43.500123+00:00", "level": "error", "logger": "rag_service.services.processing", "event": "Processing failed", "error": "timeout", "request_id": "req-123"}
```

## Testing

All tests pass successfully:

```bash
$ python3 test_logging_refactor.py

Testing Refactored Logging System
==================================================
✓ Basic logging works
✓ Structured logging (keyword args) works
✓ Standard logging with extra={} works
✓ Context propagation works
✓ JSON output works
✓ Exception logging works
✓ All log levels work
✓ Multiple loggers work
==================================================
✅ All tests passed!
```

## Migration Impact

### Breaking Changes
**None** - The refactor is 100% backward compatible.

### Required Actions
**None** - No code changes required. All existing code continues to work.

### Optional Improvements

While not required, you can optionally update code to use standard logging style:

```python
# Old (still works)
logger.info("Message", key="value")

# New (also works, more explicit)
logger.info("Message", extra={"key": "value"})
```

## Technical Details

### Context Variables

Uses Python's `contextvars` module for async-safe context tracking:

```python
from contextvars import ContextVar

request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
project_id_ctx: ContextVar[Optional[str]] = ContextVar("project_id", default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
```

### Custom Filter

The `ContextFilter` reads context variables and adds them to log records:

```python
class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_ctx.get()
        if request_id:
            record.request_id = request_id
        # ... similar for project_id and user_id
        return True
```

### Custom Formatters

- **JSONFormatter**: Converts log records to JSON with all fields
- **ConsoleFormatter**: Formats logs with colors and key=value pairs

### LoggerAdapter

Provides backward compatibility by converting keyword arguments to `extra` dict:

```python
class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        # Extract non-standard kwargs as extra fields
        # Merge with existing extra dict
        # Return processed msg and kwargs
```

## Conclusion

The refactor successfully simplifies the logging architecture by using only Python's standard library while maintaining all features and backward compatibility. The system is now:

- ✅ Simpler (no external dependencies)
- ✅ More maintainable (standard library)
- ✅ Fully compatible (all existing code works)
- ✅ Feature-complete (all structlog features maintained)
- ✅ Well-tested (comprehensive test suite)

No action required from developers - the refactor is transparent and backward compatible.

