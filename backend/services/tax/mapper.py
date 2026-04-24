"""
Pure mapper: trade rows + account rows -> FileFreePackage.

This module performs **no DB access**. The exporter layer (``filefree_exporter``)
is responsible for fetching rows; the mapper turns them into the wire-format
:class:`FileFreePackage`. Splitting it this way keeps unit tests cheap (no DB
fixtures required) and makes the transform logic auditable in isolation.

Input contracts:

* ``trades`` is an iterable of objects that look like SQLAlchemy ``Trade`` rows
  whose ``status`` is one of ``"CLOSED_LOT"`` or ``"WASH_SALE"`` (other statuses
  are silently ignored). The mapper reads these attributes::

      account_id          -> int (must match an entry in ``accounts``)
      symbol              -> str
      side                -> str (informational only)
      quantity            -> Decimal | float | str
      total_value         -> proceeds for the close
      execution_id        -> str | None  (used for stable lot_id)
      execution_time      -> datetime | None
      realized_pnl        -> Decimal | float | None
      status              -> "CLOSED_LOT" | "WASH_SALE"
      trade_metadata      -> dict (FlexQuery extras: cost_basis, open_date,
                              close_date, is_long_term, wash_sale_loss, source)
      id                  -> int (fallback for lot_id when execution_id is missing)

* ``accounts`` is an iterable of objects that look like ``BrokerAccount`` rows
  with ``id``, ``broker``, ``account_number``, ``account_type``,
  ``is_tax_advantaged`` (property or attribute).

Anything missing is filled with safe defaults and surfaced via ``warnings``.

medallion: silver
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .schemas import (
    SCHEMA_VERSION,
    DataQuality,
    FileFreeAccount,
    FileFreeLot,
    FileFreePackage,
    FileFreeSummary,
    InstrumentType,
    LotTerm,
)

logger = logging.getLogger(__name__)

ZERO = Decimal("0")

_BROKER_TO_DEFAULT_QUALITY: Dict[str, DataQuality] = {
    "ibkr": DataQuality.BROKER_OFFICIAL,
    "tastytrade": DataQuality.CALCULATED,
    "schwab": DataQuality.UNKNOWN,
    "fidelity": DataQuality.UNKNOWN,
    "robinhood": DataQuality.UNKNOWN,
}

_BROKER_TO_DEFAULT_SOURCE: Dict[str, str] = {
    "ibkr": "ibkr_flexquery",
    "tastytrade": "tastytrade_calculated",
    "schwab": "schwab",
    "fidelity": "fidelity",
    "robinhood": "robinhood",
}


def _to_decimal(value: Any, default: Decimal = ZERO) -> Decimal:
    """Coerce broker-supplied values to Decimal without losing precision.

    Floats are stringified first to avoid binary-to-decimal conversion noise
    (e.g. Decimal(0.1) != Decimal("0.1")).
    """
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def _to_date(value: Any) -> Optional[date]:
    """Coerce strings or datetimes to date; return None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # Accept ISO-8601 strings ("YYYY-MM-DD" or full timestamp).
        candidate = value.strip()
        if not candidate:
            return None
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
        try:
            # fromisoformat handles "YYYY-MM-DDTHH:MM:SS[+TZ]"
            return datetime.fromisoformat(candidate.rstrip("Z")).date()
        except ValueError:
            return None
    return None


def _enum_value(value: Any) -> str:
    """Return ``.value`` for enums, str(value) otherwise."""
    if value is None:
        return ""
    inner = getattr(value, "value", value)
    return str(inner)


def _account_ref(broker: str, account_number: Any) -> str:
    return f"{broker}:{account_number or 'unknown'}"


def _classify_term(meta: Dict[str, Any]) -> LotTerm:
    if meta.get("is_long_term") is True:
        return LotTerm.LONG_TERM
    if meta.get("is_long_term") is False:
        return LotTerm.SHORT_TERM
    # Some FlexQuery rows use the "openDateTime" + "tradeDate" pair instead;
    # if neither is set, fall back to UNKNOWN rather than guessing.
    return LotTerm.UNKNOWN


def _instrument_type(symbol: str, meta: Dict[str, Any]) -> InstrumentType:
    """Heuristic instrument classifier.

    OCC option symbols are 21 chars typically (e.g. 'AAPL  240119C00150000'),
    so anything > 12 chars with a space is treated as an option.
    """
    declared = (meta.get("instrument_type") or meta.get("asset_class") or "").lower()
    if declared in ("opt", "option", "fop"):
        return InstrumentType.OPTION
    if declared in ("etf", "fund"):
        return InstrumentType.ETF
    if " " in symbol or len(symbol) > 12:
        return InstrumentType.OPTION
    return InstrumentType.EQUITY


def _data_quality_for(broker: str, meta: Dict[str, Any]) -> Tuple[DataQuality, str]:
    """Return ``(quality, source_slug)`` for one trade row."""
    declared_source = (meta.get("source") or "").lower().strip()
    if declared_source:
        if declared_source.startswith("ibkr") or "flexquery" in declared_source:
            return DataQuality.BROKER_OFFICIAL, declared_source
        if declared_source.startswith("manual"):
            return DataQuality.MANUAL, declared_source
        if declared_source.startswith("calc"):
            return DataQuality.CALCULATED, declared_source
    quality = _BROKER_TO_DEFAULT_QUALITY.get(broker, DataQuality.UNKNOWN)
    source = _BROKER_TO_DEFAULT_SOURCE.get(broker, broker or "unknown")
    return quality, source


def _build_lot(
    trade: Any,
    account: Any,
    broker_slug: str,
    warnings: List[str],
) -> Optional[FileFreeLot]:
    """Map a single Trade-shaped row into a FileFreeLot."""

    status = (getattr(trade, "status", "") or "").upper()
    if status not in ("CLOSED_LOT", "WASH_SALE"):
        return None

    meta_raw = getattr(trade, "trade_metadata", None) or {}
    meta: Dict[str, Any] = dict(meta_raw) if isinstance(meta_raw, dict) else {}

    symbol = (getattr(trade, "symbol", None) or "").upper()
    if not symbol:
        warnings.append(
            f"trade id={getattr(trade, 'id', '?')} skipped: missing symbol"
        )
        return None

    qty = _to_decimal(getattr(trade, "quantity", None))
    proceeds = _to_decimal(getattr(trade, "total_value", None))
    cost_basis = _to_decimal(meta.get("cost_basis"))
    realized = _to_decimal(getattr(trade, "realized_pnl", None), default=proceeds - cost_basis)

    is_wash = status == "WASH_SALE"
    wash_amt: Optional[Decimal] = None
    adj_code: Optional[str] = None
    if is_wash:
        raw_wash = meta.get("wash_sale_loss") or meta.get("wash_sale_disallowed")
        wash_amt = abs(_to_decimal(raw_wash)) if raw_wash is not None else None
        adj_code = "W"

    execution_id = getattr(trade, "execution_id", None)
    trade_pk = getattr(trade, "id", None)
    lot_key = execution_id or f"trade-{trade_pk}" if trade_pk is not None else None
    if lot_key is None:
        warnings.append(
            f"trade for {symbol} skipped: no execution_id and no id"
        )
        return None
    lot_id = f"{getattr(account, 'id', 'na')}::{lot_key}"

    date_acquired = _to_date(meta.get("open_date") or meta.get("acquisition_date"))
    date_sold = _to_date(
        meta.get("close_date") or getattr(trade, "execution_time", None)
    )
    if date_sold is None:
        trade_pk = getattr(trade, "id", None)
        warnings.append(f"missing date_sold for trade {trade_pk}")
        return None

    quality, source = _data_quality_for(broker_slug, meta)

    description = f"{symbol} ({qty:f} sh)" if qty else symbol

    return FileFreeLot(
        lot_id=lot_id,
        account_ref=_account_ref(broker_slug, getattr(account, "account_number", None)),
        symbol=symbol,
        description=description,
        instrument_type=_instrument_type(symbol, meta),
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost_basis,
        realized_gain=realized,
        date_acquired=date_acquired,
        date_sold=date_sold,
        term=_classify_term(meta),
        is_wash_sale=is_wash,
        wash_sale_disallowed_loss=wash_amt,
        adjustment_code=adj_code,
        data_quality=quality,
        source=source,
    )


def _summarize(lots: Sequence[FileFreeLot]) -> FileFreeSummary:
    short = ZERO
    long_ = ZERO
    proceeds = ZERO
    basis = ZERO
    gain = ZERO
    wash_total = ZERO
    for lot in lots:
        proceeds += lot.proceeds
        basis += lot.cost_basis
        gain += lot.realized_gain
        if lot.term == LotTerm.SHORT_TERM:
            short += lot.realized_gain
        elif lot.term == LotTerm.LONG_TERM:
            long_ += lot.realized_gain
        if lot.is_wash_sale and lot.wash_sale_disallowed_loss:
            wash_total += lot.wash_sale_disallowed_loss
    return FileFreeSummary(
        lot_count=len(lots),
        total_proceeds=proceeds,
        total_cost_basis=basis,
        total_realized_gain=gain,
        total_short_term_gain=short,
        total_long_term_gain=long_,
        wash_sale_disallowed_total=wash_total,
    )


def build_package(
    *,
    user_id: int,
    tax_year: int,
    accounts: Iterable[Any],
    trades: Iterable[Any],
    generated_at: Optional[datetime] = None,
) -> FileFreePackage:
    """Build a :class:`FileFreePackage` from already-fetched DB rows.

    This function is **pure** -- it does no IO. All inputs are passed by the
    caller. The mapper:

    1. Indexes accounts by id so we can attach broker metadata to each lot.
    2. Walks trades, drops anything that's not a CLOSED_LOT or WASH_SALE row,
       and emits one ``FileFreeLot`` per closed slice.
    3. Computes per-account roll-ups (lot count, has_calculated_lots) and the
       global summary.
    4. Surfaces every quirky-data condition into the ``warnings`` list so the
       consumer (FileFree.ai UI) can show a banner instead of silently
       miscomputing the user's taxes.
    """
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    warnings: List[str] = []
    accounts_by_id: Dict[int, Any] = {}
    for account in accounts:
        acct_id = getattr(account, "id", None)
        if acct_id is None:
            warnings.append("skipped account with no id")
            continue
        accounts_by_id[int(acct_id)] = account

    # Group lots by account for per-account roll-up flags.
    per_account_lots: Dict[int, List[FileFreeLot]] = defaultdict(list)
    all_lots: List[FileFreeLot] = []

    for trade in trades:
        acct_id = getattr(trade, "account_id", None)
        if acct_id is None or int(acct_id) not in accounts_by_id:
            warnings.append(
                f"trade id={getattr(trade, 'id', '?')} skipped: "
                f"account_id={acct_id!r} not in scope"
            )
            continue
        account = accounts_by_id[int(acct_id)]
        broker_slug = _enum_value(getattr(account, "broker", "")).lower() or "unknown"

        lot = _build_lot(trade, account, broker_slug, warnings)
        if lot is None:
            continue
        per_account_lots[int(acct_id)].append(lot)
        all_lots.append(lot)

    # Build the per-account summaries (only for accounts that produced lots OR
    # were explicitly in scope -- the ladder lets the consumer see "this taxable
    # account had zero realized gains" instead of silently dropping it).
    account_blocks: List[FileFreeAccount] = []
    for acct_id, account in accounts_by_id.items():
        lots_for_acct = per_account_lots.get(acct_id, [])
        broker_slug = _enum_value(getattr(account, "broker", "")).lower() or "unknown"
        has_calc = any(lot.data_quality == DataQuality.CALCULATED for lot in lots_for_acct)

        account_blocks.append(
            FileFreeAccount(
                account_ref=_account_ref(
                    broker_slug, getattr(account, "account_number", None)
                ),
                broker=broker_slug,
                account_type=_enum_value(getattr(account, "account_type", "")).lower(),
                is_tax_advantaged=bool(
                    getattr(account, "is_tax_advantaged", False)
                ),
                lot_count=len(lots_for_acct),
                has_calculated_lots=has_calc,
            )
        )

        if has_calc:
            warnings.append(
                f"account {broker_slug}:{getattr(account, 'account_number', '?')} "
                "contains CALCULATED lots; reconcile with broker 1099-B before filing"
            )

    summary = _summarize(all_lots)

    return FileFreePackage(
        schema_version=SCHEMA_VERSION,
        generated_at=generated_at,
        tax_year=tax_year,
        user_id=user_id,
        accounts=account_blocks,
        lots=all_lots,
        summary=summary,
        warnings=warnings,
    )
