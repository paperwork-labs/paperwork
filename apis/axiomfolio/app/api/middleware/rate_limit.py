"""Per-tenant rate-limit middleware.

Resolves the calling user (best-effort, no exception if unauth) and
calls :class:`TenantRateLimiter`. Returns 429 with ``Retry-After`` on
limit, 503 on infra failure. Bypasses the limiter for an allowlist of
critical paths so health checks, auth, and webhooks can never be
locked out.
"""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Iterable

from fastapi import Request
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.api.security import decode_token
from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.services.multitenant.rate_limiter import (
    RateLimitDecision,
    TenantRateLimiter,
)
from app.services.multitenant.rate_limiter import (
    rate_limiter as default_rate_limiter,
)

logger = logging.getLogger(__name__)


# Paths that MUST always pass through the limiter — anything that, if
# locked out, would prevent diagnosis or recovery (health, auth, webhooks).
_DEFAULT_ALLOWLIST: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p)
    for p in (
        r"^/$",
        r"^/health",
        r"^/api/v1/health",
        r"^/api/v1/auth/",
        r"^/api/v1/stripe/webhook",
        r"^/api/v1/picks/webhook",
        r"^/docs",
        r"^/openapi.json",
        r"^/redoc",
    )
)


def _normalise_endpoint(path: str) -> str:
    """Collapse numeric ids to ``:id`` so /me/items/123 buckets with
    /me/items/456. Keeps the pattern small and stable.
    """
    return re.sub(r"/\d+", "/:id", path)


def _resolve_user_id(request: Request, db: Session) -> int | None:
    """Best-effort user resolution. Returns ``None`` for anonymous calls.

    Order:
      1. Bearer JWT (preferred — same path as get_current_user)
      2. ``X-Brain-Api-Key`` + ``X-Axiom-User-Id`` header (M2M scoped)
      3. ``X-Brain-Api-Key`` alone -> fallback to ``BRAIN_TOOLS_USER_ID``
         (with a deprecation warning).
    """
    # 1. JWT
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except Exception:
            payload = None
        if payload:
            username = payload.get("sub")
            if username:
                user = db.query(User.id).filter(User.username == username).first()
                if user:
                    return int(user[0])

    # 2 & 3. Brain M2M
    brain_key = request.headers.get("x-brain-api-key") or request.headers.get("X-Brain-Api-Key")
    if brain_key and settings.BRAIN_API_KEY:
        provided = brain_key.encode("utf-8")
        expected = settings.BRAIN_API_KEY.encode("utf-8")
        if len(provided) == len(expected) and secrets.compare_digest(provided, expected):
            override = request.headers.get("x-axiom-user-id") or request.headers.get(
                "X-Axiom-User-Id"
            )
            if override:
                try:
                    return int(override)
                except ValueError:
                    logger.warning(
                        "rate_limit: invalid X-Axiom-User-Id header value=%r",
                        override,
                    )
            # Last-resort fallback. We log every use so we can drive
            # the deprecation campaign.
            logger.warning(
                "rate_limit: Brain M2M call without X-Axiom-User-Id; "
                "falling back to BRAIN_TOOLS_USER_ID=%s path=%s",
                settings.BRAIN_TOOLS_USER_ID,
                request.url.path,
            )
            return int(settings.BRAIN_TOOLS_USER_ID)

    return None


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        limiter: TenantRateLimiter | None = None,
        allowlist: Iterable[re.Pattern[str]] | None = None,
    ) -> None:
        super().__init__(app)
        self._limiter = limiter or default_rate_limiter
        self._allowlist = tuple(allowlist) if allowlist else _DEFAULT_ALLOWLIST

    def _is_allowlisted(self, path: str) -> bool:
        return any(p.match(path) for p in self._allowlist)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not settings.TENANT_RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if self._is_allowlisted(path):
            return await call_next(request)

        endpoint = _normalise_endpoint(path)

        # Use a short-lived session for resolution + bucket lookup.
        db = SessionLocal()
        try:
            user_id = _resolve_user_id(request, db)
            result = self._limiter.check(db, user_id, endpoint)
        finally:
            db.close()

        headers = {
            "X-RateLimit-Limit": str(result.bucket_per_minute),
            "X-RateLimit-Remaining": str(max(result.tokens_remaining, 0)),
            "X-RateLimit-Bucket": endpoint,
        }

        if result.decision == RateLimitDecision.ALLOWED:
            response = await call_next(request)
            for k, v in headers.items():
                response.headers.setdefault(k, v)
            return response

        if result.decision == RateLimitDecision.FAILED_CLOSED:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Rate limiter unavailable; request rejected for safety.",
                    "code": "rate_limit_unavailable",
                },
                headers={**headers, "Retry-After": "1"},
            )

        retry_secs = max(1, int((result.retry_after_ms + 999) / 1000))
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded for this tenant on this endpoint.",
                "code": "rate_limit_exceeded",
                "retry_after_seconds": retry_secs,
            },
            headers={**headers, "Retry-After": str(retry_secs)},
        )
