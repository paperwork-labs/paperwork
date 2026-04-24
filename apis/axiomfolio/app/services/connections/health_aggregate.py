"""Aggregate broker connection + OAuth status for the connections health API.

medallion: ops
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.broker_account import BrokerAccount, BrokerType, SyncStatus
from app.models.broker_oauth_connection import BrokerOAuthConnection, OAuthConnectionStatus

# Canonical broker slugs shown in the connections UI (order preserved).
CONNECTION_HEALTH_BROKERS: tuple[str, ...] = (
    "ibkr",
    "schwab",
    "tastytrade",
    "etrade",
    "tradier",
    "coinbase",
)

_BROKER_TYPES_BY_SLUG: dict[str, tuple[BrokerType, ...]] = {
    "ibkr": (BrokerType.IBKR,),
    "schwab": (BrokerType.SCHWAB,),
    "tastytrade": (BrokerType.TASTYTRADE,),
    "etrade": (BrokerType.ETRADE,),
    "tradier": (BrokerType.TRADIER, BrokerType.TRADIER_SANDBOX),
    "coinbase": (BrokerType.COINBASE,),
}

_OAUTH_BROKER_KEYS_BY_SLUG: dict[str, tuple[str, ...]] = {
    "ibkr": ("ibkr",),
    "schwab": ("schwab",),
    "tastytrade": (),
    "etrade": ("etrade_sandbox", "etrade"),
    "tradier": ("tradier", "tradier_sandbox"),
    "coinbase": ("coinbase",),
}

_STALE_OAUTH = frozenset(
    {
        OAuthConnectionStatus.EXPIRED.value,
        OAuthConnectionStatus.REFRESH_FAILED.value,
        OAuthConnectionStatus.REVOKED.value,
        OAuthConnectionStatus.PENDING.value,
    }
)

_ERROR_OAUTH = frozenset({OAuthConnectionStatus.ERROR.value})

_BAD_SYNC = frozenset(
    {
        SyncStatus.FAILED.value,
        SyncStatus.ERROR.value,
    }
)


def _max_dt(*values: datetime | None) -> datetime | None:
    found: list[datetime] = [v for v in values if v is not None]
    if not found:
        return None
    return max(found)


def build_connections_health(db: Session, user_id: int) -> dict[str, Any]:
    """Return a JSON-serializable health payload scoped to ``user_id``."""

    accounts: Sequence[BrokerAccount] = (
        db.query(BrokerAccount).filter(BrokerAccount.user_id == user_id).all()
    )
    oauth_rows: Sequence[BrokerOAuthConnection] = (
        db.query(BrokerOAuthConnection).filter(BrokerOAuthConnection.user_id == user_id).all()
    )

    oauth_by_key: dict[str, list[BrokerOAuthConnection]] = {}
    for row in oauth_rows:
        oauth_by_key.setdefault(row.broker, []).append(row)

    global_last_sync: datetime | None = None
    by_broker: list[dict[str, Any]] = []
    connected_slugs = 0

    for slug in CONNECTION_HEALTH_BROKERS:
        types = _BROKER_TYPES_BY_SLUG[slug]
        slug_accounts = [a for a in accounts if a.broker in types]
        has_accounts = len(slug_accounts) > 0

        oauth_keys = _OAUTH_BROKER_KEYS_BY_SLUG.get(slug, ())
        slug_oauth: list[BrokerOAuthConnection] = []
        for key in oauth_keys:
            slug_oauth.extend(oauth_by_key.get(key, []))

        last_sync = _max_dt(*[a.last_successful_sync for a in slug_accounts])

        err_msg: str | None = None
        for a in slug_accounts:
            if a.sync_error_message:
                err_msg = a.sync_error_message
                break
        if err_msg is None:
            for o in slug_oauth:
                if o.last_error:
                    err_msg = o.last_error
                    break

        status = "disconnected"
        if has_accounts:
            connected_slugs += 1
            oauth_statuses = {o.status for o in slug_oauth}
            sync_values = {a.sync_status.value for a in slug_accounts if a.sync_status}

            if oauth_statuses & _ERROR_OAUTH or sync_values & _BAD_SYNC:
                status = "error"
            elif oauth_statuses & _STALE_OAUTH:
                status = "stale"
            else:
                status = "connected"

        if last_sync is not None:
            global_last_sync = _max_dt(global_last_sync, last_sync)

        by_broker.append(
            {
                "broker": slug,
                "status": status,
                "last_sync_at": last_sync,
                "error_message": err_msg,
            }
        )

    return {
        "connected": connected_slugs,
        "total": len(CONNECTION_HEALTH_BROKERS),
        "last_sync_at": global_last_sync,
        "by_broker": by_broker,
    }
