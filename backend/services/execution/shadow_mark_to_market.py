"""Mark-to-market refresh for shadow (paper) orders.

Runs as a Celery beat job every 15 minutes. Walks every ``ShadowOrder`` in
status ``executed_at_simulation_time`` or ``marked_to_market`` and updates
``simulated_pnl`` using the latest ``MarketSnapshot.current_price`` for the
symbol. No broker calls — uses only data already in the DB.

Follows the operator-observability pattern from ``.cursor/rules/no-silent-fallback.mdc``:
per-iteration counters (``updated`` / ``skipped_no_price`` / ``errors``) are
returned and asserted to sum to the total rows considered, so counter drift
trips loudly in CI and the admin panel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Set

from celery import shared_task
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.market_data import MarketSnapshot
from backend.models.shadow_order import ShadowOrder, ShadowOrderStatus
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


# Statuses that MtM should refresh. "CLOSED" shadows are ignored; so are
# orders the risk gate would have denied (they never simulated a fill).
_OPEN_MTM_STATUSES: tuple[str, ...] = (
    ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME.value,
    ShadowOrderStatus.MARKED_TO_MARKET.value,
)


def _latest_snapshot_prices(
    session: Session, symbols: Set[str]
) -> Dict[str, Decimal]:
    """Latest ``MarketSnapshot.current_price`` per symbol (one query batch).

    Keys are uppercased symbols. Omits symbols with no row, NULL price, or
    unparseable price so callers count ``skipped_no_price`` per row.
    """
    sym_list = sorted({(s or "").upper() for s in symbols if (s or "").strip()})
    if not sym_list:
        return {}

    subq = (
        session.query(
            MarketSnapshot.symbol,
            func.max(MarketSnapshot.analysis_timestamp).label("max_ts"),
        )
        .filter(
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.symbol.in_(sym_list),
        )
        .group_by(MarketSnapshot.symbol)
    ).subquery()

    rows = (
        session.query(MarketSnapshot.symbol, MarketSnapshot.current_price)
        .join(
            subq,
            and_(
                MarketSnapshot.symbol == subq.c.symbol,
                MarketSnapshot.analysis_timestamp == subq.c.max_ts,
                MarketSnapshot.analysis_type == "technical_snapshot",
            ),
        )
        .all()
    )

    out: Dict[str, Decimal] = {}
    for sym, raw_price in rows:
        key = (sym or "").upper()
        if raw_price is None:
            continue
        try:
            out[key] = Decimal(str(raw_price))
        except (InvalidOperation, TypeError, ValueError):
            logger.warning(
                "shadow_mtm: snapshot price for %s could not be parsed (%r)",
                sym,
                raw_price,
            )
    return out


def _compute_simulated_pnl(
    *,
    side: str,
    qty: Decimal,
    fill_price: Decimal,
    mark_price: Decimal,
) -> Decimal:
    """Per-share price delta × qty, sign-adjusted by side.

    Longs profit when mark rises above fill; shorts profit when mark falls
    below fill. Result keeps full ``Decimal`` precision.
    """
    if (side or "").lower() == "buy":
        return (mark_price - fill_price) * qty
    return (fill_price - mark_price) * qty


def mark_open_shadow_orders(session: Session) -> Dict[str, Any]:
    """Update ``simulated_pnl`` for every open shadow order.

    Pure Python (no Celery dependency) so tests can exercise the exact same
    code path with an injected ``Session`` and a frozen ``MarketSnapshot``
    fixture.
    """
    rows = (
        session.query(ShadowOrder)
        .filter(ShadowOrder.status.in_(_OPEN_MTM_STATUSES))
        .all()
    )
    total = len(rows)
    price_by_symbol = _latest_snapshot_prices(
        session, {(r.symbol or "") for r in rows}
    )
    updated = 0
    skipped_no_price = 0
    skipped_no_fill = 0
    errors = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        try:
            if row.intended_fill_price is None or row.qty is None:
                skipped_no_fill += 1
                logger.info(
                    "shadow_mtm: row id=%s missing intended_fill_price/qty; skipping",
                    row.id,
                )
                continue

            mark = price_by_symbol.get((row.symbol or "").upper())
            if mark is None:
                skipped_no_price += 1
                continue

            fill = Decimal(str(row.intended_fill_price))
            qty = Decimal(str(row.qty))
            pnl = _compute_simulated_pnl(
                side=row.side,
                qty=qty,
                fill_price=fill,
                mark_price=mark,
            )

            row.simulated_pnl = pnl
            row.simulated_pnl_as_of = now
            row.last_mark_price = mark
            row.status = ShadowOrderStatus.MARKED_TO_MARKET.value
            updated += 1
        except Exception as e:  # noqa: BLE001 — count + log, never swallow silently
            errors += 1
            logger.warning(
                "shadow_mtm: row id=%s failed to mark-to-market: %s", row.id, e
            )

    if updated or skipped_no_price or skipped_no_fill or errors:
        session.commit()

    assert (
        updated + skipped_no_price + skipped_no_fill + errors == total
    ), "shadow_mtm counter drift: counters do not sum to total rows"

    logger.info(
        "shadow_mtm: total=%d updated=%d skipped_no_price=%d skipped_no_fill=%d errors=%d",
        total,
        updated,
        skipped_no_price,
        skipped_no_fill,
        errors,
    )

    return {
        "status": "ok",
        "total": total,
        "updated": updated,
        "skipped_no_price": skipped_no_price,
        "skipped_no_fill": skipped_no_fill,
        "errors": errors,
    }


@shared_task(
    name="backend.services.execution.shadow_mark_to_market.run",
    soft_time_limit=290,
    time_limit=300,
)
@task_run(
    "shadow_mtm_refresh",
    lock_key=lambda **k: "singleton",
    lock_ttl_seconds=600,
)
def run() -> Dict[str, Any]:
    """Celery entry point. Refreshes MtM P&L for every open shadow order."""
    session = SessionLocal()
    try:
        return mark_open_shadow_orders(session)
    finally:
        session.close()
