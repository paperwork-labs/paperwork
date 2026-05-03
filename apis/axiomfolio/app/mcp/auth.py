"""AxiomFolio adapter for the shared :mod:`mcp_server` auth machinery.

Plaintext bearer tokens look like ``mcp_axfolio_<urlsafe-base64>`` and
are validated by the shared :class:`mcp_server.auth.MCPAuthBuilder`:

1. Prefix check (cheap reject for malformed input)
2. SHA-256 hash + constant-time compare against ``mcp_tokens.token_hash``
3. ``revoked_at`` / ``expires_at`` window check
4. Backing user must exist and be active

Plaintext tokens never touch the database. Only the SHA-256 hex digest
is stored, so a leaked DB row cannot be replayed against the API.

This module preserves the pre-extraction public surface so the rest of
the codebase keeps working byte-identical:

* :data:`mcp_bearer` -- the FastAPI ``HTTPBearer`` scheme
* :class:`MCPAuthContext` -- the resolved auth context
* :func:`get_mcp_context` -- the FastAPI dependency
* :func:`authenticate_mcp_token` -- programmatic auth (used by tests)
* :func:`generate_token`, :func:`hash_token`, :func:`_split_credential`,
  :data:`TOKEN_PREFIX`, :data:`TOKEN_RANDOM_BYTES`
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from mcp_server import (
    DEFAULT_TOKEN_RANDOM_BYTES,
    MCPAuthBuilder,
    MCPAuthContext,
    _split_credential as _shared_split_credential,
    generate_token as _shared_generate_token,
    hash_token,
    mcp_bearer,
)

from app.database import get_db
from app.models.entitlement import SubscriptionTier
from app.models.mcp_token import MCPToken
from app.models.user import User
from app.services.billing.entitlement_service import EntitlementService
from app.services.billing.tier_catalog import (
    mcp_daily_call_limit,
    mcp_scopes_for_tier,
)


TOKEN_PREFIX = "mcp_axfolio_"
TOKEN_RANDOM_BYTES = DEFAULT_TOKEN_RANDOM_BYTES


def _consent_filter(token: MCPToken, scopes: set[str]) -> set[str]:
    """Drop ``mcp.read_tax_engine`` unless the token has explicit PII consent."""
    if token.pii_consent_at is None:
        scopes.discard("mcp.read_tax_engine")
    return scopes


_builder = MCPAuthBuilder(
    token_prefix=TOKEN_PREFIX,
    token_model_class=MCPToken,
    get_db=get_db,
    tier_resolver=lambda db, user: EntitlementService.effective_tier(db, user),
    scopes_for_tier_fn=mcp_scopes_for_tier,
    daily_limit_fn=mcp_daily_call_limit,
    consent_scope_filter=_consent_filter,
)


# FastAPI dependency built once at import time; ``Depends(get_mcp_context)``
# resolves the bearer header into an :class:`MCPAuthContext`.
get_mcp_context = _builder.build_dependency()


def authenticate_mcp_token(
    plaintext: str, db: Session, *, now: Optional[datetime] = None
) -> tuple[User, MCPToken]:
    """Resolve a plaintext bearer token to ``(User, MCPToken)``.

    Raises ``HTTPException(401)`` for any failure mode (missing prefix,
    unknown hash, revoked, expired, or inactive user). The opaque
    response is intentional: callers cannot enumerate which tokens
    exist or distinguish "wrong token" from "expired token".
    """
    return _builder.authenticate(plaintext, db, now=now)


def generate_token() -> tuple[str, str]:
    """Mint a new ``(plaintext, hash)`` pair.

    The plaintext is shown to the operator exactly once; the hash is
    what the database persists.
    """
    return _shared_generate_token(TOKEN_PREFIX)


def _split_credential(raw: Optional[str]) -> Optional[str]:
    """Validate the prefix and return the raw plaintext, or ``None``."""
    return _shared_split_credential(raw, prefix=TOKEN_PREFIX)


__all__ = [
    "MCPAuthContext",
    "TOKEN_PREFIX",
    "TOKEN_RANDOM_BYTES",
    "_split_credential",
    "authenticate_mcp_token",
    "generate_token",
    "get_mcp_context",
    "hash_token",
    "mcp_bearer",
]
