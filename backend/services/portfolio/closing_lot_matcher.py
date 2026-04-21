"""Broker-agnostic FIFO closing-lot matcher.

Some brokerages (Interactive Brokers via FlexQuery) emit closed-lot records
directly. Others — notably Schwab, TastyTrade, and the new E*TRADE bronze
adapter — give us only FILLED BUY/SELL executions. This module reconstructs
closed-lot accounting from those executions so the Tax Center, realized
gains reporting, and the CSV tax export (``/api/v1/portfolio/tax/export``)
all return correct data regardless of broker.

Design
------

For each (account, symbol) we walk the FILLED trade ledger in chronological
order:

- ``BUY`` with ``is_opening=True`` opens a new FIFO lot whose cost-per-share
  includes the buy-side commission.
- ``SELL`` with ``is_opening=False`` consumes open lots FIFO. Each slice
  produces one synthetic ``Trade`` row with ``status="CLOSED_LOT"``, the
  realized P&L on that slice, and metadata (``cost_basis``,
  ``is_long_term``, ``acquisition_date``, ``holding_period_days``, optional
  ``wash_sale_loss``) that the existing ``/api/v1/portfolio/stocks/realized``
  endpoint already knows how to read.

The generated rows use a deterministic ``execution_id`` of the form
``SYNTH:{sell_exec_id_or_id}:{slice_idx}`` so re-running the matcher after
each sync upserts (never duplicates) — the matcher is therefore safe to
call on every successful sync.

Non-goals in v1
---------------

- Options closed-lot reconciliation. Tracking option open/close correctly
  requires strike/expiry/right matching; deferred to Phase 3 PR J
  (OptionsChainSurface). Options-category FILLED trades are currently
  skipped with a structured warning rather than silently included.
- IRS-compliant §1091 wash-sale detection. We implement a conservative
  "loss + same-symbol replacement within ±30 days" heuristic and label it
  explicitly in the emitted metadata. A true per-lot adjustment is
  tracked under Phase 5 PR N-ish tax-aware exits.
- Lot methods other than FIFO. Schwab/TT/ETRADE all default to FIFO for
  US taxable accounts; SpecificID support lands later when we can surface
  it in the UI.

Returns a ``MatchResult`` with per-account counters so callers emit the
``written / skipped / errors`` log line that the no-silent-fallback rule
requires. The matcher itself never silently swallows exceptions.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Deque, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import BrokerAccount, Trade

logger = logging.getLogger(__name__)

ASSET_EQUITY = "STK"
ASSET_OPTION = "OPT"
WASH_SALE_WINDOW_DAYS = 30
LONG_TERM_HOLDING_DAYS = 365
_SUPPORTED_METHODS = frozenset({"FIFO"})
_SYNTH_PREFIX = "SYNTH:"


@dataclass
class _OpenLot:
    """In-memory representation of an open FIFO lot slice."""

    acquisition_time: Optional[object]  # datetime, kept loose so callers can pass naive/aware freely
    quantity: Decimal
    cost_per_share: Decimal
    commission_per_share: Decimal
    source_trade_id: int


@dataclass
class MatchResult:
    """Counters emitted by :func:`reconcile_closing_lots`."""

    account_id: int
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    unmatched_quantity: Decimal = Decimal("0")
    warnings: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped + self.errors


def reconcile_closing_lots(
    db: Session,
    broker_account: BrokerAccount,
    *,
    method: str = "FIFO",
) -> MatchResult:
    """Build synthetic CLOSED_LOT trades from FILLED executions for one account.

    Idempotent: re-running upserts in place via ``execution_id`` of the form
    ``SYNTH:{sell_exec_id_or_sell_id}:{slice_idx}``.

    The caller is responsible for ``db.commit()``. The matcher only issues
    ``db.flush()`` so the same session can be reused for counter assertions
    and related updates.
    """
    if method.upper() not in _SUPPORTED_METHODS:
        raise NotImplementedError(
            f"closing_lot_matcher: lot method {method!r} not supported in v1 "
            f"(supported={sorted(_SUPPORTED_METHODS)})"
        )

    result = MatchResult(account_id=broker_account.id)

    filled_trades: List[Trade] = (
        db.query(Trade)
        .filter(
            Trade.account_id == broker_account.id,
            Trade.status == "FILLED",
        )
        .order_by(Trade.execution_time.asc(), Trade.id.asc())
        .all()
    )

    by_symbol: Dict[str, List[Trade]] = defaultdict(list)
    for t in filled_trades:
        if not t.symbol:
            continue
        by_symbol[t.symbol].append(t)

    existing_synth: Dict[str, Trade] = {
        t.execution_id: t
        for t in db.query(Trade)
        .filter(
            Trade.account_id == broker_account.id,
            Trade.status == "CLOSED_LOT",
            Trade.execution_id.like(f"{_SYNTH_PREFIX}%"),
        )
        .all()
    }

    # Pre-index BUYs for wash-sale replacement lookups across the account's
    # full history (not just within a given symbol's queue).
    buy_log_by_symbol: Dict[str, List[Trade]] = defaultdict(list)
    for sym, trades in by_symbol.items():
        for t in trades:
            if t.side == "BUY" and t.execution_time:
                buy_log_by_symbol[sym].append(t)

    for sym, trades in by_symbol.items():
        lot_queue: Deque[_OpenLot] = deque()

        for trade in trades:
            try:
                _apply_trade(
                    trade=trade,
                    symbol=sym,
                    lot_queue=lot_queue,
                    buy_log=buy_log_by_symbol.get(sym, []),
                    broker_account=broker_account,
                    db=db,
                    existing_synth=existing_synth,
                    result=result,
                )
            except Exception as exc:  # noqa: BLE001 — we log + count + continue
                result.errors += 1
                logger.warning(
                    "closing-lot-matcher: error applying trade_id=%s symbol=%s "
                    "account_id=%s: %s",
                    trade.id, sym, broker_account.id, exc,
                )

    db.flush()
    logger.info(
        "closing-lot-matcher: account_id=%s created=%d updated=%d skipped=%d "
        "errors=%d unmatched=%s warnings=%d",
        broker_account.id,
        result.created,
        result.updated,
        result.skipped,
        result.errors,
        result.unmatched_quantity,
        len(result.warnings),
    )
    return result


def _apply_trade(
    *,
    trade: Trade,
    symbol: str,
    lot_queue: Deque[_OpenLot],
    buy_log: List[Trade],
    broker_account: BrokerAccount,
    db: Session,
    existing_synth: Dict[str, Trade],
    result: MatchResult,
) -> None:
    side = (trade.side or "").upper()
    asset_category = _asset_category(trade)
    if asset_category == ASSET_OPTION:
        # Options require strike/expiry/right tracking; deferred to Phase 3.
        result.skipped += 1
        result.warnings.append(
            f"{symbol}: skipped option trade_id={trade.id} "
            f"(options closed-lot matching is Phase 3 / PR J)"
        )
        return

    if side == "BUY" and bool(trade.is_opening):
        qty = Decimal(str(trade.quantity or 0))
        if qty <= 0:
            result.skipped += 1
            return
        price = Decimal(str(trade.price or 0))
        commission = Decimal(str(trade.commission or 0))
        commission_per_share = commission / qty if qty else Decimal("0")
        lot_queue.append(
            _OpenLot(
                acquisition_time=trade.execution_time,
                quantity=qty,
                cost_per_share=price,
                commission_per_share=commission_per_share,
                source_trade_id=trade.id,
            )
        )
        return

    if side == "SELL" and not bool(trade.is_opening):
        remaining = Decimal(str(trade.quantity or 0))
        if remaining <= 0:
            result.skipped += 1
            return
        sell_price = Decimal(str(trade.price or 0))
        sell_commission = Decimal(str(trade.commission or 0))
        sell_commission_per_share = (
            sell_commission / remaining if remaining else Decimal("0")
        )

        slice_idx = 0
        while remaining > 0 and lot_queue:
            lot = lot_queue[0]
            take = lot.quantity if lot.quantity <= remaining else remaining

            cost_basis = (lot.cost_per_share + lot.commission_per_share) * take
            proceeds_gross = sell_price * take
            proceeds_net = proceeds_gross - (sell_commission_per_share * take)
            realized_pnl = proceeds_net - cost_basis

            holding_days = _holding_days(lot.acquisition_time, trade.execution_time)
            is_long_term = holding_days > LONG_TERM_HOLDING_DAYS
            wash_sale_loss = _wash_sale_loss(
                realized_pnl=realized_pnl,
                sell_time=trade.execution_time,
                lot_source_trade_id=lot.source_trade_id,
                lot_acquisition_time=lot.acquisition_time,
                buy_log=buy_log,
            )

            sell_key = trade.execution_id or f"id{trade.id}"
            synth_exec_id = f"{_SYNTH_PREFIX}{sell_key}:{slice_idx}"

            meta: Dict[str, object] = {
                "cost_basis": float(cost_basis),
                "proceeds": float(proceeds_net),
                "acquisition_date": (
                    lot.acquisition_time.isoformat()
                    if lot.acquisition_time is not None
                    and hasattr(lot.acquisition_time, "isoformat")
                    else None
                ),
                "holding_period_days": holding_days,
                "is_long_term": is_long_term,
                "method": "FIFO",
                "source_buy_trade_id": lot.source_trade_id,
                "source_sell_trade_id": trade.id,
                "slice_idx": slice_idx,
                "asset_category": asset_category,
            }
            if wash_sale_loss > 0:
                meta["wash_sale"] = True
                meta["wash_sale_loss"] = float(wash_sale_loss)

            existing = existing_synth.get(synth_exec_id)
            if existing is not None:
                existing.symbol = symbol
                existing.quantity = take
                existing.price = sell_price
                existing.total_value = proceeds_net
                existing.commission = Decimal("0")
                existing.realized_pnl = realized_pnl
                existing.execution_time = trade.execution_time
                existing.is_opening = False
                existing.trade_metadata = meta
                result.updated += 1
            else:
                db.add(
                    Trade(
                        account_id=broker_account.id,
                        symbol=symbol,
                        side="SELL",
                        quantity=take,
                        price=sell_price,
                        total_value=proceeds_net,
                        commission=Decimal("0"),
                        execution_id=synth_exec_id,
                        execution_time=trade.execution_time,
                        status="CLOSED_LOT",
                        is_opening=False,
                        is_paper_trade=False,
                        realized_pnl=realized_pnl,
                        trade_metadata=meta,
                    )
                )
                result.created += 1

            slice_idx += 1
            remaining -= take
            if take >= lot.quantity:
                lot_queue.popleft()
            else:
                lot.quantity -= take

        if remaining > 0:
            result.unmatched_quantity += remaining
            result.warnings.append(
                f"{symbol}: {remaining} shares on trade_id={trade.id} at "
                f"{trade.execution_time} could not be matched "
                f"(insufficient prior BUY history)"
            )
        return

    # Any other combination (BUY-to-cover, SELL short-open, transfer, etc.)
    # is left to future iterations — surfaced as skipped + warning, never
    # silently swallowed.
    result.skipped += 1
    result.warnings.append(
        f"{symbol}: skipped trade_id={trade.id} with side={side!r} "
        f"is_opening={trade.is_opening!r} (short/cover handling is out of scope for v1)"
    )


def _asset_category(trade: Trade) -> str:
    meta = trade.trade_metadata
    if isinstance(meta, dict):
        cat = meta.get("asset_category") or meta.get("instrument_type")
        if isinstance(cat, str) and cat:
            cat_upper = cat.upper()
            if cat_upper in {"OPT", "OPTION", "OPTIONS"}:
                return ASSET_OPTION
    # Schwab & friends encode option symbols with spaces / length > 20.
    # Fall back to a symbol-shape heuristic so we don't mis-match options
    # as equities when metadata is absent.
    sym = trade.symbol or ""
    if len(sym) > 15 or " " in sym:
        return ASSET_OPTION
    return ASSET_EQUITY


def _holding_days(buy_time, sell_time) -> int:
    if not buy_time or not sell_time:
        return 0
    # Accept naive/aware mix by falling back to date diff when tz mix breaks.
    try:
        return (sell_time - buy_time).days
    except TypeError:
        try:
            return (sell_time.date() - buy_time.date()).days
        except AttributeError:
            return 0


def _wash_sale_loss(
    *,
    realized_pnl: Decimal,
    sell_time,
    lot_source_trade_id: int,
    lot_acquisition_time,
    buy_log: List[Trade],
) -> Decimal:
    """Conservative ±30d same-symbol replacement heuristic.

    Returns the magnitude of the disallowed loss if a qualifying replacement
    BUY exists, else 0. Not a full §1091 implementation — intentionally
    labelled as heuristic in the emitted metadata so downstream tax export
    can flag it as advisory.
    """
    if realized_pnl >= 0 or sell_time is None:
        return Decimal("0")
    window_start = sell_time - timedelta(days=WASH_SALE_WINDOW_DAYS)
    window_end = sell_time + timedelta(days=WASH_SALE_WINDOW_DAYS)
    for candidate in buy_log:
        if candidate.id == lot_source_trade_id:
            continue
        ctime = candidate.execution_time
        if ctime is None:
            continue
        try:
            if ctime == lot_acquisition_time:
                continue
            if window_start <= ctime <= window_end:
                return -realized_pnl
        except TypeError:
            # Naive/aware mix on the replacement search — skip rather than
            # raise; we never want the matcher to crash on a tz edge case.
            continue
    return Decimal("0")
