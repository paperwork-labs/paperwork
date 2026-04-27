"""Read-only API for auxiliary external signals (authenticated; symbol-scoped)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.external_signal import ExternalSignal
from app.models.user import User

router = APIRouter()


class ExternalSignalItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    source: str
    signal_date: date
    signal_type: str
    value: Optional[str] = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ExternalSignalsResponse(BaseModel):
    items: List[ExternalSignalItem]


def _row_to_item(r: ExternalSignal) -> ExternalSignalItem:
    v = r.value
    return ExternalSignalItem(
        id=r.id,
        symbol=r.symbol,
        source=r.source,
        signal_date=r.signal_date,
        signal_type=r.signal_type,
        value=None if v is None else format(v, "f"),
        raw_payload=dict(r.raw_payload) if r.raw_payload is not None else {},
        created_at=r.created_at.isoformat() if r.created_at else "",
    )


class ExternalSignalsBatchResponse(BaseModel):
    by_symbol: dict[str, List[ExternalSignalItem]]


def _load_external_items_for_symbol(
    db: Session, sym: str, days: int, *, per_symbol_max: int = 10
) -> list[ExternalSignalItem]:
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    rows = db.scalars(
        select(ExternalSignal)
        .where(
            ExternalSignal.symbol == sym,
            ExternalSignal.signal_date >= cutoff,
        )
        .order_by(ExternalSignal.signal_date.desc(), ExternalSignal.id.desc())
        .limit(per_symbol_max)
    ).all()
    return [_row_to_item(r) for r in rows]


@router.get("/external/batch", response_model=ExternalSignalsBatchResponse)
def list_external_signals_batch(
    symbols: str = Query(
        ...,
        min_length=1,
        max_length=2048,
        description="Comma-separated tickers, max 50 (deduplicated in order).",
    ),
    days: int = Query(7, ge=1, le=366),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExternalSignalsBatchResponse:
    """Batched read for Picks: one SQL round-trip, then per-symbol top rows in memory."""
    _ = current_user
    seen: set[str] = set()
    parts: list[str] = []
    for p in (s.strip() for s in symbols.split(",") if s.strip()):
        u = p.upper()[:32]
        if u not in seen:
            seen.add(u)
            parts.append(u)
    parts = parts[:50]
    if not parts:
        return ExternalSignalsBatchResponse(by_symbol={})
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    all_rows: list[ExternalSignal] = list(
        db.scalars(
            select(ExternalSignal)
            .where(
                ExternalSignal.symbol.in_(parts),
                ExternalSignal.signal_date >= cutoff,
            )
            .order_by(
                ExternalSignal.symbol,
                ExternalSignal.signal_date.desc(),
                ExternalSignal.id.desc(),
            )
        ).all()
    )
    grouped: dict[str, list[ExternalSignal]] = defaultdict(list)
    for r in all_rows:
        if len(grouped[r.symbol]) < 10:
            grouped[r.symbol].append(r)
    by_symbol: dict[str, list[ExternalSignalItem]] = {
        p: [_row_to_item(r) for r in grouped.get(p, [])] for p in parts
    }
    return ExternalSignalsBatchResponse(by_symbol=by_symbol)


@router.get("/external", response_model=ExternalSignalsResponse)
def list_external_signals(
    symbol: str = Query(..., min_length=1, max_length=32),
    days: int = Query(7, ge=1, le=366),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExternalSignalsResponse:
    _ = current_user
    sym = symbol.upper().strip()
    return ExternalSignalsResponse(
        items=_load_external_items_for_symbol(db, sym, days, per_symbol_max=500)
    )
