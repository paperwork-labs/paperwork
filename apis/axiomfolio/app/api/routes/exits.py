"""Exit-advice API.

Single read-only endpoint for the Winner Exit Advisor. Advisory only; never
triggers an order. All data is scoped to ``current_user.id``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.broker_account import BrokerAccount
from app.models.market_data import MarketSnapshot
from app.models.position import Position
from app.models.tax_lot import TaxLot
from app.models.user import User
from app.services.gold.peak_signal_engine import PeakSignalEngine
from app.services.gold.tax_aware_exit_calculator import (
    ExitLot,
    TaxAwareExitCalculator,
    TaxProfile,
)
from app.services.gold.winner_exit_advisor import WinnerExitAdvisor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exits", tags=["exits"])


def _d(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _latest_snapshot(db: Session, symbol: str) -> MarketSnapshot | None:
    return (
        db.query(MarketSnapshot)
        .filter(
            MarketSnapshot.symbol == symbol,
            MarketSnapshot.analysis_type == "technical_snapshot",
            MarketSnapshot.is_valid.is_(True),
        )
        .order_by(MarketSnapshot.analysis_timestamp.desc())
        .first()
    )


def _build_lots(lots: list[TaxLot], symbol: str) -> list[ExitLot]:
    """Order lots FIFO by acquisition date and convert to ``ExitLot``.

    Lots missing the fields the calculator needs (cost, date, quantity) are
    skipped with a log line; we never silently zero them.
    """
    out: list[ExitLot] = []
    for lot in sorted(
        lots,
        key=lambda x: (x.acquisition_date or date.max, x.id or 0),
    ):
        qty = _d(lot.quantity)
        cps = _d(lot.cost_per_share)
        if qty is None or qty <= Decimal("0"):
            logger.info(
                "exits: skipping lot %s for %s (quantity missing/zero)",
                lot.id,
                symbol,
            )
            continue
        if cps is None or cps < Decimal("0"):
            logger.info(
                "exits: skipping lot %s for %s (cost_per_share missing)",
                lot.id,
                symbol,
            )
            continue
        if lot.acquisition_date is None:
            logger.info(
                "exits: skipping lot %s for %s (acquisition_date missing)",
                lot.id,
                symbol,
            )
            continue
        out.append(
            ExitLot(
                shares=qty,
                cost_per_share=cps,
                acquired_on=lot.acquisition_date,
            )
        )
    return out


@router.get("/advise/{position_id}")
async def advise_exit(
    position_id: int = Path(..., ge=1, description="Position id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return a structured exit recommendation for one open position.

    The response composes three service outputs (peak signal, tax-aware
    exit, winner exit advice) plus a plain-English one-line summary. This
    endpoint is advisory only; it never places an order.
    """
    position = (
        db.query(Position)
        .filter(
            Position.id == position_id,
            Position.user_id == current_user.id,
        )
        .first()
    )
    if position is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    symbol = (position.symbol or "").upper().strip()
    if not symbol:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Position has no symbol",
        )

    quantity = _d(position.quantity) or Decimal("0")
    if quantity <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Position quantity is zero; nothing to advise",
        )

    current_price = _d(position.current_price) or _d(position.average_cost)
    if current_price is None or current_price <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Position has no usable current price",
        )

    # Snapshot (same tenancy model as pick_quality_scorer: snapshots are
    # universe-level, not per-user).
    snapshot = _latest_snapshot(db, symbol)
    peak = PeakSignalEngine().evaluate(symbol, snapshot)

    # Tax lots: scoped to the account the position belongs to, which already
    # belongs to the caller.
    raw_lots = (
        db.query(TaxLot)
        .filter(
            TaxLot.symbol == symbol,
            TaxLot.account_id == position.account_id,
        )
        .all()
    )
    lots = _build_lots(raw_lots, symbol)

    account: BrokerAccount | None = (
        db.query(BrokerAccount)
        .filter(
            BrokerAccount.id == position.account_id,
            BrokerAccount.user_id == current_user.id,
        )
        .first()
    )
    tax_advantaged = bool(account and account.is_tax_advantaged)

    # Default proposed exit = full quantity; the UI layer can re-call the
    # calculator directly with a fractional size if it offers a scale-ladder.
    calculator = TaxAwareExitCalculator(TaxProfile.conservative_default())

    # If lot coverage is insufficient (e.g. sync gap), run the calculator
    # with a synthetic lot from ``average_cost`` + ``created_at`` so the
    # advisor still returns directional advice. This is documented in the
    # response so the UI can flag it.
    lot_coverage = sum((l.shares for l in lots), Decimal("0"))
    synthetic_lot_used = False
    if lot_coverage < quantity:
        synthetic_lot_used = True
        fallback_cost = _d(position.average_cost)
        if fallback_cost is None or fallback_cost < Decimal("0"):
            fallback_cost = current_price
        fallback_date = (
            position.created_at.date()
            if isinstance(position.created_at, datetime)
            else date.today()
        )
        lots = [
            ExitLot(
                shares=quantity,
                cost_per_share=fallback_cost,
                acquired_on=fallback_date,
            )
        ]

    tax_result = calculator.evaluate(
        symbol=symbol,
        current_price=current_price,
        exit_shares=quantity,
        lots=lots,
        tax_advantaged=tax_advantaged,
    )

    atr_value = _d(snapshot.atr_14) if snapshot is not None else None
    regime_state = snapshot.regime_state if snapshot is not None else None

    advice = WinnerExitAdvisor().advise(
        symbol=symbol,
        peak=peak,
        tax=tax_result,
        current_price=current_price,
        stop_price=None,  # ExitCascade stop is owned by a protected-region
        # service and must not be imported here; UI can
        # render the stop separately.
        atr_value=atr_value,
        regime_state=regime_state,
    )

    return {
        "data": {
            "position_id": position.id,
            "symbol": symbol,
            "current_price": float(current_price),
            "quantity": float(quantity),
            "tax_advantaged": tax_advantaged,
            "synthetic_lot_used": synthetic_lot_used,
            "peak_signal": peak.to_payload(),
            "tax_aware_exit": tax_result.to_payload(),
            "advice": advice.to_payload(),
            "summary": advice.summary,
        }
    }
