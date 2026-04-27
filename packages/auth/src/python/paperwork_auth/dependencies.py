"""FastAPI dependency for Clerk-authenticated endpoints.

Tracks B1 (FileFree API) and B2 (Brain API) will consume ``require_clerk_user``
to drop their custom ad-hoc verifiers. Keep the module FastAPI-optional so the
sidecar can also be imported by Celery / APScheduler tasks that don't depend
on FastAPI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .jwks import ClerkAuthError, ClerkJwtConfig, verify_clerk_jwt


@dataclass(frozen=True)
class ClerkUser:
    """Decoded Clerk session JWT, surfaced to FastAPI handlers.

    ``raw_claims`` contains all claims for callers that need org_role,
    custom JWT-template fields, etc.
    """

    user_id: str
    session_id: Optional[str]
    org_id: Optional[str]
    org_role: Optional[str]
    raw_claims: Mapping[str, Any]


def _build_default_config() -> ClerkJwtConfig:
    issuer = os.environ.get("CLERK_JWT_ISSUER")
    if not issuer:
        raise ClerkAuthError(
            "CLERK_JWT_ISSUER is required to verify Clerk tokens. "
            "Set it to the Clerk Frontend API URL, e.g. https://clerk.filefree.ai",
        )
    audience = os.environ.get("CLERK_JWT_AUDIENCE") or None
    return ClerkJwtConfig(issuer=issuer, audience=audience)


def require_clerk_user(
    config: Optional[ClerkJwtConfig] = None,
) -> Callable[..., "ClerkUser"]:
    """Construct a FastAPI dependency that yields a verified ``ClerkUser``.

    Usage::

        from fastapi import Depends, FastAPI
        from paperwork_auth import require_clerk_user, ClerkUser

        app = FastAPI()

        @app.get("/me")
        async def me(user: ClerkUser = Depends(require_clerk_user())) -> dict:
            return {"user_id": user.user_id}

    The dependency expects either an ``Authorization: Bearer <token>`` header
    or a ``__session`` cookie (Clerk's default). It raises ``HTTPException(401)``
    on any verification failure.
    """
    try:
        from fastapi import HTTPException, Request
    except ModuleNotFoundError as exc:
        raise ClerkAuthError(
            "fastapi is required: pip install fastapi",
        ) from exc

    resolved_config = config

    def _resolve_config() -> ClerkJwtConfig:
        nonlocal resolved_config
        if resolved_config is None:
            resolved_config = _build_default_config()
        return resolved_config

    def _dependency(request: Request) -> ClerkUser:
        token = _extract_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="missing clerk token")

        try:
            claims = verify_clerk_jwt(token, _resolve_config())
        except ClerkAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise HTTPException(status_code=401, detail="token missing sub")

        return ClerkUser(
            user_id=sub,
            session_id=_str_or_none(claims.get("sid")),
            org_id=_str_or_none(claims.get("org_id")),
            org_role=_str_or_none(claims.get("org_role")),
            raw_claims=claims,
        )

    return _dependency


def _extract_token(request: Any) -> Optional[str]:
    auth_header = request.headers.get("authorization") if hasattr(request, "headers") else None
    if auth_header:
        parts = auth_header.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
            return parts[1].strip()
    cookies = getattr(request, "cookies", None) or {}
    session = cookies.get("__session")
    if session:
        return session
    return None


def _str_or_none(value: Any) -> Optional[str]:
    if isinstance(value, str) and value:
        return value
    return None
