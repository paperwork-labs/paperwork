"""FastAPI dependencies for Brain caller identity (WS-76 PR-13).

Resolves :class:`~app.schemas.brain_user_context.BrainUserContext` from either an
optional Clerk JWT Bearer token or env-based tooling fallback.

medallion: ops
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from jose.exceptions import JWTError

from app.config import Settings, settings
from app.schemas.brain_user_context import BrainUserContext
from app.services.clerk_jwt import ClerkJwtConfigurationError, clerk_jwt_claims
from app.services.paperwork_links import resolve_by_clerk_user_id_optional

logger = logging.getLogger(__name__)


def extract_bearer_token(request: Request) -> str | None:
    """Return raw Bearer token from ``Authorization`` or ``None``."""
    auth = request.headers.get("authorization") or ""
    parts = auth.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer":
        return None
    tok = token.strip()
    return tok or None


def looks_like_jwt(token: str) -> bool:
    """Heuristic: Clerk session tokens are three dot-separated segments."""
    return token.count(".") == 2


def resolve_brain_user_context(*, bearer_token: str | None, cfg: Settings) -> BrainUserContext:
    """Core resolver used by tests and :func:`get_brain_user_context`.

    When *bearer_token* looks like a JWT, decode claims and map ``sub`` via the
    paperwork link ledger. Otherwise return env fallback (``BRAIN_TOOLS_USER_ID``).
    """
    if bearer_token and looks_like_jwt(bearer_token):
        try:
            claims = clerk_jwt_claims(bearer_token, cfg)
        except ClerkJwtConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except JWTError as exc:
            raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {exc}") from exc

        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub.strip():
            raise HTTPException(status_code=401, detail="Invalid Clerk token: missing sub")

        link = resolve_by_clerk_user_id_optional(sub)
        if link is None:
            logger.info("paperwork_links: no ledger row for clerk_user_id=%s", sub)
            raise HTTPException(
                status_code=403,
                detail="Paperwork link not found for Clerk user",
            )

        return BrainUserContext(
            auth_source="clerk_jwt",
            paperwork_link_id=link.id,
            clerk_user_id=link.clerk_user_id,
            organization_id=link.organization_id,
            display_name=link.display_name,
            role=link.role,
            brain_user_id=link.id,
        )

    return BrainUserContext(
        auth_source="env_fallback",
        paperwork_link_id=None,
        clerk_user_id=None,
        organization_id=cfg.BRAIN_TOOLS_ORGANIZATION_ID.strip() or None,
        display_name=None,
        role="member",
        brain_user_id=str(cfg.BRAIN_TOOLS_USER_ID),
    )


def get_brain_user_context(request: Request) -> BrainUserContext:
    """FastAPI dependency — resolves tenancy + Brain user key for the request."""
    tok = extract_bearer_token(request)
    return resolve_brain_user_context(bearer_token=tok, cfg=settings)


get_current_user = get_brain_user_context
