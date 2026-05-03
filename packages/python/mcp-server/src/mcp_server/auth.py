"""Bearer-token authentication primitives for the MCP transport.

The shared package provides:

* Token helpers (:func:`hash_token`, :func:`generate_token`,
  :func:`split_credential`) that every backend can reuse without
  duplicating crypto-sensitive code.
* :class:`MCPAuthContext` -- the result type a route layer hands to
  :class:`mcp_server.dispatcher.MCPServer.handle`.
* :class:`MCPAuthBuilder` -- a factory that, given a backend's specific
  token model, tier resolver, and tier-to-scope mapping, returns a
  ready-to-use FastAPI dependency that resolves an
  ``Authorization: Bearer <token>`` header into an
  :class:`MCPAuthContext`.

Tokens look like ``<prefix><urlsafe-base64>`` (e.g.
``mcp_axfolio_…``, ``mcp_filefree_…``). They are validated by:

1. Prefix check (cheap reject for malformed input)
2. SHA-256 hash + constant-time compare against the persisted hash
3. ``revoked_at`` / ``expires_at`` window check (delegated to the
   token row's :meth:`is_active` method, which the backend owns)
4. Backing user must exist and be active

Plaintext tokens never touch the database. Only the SHA-256 hex digest
is stored, so a leaked DB row cannot be replayed against the API.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .bearer import mcp_bearer

logger = logging.getLogger(__name__)


# Default minimum length we'll consider before even hashing. Short
# enough that random base64 with 16 bytes of entropy passes; long
# enough to drop trivially-truncated input. The prefix is added on top.
_MIN_RAW_LENGTH = 16

# Default random body size for newly minted tokens. 32 bytes of
# entropy -> ~43 chars of url-safe base64 -> well above any
# brute-force threat.
DEFAULT_TOKEN_RANDOM_BYTES = 32


# ----------------------------------------------------------------------
# Public dataclass
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MCPAuthContext:
    """Resolved auth context for a single MCP request.

    Fields are typed loosely so the same dataclass works for any
    backend's user / token / tier types. Each backend's wrapper module
    can re-export a typed alias if it wants stronger types at the call
    site.
    """

    user: Any
    token: Any
    tier: Any
    allowed_scopes: frozenset[str]
    daily_limit: int | None


# ----------------------------------------------------------------------
# Token helpers (pure, side-effect-free)
# ----------------------------------------------------------------------


def hash_token(plaintext: str) -> str:
    """Return the canonical SHA-256 hex digest for a plaintext token."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def split_credential(
    raw: str | None,
    *,
    prefix: str,
    min_random_length: int = _MIN_RAW_LENGTH,
) -> str | None:
    """Validate the prefix and minimum length; return the raw plaintext.

    Returns ``None`` for any malformed input so callers can issue a
    uniform 401 without leaking which check failed.
    """
    if not raw or not raw.startswith(prefix):
        return None
    if len(raw) < len(prefix) + min_random_length:
        return None
    return raw


# Back-compat name preserved for consumers that imported the
# leading-underscore symbol from AxiomFolio's pre-extraction module.
_split_credential = split_credential


def generate_token(
    prefix: str, *, random_bytes: int = DEFAULT_TOKEN_RANDOM_BYTES
) -> tuple[str, str]:
    """Mint a new ``(plaintext, hash)`` pair.

    The plaintext is shown to the operator exactly once; the hash is
    what the database persists.
    """
    raw = prefix + secrets.token_urlsafe(random_bytes)
    return raw, hash_token(raw)


# ----------------------------------------------------------------------
# Builder
# ----------------------------------------------------------------------

# Type aliases just for readability at the call site.
TierResolver = Callable[[Session, Any], Any]
ScopesForTierFn = Callable[[Any], "list[str] | tuple[str, ...] | frozenset[str]"]
DailyLimitFn = Callable[[Any], int | None]
ConsentScopeFilter = Callable[[Any, set[str]], set[str]]


class MCPAuthBuilder:
    """Factory that produces a backend-specific FastAPI auth dependency.

    Every backend has its own ``MCPToken`` model, its own ``User`` model,
    and its own way of computing ``tier``. The shared dispatcher only
    needs an :class:`MCPAuthContext` -- so we keep all the
    backend-specific bits as constructor args and return a plain
    callable that FastAPI can ``Depends(...)``.

    Parameters
    ----------
    token_prefix
        e.g. ``"mcp_axfolio_"``, ``"mcp_filefree_"``. Tokens not
        starting with this string are rejected before we ever hit the DB.
    token_model_class
        SQLAlchemy declarative model. Must have ``token_hash``
        (str column), ``user`` (joined relationship), ``user_id`` (FK),
        ``revoked_at`` / ``expires_at``, and an ``is_active(now=...)``
        instance method. ``last_used_at`` is updated opportunistically
        if present.
    get_db
        FastAPI dependency that yields a ``Session`` per request.
    tier_resolver
        ``(db, user) -> tier``. The shape of ``tier`` is opaque -- it
        flows straight into ``scopes_for_tier_fn`` and ``daily_limit_fn``.
    scopes_for_tier_fn
        ``tier -> iterable[str]``. The result is the set of scopes the
        bearer is entitled to today.
    daily_limit_fn
        ``tier -> int | None``. ``None`` means unlimited; the dispatcher
        skips the quota check entirely in that case.
    consent_scope_filter
        Optional ``(token_row, scope_set) -> scope_set`` post-processor.
        Used by AxiomFolio to drop ``mcp.read_tax_engine`` if the user
        hasn't recorded explicit PII consent on the token.
    """

    def __init__(
        self,
        *,
        token_prefix: str,
        token_model_class: type,
        get_db: Callable[..., Any],
        tier_resolver: TierResolver,
        scopes_for_tier_fn: ScopesForTierFn,
        daily_limit_fn: DailyLimitFn,
        consent_scope_filter: ConsentScopeFilter | None = None,
        min_random_length: int = _MIN_RAW_LENGTH,
    ) -> None:
        self._prefix = token_prefix
        self._token_model = token_model_class
        self._get_db = get_db
        self._tier_resolver = tier_resolver
        self._scopes_for_tier = scopes_for_tier_fn
        self._daily_limit = daily_limit_fn
        self._consent_filter = consent_scope_filter
        self._min_random_length = min_random_length

    # ------------------------------------------------------------------
    # Direct authentication (used by tests and CLI tooling)
    # ------------------------------------------------------------------

    def authenticate(
        self,
        plaintext: str,
        db: Session,
        *,
        now: datetime | None = None,
    ) -> tuple[Any, Any]:
        """Resolve a plaintext bearer token to ``(user, token_row)``.

        Raises ``HTTPException(401)`` for any failure mode (missing
        prefix, unknown hash, revoked, expired, or inactive user). The
        opaque response is intentional: callers cannot enumerate which
        tokens exist or distinguish "wrong token" from "expired token".
        """
        valid = split_credential(
            plaintext,
            prefix=self._prefix,
            min_random_length=self._min_random_length,
        )
        if valid is None:
            raise self._unauthorized()

        candidate_hash = hash_token(valid)
        row = (
            db.query(self._token_model)
            .filter(self._token_model.token_hash == candidate_hash)
            .one_or_none()
        )
        if row is None:
            raise self._unauthorized()
        # Defense-in-depth: even though the DB filter already used
        # equality, use constant-time compare on the canonical strings
        # so any future refactor that loads candidates by prefix or
        # partial match still cannot leak timing data.
        if not secrets.compare_digest(row.token_hash, candidate_hash):
            raise self._unauthorized()

        if not row.is_active(now=now):
            reason = "revoked" if row.revoked_at is not None else "expired"
            logger.info(
                "MCP auth rejected: token id=%s user_id=%s reason=%s",
                getattr(row, "id", "?"),
                getattr(row, "user_id", "?"),
                reason,
            )
            raise self._unauthorized()

        user = row.user
        if user is None:
            logger.error(
                "MCP token %s references missing user %s; rejecting",
                getattr(row, "id", "?"),
                getattr(row, "user_id", "?"),
            )
            raise self._unauthorized()
        if not getattr(user, "is_active", True):
            raise self._unauthorized()

        return user, row

    # ------------------------------------------------------------------
    # FastAPI dependency
    # ------------------------------------------------------------------

    def build_dependency(self) -> Callable[..., MCPAuthContext]:
        """Return a FastAPI dependency that yields :class:`MCPAuthContext`.

        Wire it into a route like::

            mcp_auth = builder.build_dependency()

            @router.post("/jsonrpc")
            def mcp_jsonrpc(
                payload: Any = Body(...),
                db: Session = Depends(get_db),
                auth: MCPAuthContext = Depends(mcp_auth),
            ):
                ...
        """
        get_db = self._get_db

        def _dependency(
            credentials: HTTPAuthorizationCredentials | None = Depends(
                mcp_bearer
            ),
            db: Session = Depends(get_db),
        ) -> MCPAuthContext:
            raw = credentials.credentials if credentials else None
            user, token = self.authenticate(raw or "", db)
            tier = self._tier_resolver(db, user)
            allowed_scopes: set[str] = set(self._scopes_for_tier(tier))
            if self._consent_filter is not None:
                allowed_scopes = set(
                    self._consent_filter(token, allowed_scopes)
                )
            daily_limit = self._daily_limit(tier)

            self._touch_last_used_at(db, token)

            return MCPAuthContext(
                user=user,
                token=token,
                tier=tier,
                allowed_scopes=frozenset(allowed_scopes),
                daily_limit=daily_limit,
            )

        return _dependency

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unauthorized() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MCP token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _touch_last_used_at(db: Session, token: Any) -> None:
        """Best-effort ``last_used_at`` write; never fails the request."""
        if not hasattr(token, "last_used_at"):
            return
        try:
            token.last_used_at = datetime.now(UTC)
            db.commit()
        except Exception as e:  # pragma: no cover - opportunistic write
            logger.warning(
                "MCP last_used_at update failed for token id=%s: %s",
                getattr(token, "id", "?"),
                e,
            )
            db.rollback()


__all__ = [
    "DEFAULT_TOKEN_RANDOM_BYTES",
    "ConsentScopeFilter",
    "DailyLimitFn",
    "MCPAuthBuilder",
    "MCPAuthContext",
    "ScopesForTierFn",
    "TierResolver",
    "_split_credential",
    "generate_token",
    "hash_token",
    "split_credential",
]
