"""Day P&L computation — single source of truth.

Architectural principle: broker-reported ``currentDayProfitLoss`` /
``daysGain`` fields are unreliable across corporate actions, session
boundaries, and provider sync gaps. We recompute day P&L server-side
from the same ``(current, prior_close)`` pair we already trust for
other indicators. When the prior_close is missing or split-ambiguous,
we return ``None`` and the UI renders ``'—'`` rather than a lie
(no-silent-fallback rule — see ``.cursor/rules/no-silent-fallback.mdc``).

RIVN regression (founder screenshot, Wave A2): Day P&L displayed
-$55,691 (-47.82%) on a 3,500-share position with only +$3,284 total
unrealized P&L. ``-$55,691 / 3,500 ≈ -$15.91 per share`` implies a
reference price near $32.9 vs the current $17.15 — a pre-split
baseline that the broker never refreshed and that we previously
blindly persisted.

Contract (D141):

* Day P&L is ALWAYS server-recomputed from
  ``(current_price, prior_close, quantity)``.
* Broker ``currentDayProfitLoss`` / ``daysGain`` are advisory only
  (logged at debug level for drift measurement; NOT persisted).
* On missing prior_close or ambiguous corporate-action window,
  ``day_pnl`` and ``day_pnl_pct`` are set to ``NULL`` — zero is a
  valid market outcome, null is "unknown".

medallion: silver
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.corporate_action import CorporateAction, CorporateActionType
from app.models.market_data import MarketSnapshot, PriceData

if TYPE_CHECKING:  # avoid circular import at runtime
    from app.models.position import Position


logger = logging.getLogger(__name__)


# Corporate-action types whose ex-date between the prior-close date and
# today invalidates a naive (current - prior_close) day P&L. A forward
# split, reverse split, or stock-dividend all silently change the price
# scale; a cash dividend does NOT (share count is unchanged).
_SPLIT_LIKE_TYPES: Tuple[str, ...] = (
    CorporateActionType.SPLIT.value,
    CorporateActionType.REVERSE_SPLIT.value,
    CorporateActionType.STOCK_DIVIDEND.value,
)


def _to_decimal(value: object) -> Optional[Decimal]:
    """Coerce a DB scalar (float / Decimal / str) to Decimal, or None.

    We explicitly do NOT default to ``Decimal(0)`` on failure: an
    unparseable price is an unknown price, not a zero price.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d.is_finite() else None


def resolve_prior_close(
    db: Session,
    symbol: str,
    *,
    as_of: Optional[date] = None,
) -> Optional[Tuple[Decimal, date]]:
    """Return ``(prior_close, prior_close_date)`` or ``None`` if unavailable.

    Source of truth: daily ``price_data`` (interval='1d') — the same
    OHLCV series ``indicator_engine.compute_full_indicator_series`` is
    built on. We choose the most recent daily bar strictly before
    ``as_of`` (default: today, UTC).

    If ``price_data`` is empty for the symbol, we fall back to
    ``MarketSnapshot.as_of_timestamp`` + ``current_price`` so symbols
    that have a snapshot row but no local OHLCV cache can still get a
    prior close. Rows where neither exists return ``None``.
    """
    if not symbol:
        return None

    as_of_date = as_of or datetime.utcnow().date()
    # Bar dates in ``price_data`` are stored as DATETIME at 00:00 UTC;
    # using the date at midnight as a strict upper bound picks the
    # previous trading day without double-counting today's bar.
    as_of_cutoff = datetime.combine(as_of_date, datetime.min.time())

    # Primary: latest daily bar strictly before as_of.
    row = (
        db.query(PriceData)
        .filter(
            PriceData.symbol == symbol,
            PriceData.interval == "1d",
            PriceData.date < as_of_cutoff,
        )
        .order_by(PriceData.date.desc())
        .first()
    )
    if row is not None and row.close_price is not None:
        close = _to_decimal(row.close_price)
        if close is not None and close > 0:
            bar_date = row.date.date() if isinstance(row.date, datetime) else row.date
            return (close, bar_date)

    # Fallback: MarketSnapshot ``as_of_timestamp`` + ``current_price``.
    # The snapshot is computed from the same OHLCV series, so if the
    # snapshot is from a prior session it's a trustworthy reference.
    snap = (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.analysis_type == "technical_snapshot",
        )
        .order_by(MarketSnapshot.analysis_timestamp.desc())
        .first()
    )
    if snap is not None and snap.current_price and snap.as_of_timestamp is not None:
        snap_date = (
            snap.as_of_timestamp.date()
            if isinstance(snap.as_of_timestamp, datetime)
            else snap.as_of_timestamp
        )
        if snap_date < as_of_date:
            close = _to_decimal(snap.current_price)
            if close is not None and close > 0:
                return (close, snap_date)

    return None


def has_ambiguous_corporate_action(
    db: Session,
    symbol: str,
    prior_close_date: date,
    *,
    as_of: Optional[date] = None,
) -> bool:
    """``True`` if a SPLIT / REVERSE_SPLIT / STOCK_DIVIDEND has
    ``ex_date`` in ``(prior_close_date, as_of]``.

    When true, the caller must set ``day_pnl`` and ``day_pnl_pct`` to
    ``None``: the prior close is on a different price scale than the
    current price, and a naive difference would reproduce the RIVN
    ``-$55,691`` bug.

    Cash dividends intentionally do NOT trigger — they reduce price by
    the dividend amount but share count is unchanged, so the resulting
    day P&L ≈ -(qty × dividend), which is the correct economic answer.
    A future PR can optionally adjust for cash-div drag; for now we
    report it as-is.
    """
    if not symbol or prior_close_date is None:
        return False
    as_of_date = as_of or datetime.utcnow().date()
    if prior_close_date >= as_of_date:
        return False

    exists = (
        db.query(CorporateAction.id)
        .filter(
            CorporateAction.symbol == symbol,
            CorporateAction.action_type.in_(_SPLIT_LIKE_TYPES),
            CorporateAction.ex_date > prior_close_date,
            CorporateAction.ex_date <= as_of_date,
        )
        .first()
    )
    return exists is not None


def compute_day_pnl(
    quantity: Decimal,
    current_price: Decimal,
    prior_close: Decimal,
    market_value: Decimal,
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Return ``(day_pnl, day_pnl_pct)``.

    Formula:

    * ``day_pnl = quantity × (current_price - prior_close)``
    * ``day_pnl_pct = day_pnl / (market_value - day_pnl) × 100`` —
      matches the existing ``Position.update_market_data`` helper, i.e.
      the denominator is the *prior* market value.

    Returns ``(None, None)`` if:

    * any input is ``None`` or not finite
    * ``current_price`` or ``prior_close`` is non-positive
    * the percentage denominator collapses to zero (degenerate)

    Never returns ``(Decimal(0), ...)`` on error: zero is a valid
    market outcome; unknown is ``None``.
    """
    qty = _to_decimal(quantity)
    cur = _to_decimal(current_price)
    prior = _to_decimal(prior_close)
    mv = _to_decimal(market_value)
    if qty is None or cur is None or prior is None or mv is None:
        return (None, None)
    if cur <= 0 or prior <= 0:
        return (None, None)

    # Use |quantity| so a short position's day P&L is still measured
    # against the number of shares moved. Sign of day_pnl is driven by
    # the price delta for longs; for shorts the caller inverts via the
    # position type (we stay price-delta native here).
    abs_qty = abs(qty)
    if abs_qty == 0:
        return (None, None)

    day_pnl = abs_qty * (cur - prior)
    denom = mv - day_pnl
    if denom == 0:
        return (day_pnl, None)
    day_pnl_pct = (day_pnl / denom) * Decimal("100")
    return (day_pnl, day_pnl_pct)


def recompute_position_day_pnl(
    db: Session,
    position: "Position",
    *,
    as_of: Optional[date] = None,
) -> None:
    """Mutates ``position.day_pnl`` and ``position.day_pnl_pct`` in
    place.

    Sets both to ``None`` on ambiguity (split-drift window or missing
    prior_close). Does NOT commit — caller owns the session.

    Short positions: we use |quantity| in :func:`compute_day_pnl` and
    then flip sign for SHORT position types so a long's gain equals a
    short's loss on the same price move.
    """
    from app.models.position import PositionType  # late import: avoid cycle

    if position is None or not position.symbol or position.quantity is None:
        return

    qty = _to_decimal(position.quantity)
    cur = _to_decimal(position.current_price)
    mv = _to_decimal(position.market_value)
    if qty is None or cur is None or mv is None or qty == 0 or cur <= 0:
        position.day_pnl = None
        position.day_pnl_pct = None
        return

    resolved = resolve_prior_close(db, position.symbol, as_of=as_of)
    if resolved is None:
        position.day_pnl = None
        position.day_pnl_pct = None
        return
    prior_close, prior_close_date = resolved

    if has_ambiguous_corporate_action(
        db, position.symbol, prior_close_date, as_of=as_of
    ):
        logger.info(
            "day_pnl: nulling %s (qty=%s): split-like corporate action between "
            "prior_close_date=%s and as_of=%s",
            position.symbol,
            qty,
            prior_close_date,
            as_of or datetime.utcnow().date(),
        )
        position.day_pnl = None
        position.day_pnl_pct = None
        return

    day_pnl, day_pnl_pct = compute_day_pnl(
        quantity=qty,
        current_price=cur,
        prior_close=prior_close,
        market_value=mv,
    )
    if day_pnl is None:
        position.day_pnl = None
        position.day_pnl_pct = None
        return

    # Short position: price up = loss. Flip sign.
    is_short = position.position_type in (
        PositionType.SHORT,
        PositionType.OPTION_SHORT,
        PositionType.FUTURE_SHORT,
    )
    if is_short:
        day_pnl = -day_pnl
        if day_pnl_pct is not None:
            day_pnl_pct = -day_pnl_pct

    position.day_pnl = day_pnl
    position.day_pnl_pct = day_pnl_pct


def recompute_day_pnl_for_rows(
    db: Session,
    rows: Iterable["Position"],
    source_label: str,
    *,
    as_of: Optional[date] = None,
) -> Dict[str, int]:
    """Recompute day P&L for a batch of positions with structured counters.

    Returns a dict with ``day_pnl_recomputed``, ``day_pnl_nulled_due_to_split``,
    ``day_pnl_nulled_due_to_missing_prior_close``, ``day_pnl_errors``.

    Asserts that the counters sum to ``len(rows)`` (no silent drift, per
    ``.cursor/rules/no-silent-fallback.mdc`` and engineering rule 9).

    ``source_label`` is used only for log context (e.g. ``'schwab'``,
    ``'etrade'``, ``'ibkr'``, ``'tastytrade'``, ``'refresh_prices'``).
    """
    rows_list = list(rows)
    recomputed = 0
    nulled_split = 0
    nulled_missing = 0
    errors = 0

    for p in rows_list:
        try:
            if p is None or not p.symbol or p.quantity is None:
                errors += 1
                continue
            resolved = resolve_prior_close(db, p.symbol, as_of=as_of)
            if resolved is None:
                p.day_pnl = None
                p.day_pnl_pct = None
                nulled_missing += 1
                continue
            _, prior_close_date = resolved
            if has_ambiguous_corporate_action(
                db, p.symbol, prior_close_date, as_of=as_of
            ):
                p.day_pnl = None
                p.day_pnl_pct = None
                nulled_split += 1
                continue
            recompute_position_day_pnl(db, p, as_of=as_of)
            recomputed += 1
        except Exception as e:  # noqa: BLE001 — per-row isolation, counted
            errors += 1
            logger.warning(
                "%s day_pnl: recompute failed for position %s (%s): %s",
                source_label,
                getattr(p, "id", "?"),
                getattr(p, "symbol", "?"),
                e,
            )

    total = len(rows_list)
    assert recomputed + nulled_split + nulled_missing + errors == total, (
        f"{source_label} day_pnl counter drift: "
        f"{recomputed}+{nulled_split}+{nulled_missing}+{errors} != {total}"
    )
    logger.info(
        "%s day_pnl: recomputed=%d nulled_due_to_split=%d "
        "nulled_due_to_missing_prior_close=%d errors=%d total=%d",
        source_label,
        recomputed,
        nulled_split,
        nulled_missing,
        errors,
        total,
    )
    return {
        "day_pnl_recomputed": recomputed,
        "day_pnl_nulled_due_to_split": nulled_split,
        "day_pnl_nulled_due_to_missing_prior_close": nulled_missing,
        "day_pnl_errors": errors,
    }
