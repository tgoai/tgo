"""Custom exceptions and error handling."""

from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.schemas.base import ErrorDetail, ErrorResponse
from pydantic import ValidationError as PydanticValidationError

logger = get_logger("exceptions")


class TGOAPIException(Exception):
    """Base exception for TGO API."""
    
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(TGOAPIException):
    """Validation error exception."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"field": field, **(details or {})},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class NotFoundError(TGOAPIException):
    """Resource not found exception."""
    
    def __init__(
        self,
        resource: str,
        identifier: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource} not found"
        if identifier:
            message += f" with identifier: {identifier}"
        
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier, **(details or {})},
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(TGOAPIException):
    """Resource conflict exception."""
    
    def __init__(
        self,
        message: str,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="CONFLICT",
            details={"resource": resource, **(details or {})},
            status_code=status.HTTP_409_CONFLICT,
        )


class AuthenticationError(TGOAPIException):
    """Authentication error exception."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            details=details,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class AuthorizationError(TGOAPIException):
    """Authorization error exception."""
    
    def __init__(
        self,
        message: str = "Access denied",
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details={"resource": resource, **(details or {})},
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitError(TGOAPIException):
    """Rate limit exceeded exception."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after, **(details or {})},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ExternalServiceError(TGOAPIException):
    """External service error exception."""
    
    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{service}: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, **(details or {})},
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


async def tgo_api_exception_handler(request: Request, exc: TGOAPIException) -> JSONResponse:
    """Handle TGO API exceptions."""
    request_id = str(uuid4())
    
    logger.error(
        f"TGO API Exception: {exc.code} - {exc.message}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "code": exc.code,
            "details": exc.details,
        }
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions."""
    request_id = str(uuid4())
    
    # Reduce noise for expected 401s, especially on public webhook endpoints
    if exc.status_code == 401:
        if str(request.url.path).startswith("/v1/integrations/wukongim/webhook"):
            log_fn = logger.debug
        else:
            log_fn = logger.info
    else:
        log_fn = logger.warning

    log_fn(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
        }
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="HTTP_ERROR",
            message=str(exc.detail),
            details={"status_code": exc.status_code},
        ),
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )



async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle request validation exceptions uniformly."""
    request_id = str(uuid4())

    if isinstance(exc, RequestValidationError):
        error_list = jsonable_encoder(exc.errors())
    elif isinstance(exc, PydanticValidationError):
        error_list = jsonable_encoder(exc.errors())
    else:
        error_list = jsonable_encoder(
            [{"type": exc.__class__.__name__, "msg": str(exc)}]
        )

    logger.warning(
        "Validation Exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "errors": error_list,
        }
    )

    error_response = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": error_list},
        ),
        request_id=request_id,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(error_response.model_dump()),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    request_id = str(uuid4())
    
    logger.error(
        f"Unhandled Exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True,
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An internal error occurred",
            details={"type": type(exc).__name__, "message": str(exc)},
        ),
        request_id=request_id,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
