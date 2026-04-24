"""Bearer-token authentication for the MCP transport endpoint.

Tokens look like ``mcp_axfolio_<urlsafe-base64>`` and are validated by:

1. Prefix check (cheap reject for malformed input)
2. SHA-256 hash + constant-time compare against ``mcp_tokens.token_hash``
3. ``revoked_at`` / ``expires_at`` window check
4. Backing user must exist and be active

Plaintext tokens never touch the database. Only the SHA-256 hex digest
is stored, so a leaked DB row cannot be replayed against the API.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entitlement import SubscriptionTier
from app.models.mcp_token import MCPToken
from app.models.user import User
from app.services.billing.entitlement_service import EntitlementService
from app.services.billing.tier_catalog import mcp_daily_call_limit, mcp_scopes_for_tier

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "mcp_axfolio_"
TOKEN_RANDOM_BYTES = 32

mcp_bearer = HTTPBearer(auto_error=False, scheme_name="MCPBearer")


@dataclass(frozen=True)
class MCPAuthContext:
    """Resolved auth context for a single MCP request."""

    user: User
    token: MCPToken
    tier: SubscriptionTier
    allowed_scopes: frozenset[str]
    daily_limit: Optional[int]


def hash_token(plaintext: str) -> str:
    """Return the canonical SHA-256 hex digest for a plaintext token."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _split_credential(raw: Optional[str]) -> Optional[str]:
    """Validate the prefix and return the raw plaintext, or None."""
    if not raw or not raw.startswith(TOKEN_PREFIX):
        return None
    if len(raw) < len(TOKEN_PREFIX) + 16:
        return None
    return raw


def authenticate_mcp_token(
    plaintext: str, db: Session, *, now: Optional[datetime] = None
) -> Tuple[User, MCPToken]:
    """Resolve a plaintext bearer token to ``(User, MCPToken)``.

    Raises ``HTTPException(401)`` for any failure mode (missing prefix,
    unknown hash, revoked, expired, or inactive user). The opaque
    response is intentional: callers cannot enumerate which tokens exist
    or distinguish "wrong token" from "expired token".
    """
    valid = _split_credential(plaintext)
    if valid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    candidate_hash = hash_token(valid)
    row = (
        db.query(MCPToken)
        .filter(MCPToken.token_hash == candidate_hash)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Defense-in-depth: even though the DB filter already used equality,
    # use constant-time compare on the canonical strings so any future
    # refactor that loads candidates by prefix or partial match still
    # cannot leak timing data.
    if not secrets.compare_digest(row.token_hash, candidate_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not row.is_active(now=now):
        reason = "revoked" if row.revoked_at is not None else "expired"
        logger.info(
            "MCP auth rejected: token id=%s user_id=%s reason=%s",
            row.id,
            row.user_id,
            reason,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = row.user
    if user is None:
        logger.error(
            "MCP token %s references missing user %s; rejecting",
            row.id,
            row.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user, row


def get_mcp_context(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(mcp_bearer),
    db: Session = Depends(get_db),
) -> MCPAuthContext:
    """FastAPI dependency: resolve the bearer header into an MCP context."""
    raw = credentials.credentials if credentials else None
    user, token = authenticate_mcp_token(raw or "", db)
    tier = EntitlementService.effective_tier(db, user)
    allowed_scopes = set(mcp_scopes_for_tier(tier))
    if token.pii_consent_at is None:
        allowed_scopes.discard("mcp.read_tax_engine")
    daily_limit = mcp_daily_call_limit(tier)

    # Best-effort last_used_at update. Never fail the request on a
    # commit error here — observability is nice-to-have, auth already
    # passed.
    try:
        token.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:  # pragma: no cover - opportunistic write
        logger.warning(
            "MCP last_used_at update failed for token id=%s: %s", token.id, e
        )
        db.rollback()

    return MCPAuthContext(
        user=user,
        token=token,
        tier=tier,
        allowed_scopes=frozenset(allowed_scopes),
        daily_limit=daily_limit,
    )


def generate_token() -> Tuple[str, str]:
    """Mint a new ``(plaintext, hash)`` pair.

    The plaintext is shown to the operator exactly once; the hash is
    what the database persists.
    """
    raw = TOKEN_PREFIX + secrets.token_urlsafe(TOKEN_RANDOM_BYTES)
    return raw, hash_token(raw)
