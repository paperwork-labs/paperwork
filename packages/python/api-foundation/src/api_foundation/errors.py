"""Typed HTTP exceptions and FastAPI handlers with safe wire surfaces."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

_logger = logging.getLogger(__name__)

_GENERIC_INTERNAL_MESSAGE = "An unexpected error occurred"


class APIError(Exception):
    """Base error for deliberate API failures surfaced to clients."""

    status_code = 500
    error_code = "INTERNAL"

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class BadRequestError(APIError):
    status_code = 400
    error_code = "BAD_REQUEST"


class UnauthorizedError(APIError):
    status_code = 401
    error_code = "UNAUTHORIZED"


class ForbiddenError(APIError):
    status_code = 403
    error_code = "FORBIDDEN"


class NotFoundError(APIError):
    status_code = 404
    error_code = "NOT_FOUND"


class ConflictError(APIError):
    status_code = 409
    error_code = "CONFLICT"


class RateLimitedError(APIError):
    status_code = 429
    error_code = "RATE_LIMITED"


class InternalError(APIError):
    status_code = 500
    error_code = "INTERNAL"


class ExternalServiceError(APIError):
    status_code = 503
    error_code = "EXTERNAL_SERVICE"


def _error_envelope(
    *,
    code: str,
    message: str,
    request_id: str | None,
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    """Wire :class:`APIError` and a final catch-all with no internal leakage."""

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        _logger.warning(
            "api_error_response",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "detail": exc.detail,
                "request_path": request.url.path,
                "request_id": _request_id(request),
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(
                code=str(exc.error_code),
                message=exc.detail,
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_any_exception(request: Request, exc: Exception) -> JSONResponse:
        _logger.error(
            "unhandled_exception; returning opaque 500 envelope "
            "(request_path=%s request_id=%s exc_type=%s)",
            request.url.path,
            _request_id(request),
            type(exc).__name__,
            exc_info=exc,
        )

        return JSONResponse(
            status_code=500,
            content=_error_envelope(
                code="INTERNAL",
                message=_GENERIC_INTERNAL_MESSAGE,
                request_id=_request_id(request),
            ),
        )
