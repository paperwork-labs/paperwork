"""Regime attribution for walk-forward trades.

A strategy that wins overall but loses in R3 (chop) is operationally
different from one that wins in every regime — the Quant Analyst rules
explicitly call this out. The optimizer therefore tags each test-window
trade with the prevailing market regime on its entry date and reports
per-regime objective values.

Lookups go through ``MarketRegime`` (immutable, indexed by ``as_of_date``)
to honor the point-in-time-data rule. If the regime table has no row for
an entry date, the trade is tagged as ``"unknown"`` rather than silently
dropped.

medallion: gold
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.services.backtest.walk_forward import TradeResult

logger = logging.getLogger(__name__)

REGIME_LABELS = ("R1", "R2", "R3", "R4", "R5")

RegimeLookup = Callable[[date], str | None]


def db_regime_lookup(db: Session) -> RegimeLookup:
    """Build a regime lookup backed by ``MarketRegime``.

    The lookup is memoized in-process for the lifetime of the optimizer
    run; a typical study touches ~250 distinct dates so the cache stays
    small. We import lazily so this module can be unit-tested without
    standing up the full SQLAlchemy stack.
    """
    from app.models.market_data import MarketRegime

    cache: dict[date, str | None] = {}

    def lookup(d: date) -> str | None:
        if d in cache:
            return cache[d]
        try:
            row = (
                db.query(MarketRegime)
                .filter(MarketRegime.as_of_date <= d)
                .order_by(MarketRegime.as_of_date.desc())
                .first()
            )
            label = row.regime_state if row else None
        except Exception as e:
            # Per the no-silent-fallback rule: log + return None so the
            # caller can attribute these to "unknown" rather than mis-
            # classify them as a real regime.
            logger.warning("regime lookup failed for %s: %s", d, e)
            label = None
        cache[d] = label
        return label

    return lookup


def attribute_trades_by_regime(
    trades: Sequence[TradeResult],
    objective: Callable[[Sequence[TradeResult]], Decimal],
) -> dict[str, dict[str, float]]:
    """Group trades by regime and apply ``objective`` to each bucket.

    Returns a dict shaped ``{regime: {"score": float, "trades": int,
    "avg_return": float}}``. Float is used for the wire format because the
    payload lands in JSON and the frontend renders to fixed precision; the
    canonical Decimal copy lives in ``best_score``.
    """
    buckets: dict[str, list[TradeResult]] = defaultdict(list)
    for t in trades:
        label = t.regime if t.regime else "unknown"
        buckets[label].append(t)

    out: dict[str, dict[str, float]] = {}
    for label, items in buckets.items():
        score = objective(items)
        rets = [t.return_pct for t in items]
        avg_ret = float(sum(rets, Decimal("0")) / Decimal(len(rets))) if rets else 0.0
        out[label] = {
            "score": float(score),
            "trades": len(items),
            "avg_return": avg_ret,
        }
    # Make the response stable: always emit the canonical R1-R5 keys + unknown
    # so the frontend radial chart has a deterministic axis order, even when
    # a bucket is empty.
    for label in REGIME_LABELS + ("unknown",):
        out.setdefault(label, {"score": 0.0, "trades": 0, "avg_return": 0.0})
    return out


def filter_trades_by_regime(trades: Sequence[TradeResult], regime: str) -> list[TradeResult]:
    """Return only trades whose regime tag matches ``regime``.

    ``regime`` must be one of ``R1``-``R5`` or ``"unknown"``. Trades with
    a missing tag are *never* matched against R1-R5 to keep the regime
    semantics honest.
    """
    if regime not in REGIME_LABELS and regime != "unknown":
        raise ValueError(
            f"Invalid regime '{regime}'. Expected one of {REGIME_LABELS} or 'unknown'."
        )
    return [t for t in trades if (t.regime or "unknown") == regime]
