"""Silver portfolio/market entry points callable from bronze broker sync.

Bronze may only import ``ops`` (and stdlib). Closing-lot reconciliation,
day P&L refresh, activity MV refresh, and quote/Redis helpers live in
``silver``; this module re-exports or thin-wraps them for ingest paths.

medallion: ops
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.silver.portfolio.closing_lot_matcher import (
    MatchResult,
    reconcile_closing_lots,
)
from app.services.silver.portfolio.day_pnl_service import (
    recompute_day_pnl_for_rows,
    recompute_position_day_pnl,
)

logger = logging.getLogger(__name__)

# Redis: closing-lot reconciliation failure counter (7-day TTL from last event).
RECONCILE_ANOMALY_KEY = "reconcile:anomaly:total"
_RECONCILE_ANOMALY_TTL_S = 60 * 60 * 24 * 7

def refresh_activity_materialized_views(db: Session) -> dict[str, Any]:
    from app.services.silver.portfolio.activity_aggregator import activity_aggregator

    return activity_aggregator.refresh_materialized_views(db)


def record_reconcile_closing_lots_anomaly() -> None:
    try:
        from app.services.silver.market.market_data_service import infra

        r = getattr(infra, "redis_client", None)
        if r is None:
            return
        r.incr(RECONCILE_ANOMALY_KEY)
        r.expire(RECONCILE_ANOMALY_KEY, _RECONCILE_ANOMALY_TTL_S)
    except Exception as e:  # pragma: no cover - best-effort
        logger.warning("reconcile_anomaly: redis increment failed: %s", e)


def get_market_quote_service():
    """Lazy access to the silver market quote singleton (heavy import graph)."""
    from app.services.silver.market.market_data_service import quote

    return quote
