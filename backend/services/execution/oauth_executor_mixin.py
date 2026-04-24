"""OAuth executor helpers — per-connection token-refresh lock.

Used by the OAuth-backed broker executors (Tradier, E*TRADE, Schwab,
TastyTrade, Coinbase) to guarantee that concurrent order operations for
the same ``BrokerOAuthConnection`` cannot race the token-refresh path.

The existing ``backend.tasks.portfolio.oauth_token_refresh._refresh_one``
already owns the refresh mechanics (decrypt, call adapter.refresh, rotate
ciphertext, bump ``rotation_count``). This mixin is a thin, synchronous-over-
Redis lock that:

* Skips refresh if the token is still valid for more than ``skew`` seconds
  (avoids a token-rotation thundering herd during burst trading).
* Serializes refresh attempts per-connection via a Redis ``SET NX EX`` lock
  on ``lock:oauth_refresh:<connection_id>``.
* Always releases the lock in ``finally``.

Callers should hold the ``db`` Session for the duration of the broker
operation so the refreshed token in ``conn.access_token_encrypted`` is what
they see when they subsequently ``decrypt()`` it.

This is *not* a coroutine-safe primitive on its own — we lean on Redis for
cross-worker mutual exclusion. Within a single process it is the caller's
responsibility not to race two refresh calls on the same ``conn`` object.

medallion: execution
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.broker_oauth_connection import (
    BrokerOAuthConnection,
    OAuthConnectionStatus,
)

# ``infra.redis_client`` and ``_refresh_one`` are imported lazily inside
# :func:`ensure_broker_token` so this module stays cheap to import from
# broker executors that don't (yet) need the market/celery import chain.

logger = logging.getLogger(__name__)


DEFAULT_SKEW_SECONDS = 60
DEFAULT_LOCK_TTL_SECONDS = 30


class TokenRefreshError(RuntimeError):
    """Raised when a connection cannot be brought to a refreshed/usable state."""


def _lock_key(connection_id: int) -> str:
    return f"lock:oauth_refresh:{connection_id}"


def _needs_refresh(conn: BrokerOAuthConnection, skew_seconds: int) -> bool:
    """Return True if ``conn`` must refresh before use."""
    if conn.status == OAuthConnectionStatus.EXPIRED.value:
        return True
    if conn.status != OAuthConnectionStatus.ACTIVE.value:
        # PENDING / REVOKED / REFRESH_FAILED / ERROR — caller should not be using this
        return False
    if conn.token_expires_at is None:
        return False
    expires_at = conn.token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc) + timedelta(seconds=skew_seconds)


def ensure_broker_token(
    db: Session,
    conn: BrokerOAuthConnection,
    *,
    skew_seconds: int = DEFAULT_SKEW_SECONDS,
    lock_ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
) -> BrokerOAuthConnection:
    """Ensure ``conn`` has a valid access token; refresh under a Redis lock if not.

    Parameters
    ----------
    db:
        Active SQLAlchemy session. Caller owns commit/rollback scope.
    conn:
        The connection row to refresh. Must already be loaded from ``db``.
    skew_seconds:
        Refresh if the token expires within this many seconds.
    lock_ttl_seconds:
        Redis lock TTL. Must cover the worst-case adapter.refresh() latency.
        30s is generous for HTTPS token refresh against every supported broker.

    Returns
    -------
    The (possibly-refreshed) connection. Caller should re-read
    ``access_token_encrypted`` / ``token_expires_at`` from ``conn`` after
    this returns.

    Raises
    ------
    TokenRefreshError
        If the connection is in a non-ACTIVE terminal state (REVOKED,
        REFRESH_FAILED) or if the refresh attempt failed permanently.
    """
    if conn.status == OAuthConnectionStatus.REVOKED.value:
        raise TokenRefreshError(
            f"connection {conn.id} is REVOKED; user must re-authorize"
        )
    if conn.status == OAuthConnectionStatus.REFRESH_FAILED.value:
        raise TokenRefreshError(
            f"connection {conn.id} is REFRESH_FAILED; user must re-authorize"
        )

    if not _needs_refresh(conn, skew_seconds):
        return conn

    # Lazy imports: see module docstring.
    from backend.services.market.market_data_service import infra
    from backend.tasks.portfolio.oauth_token_refresh import _refresh_one

    r = infra.redis_client
    key = _lock_key(conn.id)
    acquired: Optional[bool] = False
    try:
        acquired = r.set(name=key, value="1", nx=True, ex=lock_ttl_seconds)
    except Exception as exc:  # pragma: no cover — Redis down is fail-open on the lock
        logger.warning(
            "ensure_broker_token redis lock set failed connection=%s err=%s",
            conn.id, exc,
        )
        acquired = False

    if not acquired:
        logger.info(
            "ensure_broker_token: another worker is refreshing connection=%s; waiting via caller",
            conn.id,
        )
        # We do not spin here. The caller should re-query `conn` after a brief
        # pause if it wants to observe the refreshed token; for order-placement
        # paths we surface this as a retriable error so OrderManager can back off.
        raise TokenRefreshError(
            f"connection {conn.id} is being refreshed by another worker; retry"
        )

    try:
        outcome = _refresh_one(db, conn)
        db.commit()
        if outcome == "errors":
            raise TokenRefreshError(
                f"connection {conn.id} refresh failed: {conn.last_error}"
            )
        if outcome == "skipped":
            # _refresh_one skipped because status moved underneath us. Treat as a
            # retriable error rather than silent success — the caller must not
            # proceed to call the broker with a possibly-stale token.
            raise TokenRefreshError(
                f"connection {conn.id} refresh skipped (status={conn.status}); retry"
            )
        return conn
    finally:
        try:
            r.delete(key)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ensure_broker_token redis lock release failed connection=%s err=%s",
                conn.id, exc,
            )


__all__ = [
    "TokenRefreshError",
    "ensure_broker_token",
    "DEFAULT_SKEW_SECONDS",
    "DEFAULT_LOCK_TTL_SECONDS",
]
