"""Shared FastAPI foundation for Paperwork Labs backends."""

from __future__ import annotations

from .errors import (
    APIError,
    BadRequestError,
    ConflictError,
    ExternalServiceError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    RateLimitedError,
    UnauthorizedError,
    register_exception_handlers,
)
from .healthcheck import register_healthcheck
from .middleware import (
    REQUEST_ID_HEADER,
    STATE_ORG_ID,
    STATE_REQUEST_ID,
    STATE_USER_ID,
    LoggingMiddleware,
    RequestIDMiddleware,
    setup_access_json_logging,
)
from .responses import error_response, success_response

__all__ = [
    "REQUEST_ID_HEADER",
    "STATE_ORG_ID",
    "STATE_REQUEST_ID",
    "STATE_USER_ID",
    "APIError",
    "BadRequestError",
    "ConflictError",
    "ExternalServiceError",
    "ForbiddenError",
    "InternalError",
    "LoggingMiddleware",
    "NotFoundError",
    "RateLimitedError",
    "RequestIDMiddleware",
    "UnauthorizedError",
    "error_response",
    "register_exception_handlers",
    "register_healthcheck",
    "setup_access_json_logging",
    "success_response",
]
