"""Plaid holdings → Position + TaxLot persistence pipeline.

This is the only place Plaid JSON becomes ORM rows. Keeping it
decoupled from the client module means the sync service can mock
``persist_holdings`` in tests without patching the SDK surface.

Design constraints (plan ``docs/plans/PLAID_FIDELITY_401K.md`` §4):

* **One ``Position`` per ``(broker_account, symbol)``** — upserted so
  repeated syncs don't create duplicate rows.
* **One ``TaxLot`` with ``source=AGGREGATOR``, ``cost_per_share=None``**
  per holding. Plaid does NOT return per-lot basis; a single
  aggregator lot is the correct representation (not ``N`` synthetic
  lots faking FIFO). The ``no-silent-fallback`` rule forbids
  "pretend-basis" zeros.
* **Structured counters** — ``written`` / ``skipped_no_holdings`` /
  ``errors`` emitted from every sync, with ``assert sum == total`` so
  counter drift is loud.

medallion: silver
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.broker_account import BrokerAccount
from app.models.position import Position, PositionStatus, PositionType
from app.models.tax_lot import TaxLot, TaxLotSource

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Structured counters for a single sync run.

    All fields are required to follow ``.cursor/rules/no-silent-fallback.mdc``:
    ``written + skipped_no_holdings + errors == total`` is asserted at the
    end of ``persist_holdings`` so counter drift raises loudly instead of
    silently under-reporting failures.
    """

    total: int = 0
    written: int = 0
    skipped_no_holdings: int = 0
    errors: int = 0
    error_samples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "written": self.written,
            "skipped_no_holdings": self.skipped_no_holdings,
            "errors": self.errors,
            "error_samples": self.error_samples[:5],
        }


def _to_decimal(value: Any) -> Optional[Decimal]:
    """Convert Plaid's float/str numeric fields to Decimal safely.

    Plaid returns floats; monetary values must be ``Decimal`` per the
    IRON LAW in AGENTS.md. ``None`` passes through so ``null`` cost
    basis stays ``null`` downstream (never silently ``0``).
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _resolve_symbol(security: Optional[Dict[str, Any]]) -> Optional[str]:
    """Pick the best symbol for a Plaid security record.

    Preference order: ``ticker_symbol`` > ``name`` (truncated) > None.
    CUSIPs/ISINs aren't used because the rest of the portfolio stack
    keys on equity tickers; a CUSIP-only holding (typical for an
    in-plan mutual fund without a public ticker) is skipped upstream.
    """
    if not security:
        return None
    ticker = security.get("ticker_symbol")
    if isinstance(ticker, str) and ticker.strip():
        return ticker.strip().upper()
    # Fall back to name only for debugging; upstream treats None as
    # "skip this holding" (see persist_holdings).
    return None


def _position_type_for(security: Optional[Dict[str, Any]]) -> PositionType:
    """Map a Plaid security ``type`` to our :class:`PositionType`.

    Only LONG equity positions are supported in this phase (Plaid
    Investments doesn't expose shorts). Options would require a
    separate lot shape and are out of scope per the plan.
    """
    sec_type = (security or {}).get("type")
    # Known Plaid types: 'equity', 'etf', 'mutual fund', 'fixed income',
    # 'cash', 'derivative', 'loan', 'other'. We treat all tradable
    # non-cash types as LONG here; cash-equivalent is excluded upstream.
    if sec_type == "derivative":
        return PositionType.OPTION_LONG
    return PositionType.LONG


def _upsert_position(
    session: Session,
    *,
    user_id: int,
    account: BrokerAccount,
    symbol: str,
    quantity: Decimal,
    current_price: Optional[Decimal],
    market_value: Optional[Decimal],
    position_type: PositionType,
    price_updated_at: Optional[datetime],
) -> Position:
    """Upsert a Position row scoped to the given user/account/symbol.

    The ``user_id`` scope is defensive — :func:`persist_holdings` already
    filters to the current user's accounts, but the ORM query below also
    filters by ``user_id`` so a bug in caller scoping still can't write
    across tenants.
    """
    position: Optional[Position] = (
        session.query(Position)
        .filter(
            Position.user_id == user_id,
            Position.account_id == account.id,
            Position.symbol == symbol,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if position is None:
        position = Position(
            user_id=user_id,
            account_id=account.id,
            symbol=symbol,
            instrument_type="STOCK",
            position_type=position_type,
            quantity=quantity,
            status=PositionStatus.OPEN,
            current_price=current_price,
            market_value=market_value,
            price_updated_at=price_updated_at,
            position_updated_at=now,
        )
        session.add(position)
        return position

    position.quantity = quantity
    position.position_type = position_type
    position.status = PositionStatus.OPEN
    if current_price is not None:
        position.current_price = current_price
    if market_value is not None:
        position.market_value = market_value
    if price_updated_at is not None:
        position.price_updated_at = price_updated_at
    position.position_updated_at = now
    return position


def _write_aggregator_tax_lot(
    session: Session,
    *,
    user_id: int,
    account: BrokerAccount,
    symbol: str,
    quantity: Decimal,
    current_price: Optional[Decimal],
    market_value: Optional[Decimal],
    item_id: str,
    plaid_account_id: str,
) -> TaxLot:
    """Write (or refresh) the single aggregator-sourced lot for a holding.

    The ``lot_id`` is derived from ``(item_id, plaid_account_id, symbol)``
    so repeated syncs refresh the same row instead of accumulating
    duplicates. ``cost_per_share`` and ``cost_basis`` are left ``None``
    deliberately — callers must check :attr:`TaxLot.gain_loss_available`
    before rendering cost-basis fields (silent-fallback rule).
    """
    lot_id = f"plaid:{item_id}:{plaid_account_id}:{symbol}"
    lot: Optional[TaxLot] = (
        session.query(TaxLot).filter(TaxLot.lot_id == lot_id).first()
    )
    now = datetime.now(timezone.utc)
    # TaxLot columns are Float, not Decimal — convert defensively.
    qty_float = float(quantity) if quantity is not None else None
    price_float = float(current_price) if current_price is not None else None
    mv_float = float(market_value) if market_value is not None else None

    if lot is None:
        lot = TaxLot(
            user_id=user_id,
            account_id=account.id,
            symbol=symbol,
            quantity=qty_float,
            cost_per_share=None,
            cost_basis=None,
            acquisition_date=None,
            current_price=price_float,
            market_value=mv_float,
            source=TaxLotSource.AGGREGATOR,
            lot_id=lot_id,
            last_price_update=now,
        )
        session.add(lot)
        return lot

    lot.quantity = qty_float
    lot.current_price = price_float
    lot.market_value = mv_float
    lot.source = TaxLotSource.AGGREGATOR
    lot.cost_per_share = None
    lot.cost_basis = None
    lot.last_price_update = now
    return lot


def persist_holdings(
    session: Session,
    *,
    user_id: int,
    item_id: str,
    broker_accounts_by_plaid_id: Dict[str, BrokerAccount],
    holdings_payload: Dict[str, Any],
) -> PipelineResult:
    """Upsert Position + TaxLot rows from a Plaid ``holdings`` response.

    Args:
        session: SQLAlchemy session — caller owns commit/rollback.
        user_id: Tenant scope; every write is validated against this id.
        item_id: Plaid Item id, for lot-id derivation.
        broker_accounts_by_plaid_id: pre-materialised map of Plaid
            ``account_id`` → :class:`BrokerAccount`. The caller (routes
            or sync service) is responsible for creating any missing
            BrokerAccount rows and supplying them here — this function
            does not create them because account-type resolution and
            plaid-subtype mapping belong at the route layer.
        holdings_payload: shape matching
            :meth:`PlaidClient.get_holdings` return.

    Returns:
        A :class:`PipelineResult` with structured counters.
    """
    holdings = holdings_payload.get("holdings") or []
    securities = holdings_payload.get("securities") or []
    securities_by_id: Dict[str, Dict[str, Any]] = {
        s.get("security_id"): s for s in securities if s.get("security_id")
    }

    result = PipelineResult(total=len(holdings))

    for holding in holdings:
        try:
            plaid_account_id = holding.get("account_id")
            account = broker_accounts_by_plaid_id.get(plaid_account_id or "")
            if account is None:
                # Caller didn't supply a BrokerAccount for this holding's
                # Plaid account. That's a bug upstream, not a silent skip.
                result.errors += 1
                msg = (
                    f"plaid holding references unknown plaid_account_id="
                    f"{plaid_account_id!r}"
                )
                result.error_samples.append(msg)
                logger.warning("persist_holdings: %s", msg)
                continue

            # Cross-tenant guard: the account MUST belong to user_id.
            if account.user_id != user_id:
                result.errors += 1
                msg = (
                    f"plaid holding account_id={account.id} "
                    f"user_id={account.user_id} != expected user_id={user_id}"
                )
                result.error_samples.append(msg)
                logger.error("persist_holdings cross-tenant guard: %s", msg)
                continue

            security = securities_by_id.get(holding.get("security_id") or "")
            symbol = _resolve_symbol(security)
            quantity = _to_decimal(holding.get("quantity"))

            if not symbol or quantity is None:
                # No usable ticker (e.g. mutual fund with CUSIP-only id)
                # or non-numeric quantity — count as skipped_no_holdings
                # rather than errors; the Item is still healthy.
                result.skipped_no_holdings += 1
                continue

            if quantity == 0:
                # Plaid sometimes reports closed holdings; we treat them
                # as "nothing to write" (could also close the row here,
                # but destructive closes belong in a dedicated reconcile
                # step).
                result.skipped_no_holdings += 1
                continue

            current_price = _to_decimal(holding.get("institution_price"))
            market_value = _to_decimal(holding.get("institution_value"))
            price_updated_raw = holding.get(
                "institution_price_as_of"
            ) or holding.get("institution_price_datetime")
            price_updated_at: Optional[datetime] = None
            if isinstance(price_updated_raw, datetime):
                price_updated_at = price_updated_raw
            elif isinstance(price_updated_raw, str) and price_updated_raw:
                # Plaid uses ISO dates; best-effort parse (no silent fallback
                # — if it fails we still write the row but leave the ts
                # unset rather than guess).
                try:
                    price_updated_at = datetime.fromisoformat(
                        price_updated_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    logger.debug(
                        "persist_holdings: unparseable price_as_of=%r",
                        price_updated_raw,
                    )

            position_type = _position_type_for(security)
            _upsert_position(
                session,
                user_id=user_id,
                account=account,
                symbol=symbol,
                quantity=quantity,
                current_price=current_price,
                market_value=market_value,
                position_type=position_type,
                price_updated_at=price_updated_at,
            )
            _write_aggregator_tax_lot(
                session,
                user_id=user_id,
                account=account,
                symbol=symbol,
                quantity=quantity,
                current_price=current_price,
                market_value=market_value,
                item_id=item_id,
                plaid_account_id=plaid_account_id or "",
            )
            result.written += 1
        except Exception as exc:  # noqa: BLE001 - structured-counter loop
            result.errors += 1
            msg = f"{type(exc).__name__}: {exc}"
            result.error_samples.append(msg[:200])
            logger.warning(
                "persist_holdings: failed on holding security_id=%s: %s",
                holding.get("security_id"),
                msg,
            )

    # Counter invariant (enforces no-silent-fallback rule R32).
    total_counted = result.written + result.skipped_no_holdings + result.errors
    if total_counted != result.total:
        raise AssertionError(
            f"persist_holdings counter drift: written={result.written} "
            f"skipped_no_holdings={result.skipped_no_holdings} "
            f"errors={result.errors} total={result.total}"
        )
    session.flush()
    logger.info(
        "persist_holdings: user_id=%s item_id=%s total=%d written=%d "
        "skipped_no_holdings=%d errors=%d",
        user_id,
        item_id,
        result.total,
        result.written,
        result.skipped_no_holdings,
        result.errors,
    )
    return result


__all__ = [
    "PipelineResult",
    "persist_holdings",
]
