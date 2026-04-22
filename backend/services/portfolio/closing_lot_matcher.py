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

- Options closed-lot reconciliation builds :class:`~backend.models.option_tax_lot.OptionTaxLot`
  rows (FIFO on ``(broker_account_id, symbol)``) instead of synthetic ``Trade`` rows.
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

Medallion layer: silver. See docs/ARCHITECTURE.md and D127.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Deque, Dict, Iterable, List, Optional, cast

from sqlalchemy.orm import Session

from backend.models import BrokerAccount, Trade
from backend.models.option_tax_lot import OptionTaxLot

logger = logging.getLogger(__name__)

ASSET_EQUITY = "STK"
ASSET_OPTION = "OPT"
WASH_SALE_WINDOW_DAYS = 30
LONG_TERM_HOLDING_DAYS = 365
_SUPPORTED_METHODS = frozenset({"FIFO"})
_SYNTH_PREFIX = "S:"
# Trade.execution_id is ``String(50)``. The synthetic id layout is
# ``S:{8-char hash}:{slice_idx}`` so we fit in ~13-16 characters even
# with generous slice indices. We include a loud guard below so any
# future length drift fails the unit test rather than the production
# sync with an IntegrityError on flush.
_SYNTH_MAX_LEN = 50
# Chunk size for the FILLED-trade stream. A 5000-share account still
# produces well under this cap, but a high-frequency options trader
# hits it — we stream to avoid materialising the full history in RAM.
_STREAM_CHUNK_SIZE = 500

_OCC_RE = re.compile(
    r"^(?P<underlying>[A-Z]{1,6})"
    r"(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?P<cp>[CP])"
    r"(?P<strike>\d{8})$"
)


@dataclass
class _OpenLot:
    """In-memory representation of an open FIFO lot slice."""

    acquisition_time: Optional[object]  # datetime, kept loose so callers can pass naive/aware freely
    quantity: Decimal
    cost_per_share: Decimal
    commission_per_share: Decimal
    source_trade_id: int


@dataclass
class _OptionOpenLot:
    """FIFO queue entry for option contracts (signed quantity)."""

    opened_at: object
    quantity: Decimal
    cost_basis_per_contract: Decimal
    source_trade_id: int
    multiplier: int
    original_quantity: Decimal


@dataclass
class MatchResult:
    """Counters emitted by :func:`reconcile_closing_lots`."""

    account_id: int
    created: int = 0
    updated: int = 0
    option_lots_created: int = 0
    option_lots_updated: int = 0
    skipped: int = 0
    errors: int = 0
    unmatched_quantity: Decimal = Decimal("0")
    warnings: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped + self.errors


def _parse_occ_option_symbol(symbol: str) -> Optional[Dict[str, object]]:
    """Parse OCC/OSI option symbol into contract fields."""
    cleaned = symbol.strip().replace(" ", "")
    m = _OCC_RE.match(cleaned)
    if not m:
        return None
    try:
        expiry = date(
            2000 + int(m.group("year")),
            int(m.group("month")),
            int(m.group("day")),
        )
    except ValueError:
        return None
    strike = Decimal(m.group("strike")) / Decimal("1000")
    cp = m.group("cp")
    return {
        "underlying": m.group("underlying"),
        "expiry": expiry,
        "option_type": "call" if cp == "C" else "put",
        "strike": strike,
    }


def _option_multiplier(trade: Trade) -> int:
    meta = trade.trade_metadata
    if isinstance(meta, dict):
        raw = meta.get("multiplier")
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return 100


def _option_holding_class(opened_at: object, closed_at: object) -> str:
    """Classify like equity CLOSED_LOT metadata: long-term when held *more than* 365 days."""
    if opened_at is None or closed_at is None:
        return "short_term"
    days = _holding_days(opened_at, closed_at)
    return "long_term" if days > LONG_TERM_HOLDING_DAYS else "short_term"


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

    # Stream FILLED trades in server-side chunks. ``.all()`` previously
    # materialised the full account history into RAM every sync — the
    # exact OOM pattern that took Tax Center down (see R34). We still
    # need to group by symbol so a per-symbol FIFO queue can walk them
    # in order; streaming keeps peak memory bounded to
    # ``_STREAM_CHUNK_SIZE`` Trade rows at a time rather than the whole
    # trade ledger. ``execution_time IS NOT NULL`` excludes broker rows
    # that lack an ordering timestamp (FIFO is undefined without it).
    by_symbol: Dict[str, List[Trade]] = defaultdict(list)
    streamed: Iterable[Trade] = (
        db.query(Trade)
        .filter(
            Trade.account_id == broker_account.id,
            Trade.status == "FILLED",
            Trade.execution_time.isnot(None),
        )
        .order_by(Trade.execution_time.asc(), Trade.id.asc())
        .yield_per(_STREAM_CHUNK_SIZE)
    )
    for t in streamed:
        if not t.symbol:
            continue
        by_symbol[t.symbol].append(t)

    existing_synth: Dict[str, Trade] = {}
    for t in (
        db.query(Trade)
        .filter(
            Trade.account_id == broker_account.id,
            Trade.status == "CLOSED_LOT",
            Trade.execution_id.like(f"{_SYNTH_PREFIX}%"),
        )
        .yield_per(_STREAM_CHUNK_SIZE)
    ):
        existing_synth[t.execution_id] = t

    existing_option_lots: Dict[tuple[int, int], OptionTaxLot] = {}
    for otl in (
        db.query(OptionTaxLot)
        .filter(OptionTaxLot.broker_account_id == broker_account.id)
        .yield_per(_STREAM_CHUNK_SIZE)
    ):
        if otl.closing_trade_id is not None:
            existing_option_lots[(otl.opening_trade_id, otl.closing_trade_id)] = otl

    # Pre-index BUYs for wash-sale replacement lookups across the account's
    # full history (not just within a given symbol's queue).
    buy_log_by_symbol: Dict[str, List[Trade]] = defaultdict(list)
    for sym, trades in by_symbol.items():
        for t in trades:
            if t.side == "BUY" and t.execution_time:
                buy_log_by_symbol[sym].append(t)

    for sym, trades in by_symbol.items():
        lot_queue: Deque[_OpenLot] = deque()
        option_lot_queue: Deque[_OptionOpenLot] = deque()

        for trade in trades:
            try:
                if _asset_category(trade) == ASSET_OPTION:
                    _apply_option_trade(
                        trade=trade,
                        symbol=sym,
                        lot_queue=option_lot_queue,
                        broker_account=broker_account,
                        db=db,
                        existing_option_lots=existing_option_lots,
                        result=result,
                        user_id=broker_account.user_id,
                    )
                else:
                    _apply_equity_trade(
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
        "closing-lot-matcher: account_id=%s created=%d updated=%d "
        "option_lots_created=%d option_lots_updated=%d skipped=%d "
        "errors=%d unmatched=%s warnings=%d",
        broker_account.id,
        result.created,
        result.updated,
        result.option_lots_created,
        result.option_lots_updated,
        result.skipped,
        result.errors,
        result.unmatched_quantity,
        len(result.warnings),
    )
    return result


def _persist_option_tax_slice(
    *,
    db: Session,
    broker_account: BrokerAccount,
    user_id: int,
    symbol: str,
    parsed: Dict[str, object],
    mult: int,
    open_snapshot_qty: Decimal,
    cost_basis_per_contract: Decimal,
    opened_at: object,
    opening_trade_id: int,
    quantity_closed: Decimal,
    proceeds_per_contract: Optional[Decimal],
    closed_at: object,
    closing_trade_id: int,
    existing_option_lots: Dict[tuple[int, int], OptionTaxLot],
    result: MatchResult,
) -> None:
    holding = _option_holding_class(opened_at, closed_at)
    realized: Optional[Decimal] = None
    if proceeds_per_contract is not None:
        realized = (proceeds_per_contract - cost_basis_per_contract) * quantity_closed * Decimal(
            mult
        )

    key = (opening_trade_id, closing_trade_id)
    existing = existing_option_lots.get(key)
    underlying = str(parsed["underlying"])
    expiry_raw = parsed["expiry"]
    strike_raw = parsed["strike"]
    if not isinstance(expiry_raw, date) or not isinstance(strike_raw, Decimal):
        raise TypeError("OCC parse payload has unexpected types")
    expiry = expiry_raw
    strike = strike_raw
    opt_type = str(parsed["option_type"])
    if existing is not None:
        existing.symbol = symbol
        existing.underlying = underlying
        existing.option_type = opt_type
        existing.strike = strike
        existing.expiry = expiry
        existing.multiplier = mult
        existing.quantity_opened = open_snapshot_qty
        existing.cost_basis_per_contract = cost_basis_per_contract
        existing.opened_at = opened_at  # type: ignore[assignment]
        existing.closed_at = closed_at  # type: ignore[assignment]
        existing.quantity_closed = quantity_closed
        existing.proceeds_per_contract = proceeds_per_contract
        existing.realized_pnl = realized
        existing.holding_class = holding
        existing.closing_trade_id = closing_trade_id
        result.updated += 1
        result.option_lots_updated += 1
        return

    row = OptionTaxLot(
        user_id=user_id,
        broker_account_id=broker_account.id,
        symbol=symbol,
        underlying=underlying,
        option_type=opt_type,
        strike=strike,
        expiry=expiry,
        multiplier=mult,
        quantity_opened=open_snapshot_qty,
        cost_basis_per_contract=cost_basis_per_contract,
        opened_at=opened_at,  # type: ignore[arg-type]
        closed_at=closed_at,  # type: ignore[arg-type]
        quantity_closed=quantity_closed,
        proceeds_per_contract=proceeds_per_contract,
        realized_pnl=realized,
        holding_class=holding,
        opening_trade_id=opening_trade_id,
        closing_trade_id=closing_trade_id,
    )
    db.add(row)
    existing_option_lots[key] = row
    result.created += 1
    result.option_lots_created += 1


def _apply_option_trade(
    *,
    trade: Trade,
    symbol: str,
    lot_queue: Deque[_OptionOpenLot],
    broker_account: BrokerAccount,
    db: Session,
    existing_option_lots: Dict[tuple[int, int], OptionTaxLot],
    result: MatchResult,
    user_id: int,
) -> None:
    parsed = _parse_occ_option_symbol(symbol)
    if parsed is None:
        result.skipped += 1
        result.warnings.append(
            f"{symbol}: could not parse OCC option symbol for trade_id={trade.id}"
        )
        return

    mult = _option_multiplier(trade)
    side = (trade.side or "").upper()
    is_open = bool(trade.is_opening)
    qty = Decimal(str(trade.quantity or 0))
    if qty <= 0:
        result.skipped += 1
        return
    if trade.execution_time is None:
        result.skipped += 1
        return

    commission = Decimal(str(trade.commission or 0))
    price = Decimal(str(trade.price or 0))

    if side == "BUY" and is_open:
        signed = qty
        if lot_queue and lot_queue[0].quantity < 0:
            result.skipped += 1
            result.warnings.append(
                f"{symbol}: conflicting option open (long) trade_id={trade.id} "
                f"while short lots are open"
            )
            return
        cpc = commission / qty if qty else Decimal("0")
        cost_basis = price + cpc
        lot_queue.append(
            _OptionOpenLot(
                opened_at=trade.execution_time,
                quantity=signed,
                cost_basis_per_contract=cost_basis,
                source_trade_id=trade.id,
                multiplier=mult,
                original_quantity=signed,
            )
        )
        return

    if side == "SELL" and is_open:
        signed = -qty
        if lot_queue and lot_queue[0].quantity > 0:
            result.skipped += 1
            result.warnings.append(
                f"{symbol}: conflicting option open (short) trade_id={trade.id} "
                f"while long lots are open"
            )
            return
        cpc = commission / qty if qty else Decimal("0")
        cost_basis = price - cpc
        lot_queue.append(
            _OptionOpenLot(
                opened_at=trade.execution_time,
                quantity=signed,
                cost_basis_per_contract=cost_basis,
                source_trade_id=trade.id,
                multiplier=mult,
                original_quantity=signed,
            )
        )
        return

    if side == "SELL" and not is_open:
        remaining = qty
        close_comm_per = commission / qty if qty else Decimal("0")
        while remaining > 0 and lot_queue:
            lot = lot_queue[0]
            if lot.quantity <= 0:
                break
            take = remaining if remaining <= lot.quantity else lot.quantity
            open_snapshot_qty = lot.original_quantity
            proceeds = price - close_comm_per
            qty_closed = take
            _persist_option_tax_slice(
                db=db,
                broker_account=broker_account,
                user_id=user_id,
                symbol=symbol,
                parsed=parsed,
                mult=lot.multiplier,
                open_snapshot_qty=open_snapshot_qty,
                cost_basis_per_contract=lot.cost_basis_per_contract,
                opened_at=lot.opened_at,
                opening_trade_id=lot.source_trade_id,
                quantity_closed=qty_closed,
                proceeds_per_contract=proceeds,
                closed_at=trade.execution_time,
                closing_trade_id=trade.id,
                existing_option_lots=existing_option_lots,
                result=result,
            )
            remaining -= take
            if take >= lot.quantity:
                lot_queue.popleft()
            else:
                lot.quantity -= take

        if remaining > 0:
            result.unmatched_quantity += remaining
            result.warnings.append(
                f"{symbol}: {remaining} contracts on trade_id={trade.id} "
                f"could not be matched (insufficient long inventory)"
            )
        return

    if side == "BUY" and not is_open:
        remaining = qty
        close_comm_per = commission / qty if qty else Decimal("0")
        short_covers: Dict[int, Dict[str, object]] = {}
        while remaining > 0 and lot_queue:
            lot = lot_queue[0]
            if lot.quantity >= 0:
                break
            cover = min(remaining, abs(lot.quantity))
            proceeds = price + close_comm_per
            oid = lot.source_trade_id
            bucket = short_covers.get(oid)
            if bucket is None:
                bucket = {
                    "initial_qty": abs(lot.original_quantity),
                    "cost_basis_per_contract": lot.cost_basis_per_contract,
                    "opened_at": lot.opened_at,
                    "mult": lot.multiplier,
                    "weighted_proceeds": Decimal("0"),
                    "total_cover": Decimal("0"),
                }
                short_covers[oid] = bucket
            bucket["weighted_proceeds"] = cast(Decimal, bucket["weighted_proceeds"]) + (
                proceeds * cover
            )
            bucket["total_cover"] = cast(Decimal, bucket["total_cover"]) + cover
            remaining -= cover
            if cover >= abs(lot.quantity):
                lot_queue.popleft()
            else:
                lot.quantity += cover

        for oid, bucket in short_covers.items():
            total_cover = cast(Decimal, bucket["total_cover"])
            wproc = cast(Decimal, bucket["weighted_proceeds"])
            vwap = wproc / total_cover if total_cover else Decimal("0")
            _persist_option_tax_slice(
                db=db,
                broker_account=broker_account,
                user_id=user_id,
                symbol=symbol,
                parsed=parsed,
                mult=int(bucket["mult"]),
                open_snapshot_qty=cast(Decimal, bucket["initial_qty"]),
                cost_basis_per_contract=cast(Decimal, bucket["cost_basis_per_contract"]),
                opened_at=bucket["opened_at"],
                opening_trade_id=oid,
                quantity_closed=-total_cover,
                proceeds_per_contract=vwap,
                closed_at=trade.execution_time,
                closing_trade_id=trade.id,
                existing_option_lots=existing_option_lots,
                result=result,
            )

        if remaining > 0:
            result.unmatched_quantity += remaining
            result.warnings.append(
                f"{symbol}: {remaining} contracts on trade_id={trade.id} "
                f"could not be matched (insufficient short inventory)"
            )
        return

    result.skipped += 1
    result.warnings.append(
        f"{symbol}: skipped option trade_id={trade.id} side={side!r} "
        f"is_opening={is_open!r}"
    )


def _apply_equity_trade(
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
            # Hash the broker execution_id to a short digest so the
            # synthetic id comfortably fits inside Trade.execution_id's
            # 50-char column even when the broker emits long/URL-like
            # execution ids (Schwab returns 30-40 char ids, IBKR can
            # return longer). The hash is deterministic so idempotency
            # on re-sync is preserved. The raw sell key is persisted in
            # ``trade_metadata.source_sell_execution_id`` for traceability.
            sell_key_digest = hashlib.blake2b(
                sell_key.encode("utf-8"), digest_size=4
            ).hexdigest()
            synth_exec_id = f"{_SYNTH_PREFIX}{sell_key_digest}:{slice_idx}"
            if len(synth_exec_id) > _SYNTH_MAX_LEN:
                # Defence in depth — ``_SYNTH_MAX_LEN`` is 50; the
                # current layout tops out around 15 chars. If someone
                # widens the prefix, fail loudly here rather than at
                # flush time with a psycopg2 IntegrityError.
                raise ValueError(
                    f"closing_lot_matcher: synth execution_id {synth_exec_id!r} "
                    f"exceeds Trade.execution_id({_SYNTH_MAX_LEN}) limit"
                )

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
                "source_sell_execution_id": sell_key,
            }
            if wash_sale_loss > 0:
                # Metadata-only wash-sale flag today. The existing tax
                # export treats wash sales via ``Trade.status="WASH_SALE"``;
                # we're deliberately not rewriting the export contract
                # in the closing-lot matcher PR — the tax exporter will
                # learn to also honour ``meta["wash_sale"]`` in Phase 5
                # (tax-aware exits, see GAPS_2026Q2 §G27). Until then
                # this flag is advisory for the UI only.
                meta["wash_sale"] = True
                meta["wash_sale_loss"] = float(wash_sale_loss)
                meta["wash_sale_heuristic"] = (
                    "same-symbol-30d-replacement"
                )

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
