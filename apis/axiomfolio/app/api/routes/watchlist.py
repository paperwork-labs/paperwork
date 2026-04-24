"""Watchlist routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.market_data import MarketSnapshot
from app.models.user import User
from app.models.watchlist import Watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(max_length=20)
    notes: str | None = Field(default=None, max_length=500)


class WatchlistItem(BaseModel):
    symbol: str
    notes: str | None
    created_at: str

    current_price: float | None = None
    name: str | None = None
    sector: str | None = None
    perf_1d: float | None = None
    rsi: float | None = None
    stage_label: str | None = None
    market_cap: float | None = None
    atr_percent: float | None = None


class WatchlistCheckResponse(BaseModel):
    watched: bool


@router.get("")
def list_watchlist(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    latest_snapshot = (
        db.query(
            MarketSnapshot.symbol,
            func.max(MarketSnapshot.id).label("max_id"),
        )
        .filter(MarketSnapshot.analysis_type == "technical_snapshot")
        .group_by(MarketSnapshot.symbol)
        .subquery()
    )

    rows = (
        db.query(Watchlist, MarketSnapshot)
        .outerjoin(
            latest_snapshot,
            Watchlist.symbol == latest_snapshot.c.symbol,
        )
        .outerjoin(
            MarketSnapshot,
            MarketSnapshot.id == latest_snapshot.c.max_id,
        )
        .filter(Watchlist.user_id == user.id)
        .order_by(Watchlist.created_at.desc())
        .all()
    )

    items = []
    for wl, snap in rows:
        item = WatchlistItem(
            symbol=wl.symbol,
            notes=wl.notes,
            created_at=wl.created_at.isoformat() if wl.created_at else "",
            current_price=snap.current_price if snap else None,
            name=snap.name if snap else None,
            sector=snap.sector if snap else None,
            perf_1d=snap.perf_1d if snap else None,
            rsi=snap.rsi if snap else None,
            stage_label=snap.stage_label if snap else None,
            market_cap=snap.market_cap if snap else None,
            atr_percent=snap.atr_percent if snap else None,
        )
        items.append(item)

    return {"data": [item.model_dump() for item in items]}


@router.post("")
def add_to_watchlist(
    req: WatchlistAddRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    symbol = req.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    existing = (
        db.query(Watchlist).filter(Watchlist.user_id == user.id, Watchlist.symbol == symbol).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{symbol} is already on your watchlist")

    entry = Watchlist(user_id=user.id, symbol=symbol, notes=req.notes)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "data": {
            "symbol": entry.symbol,
            "notes": entry.notes,
            "created_at": entry.created_at.isoformat() if entry.created_at else "",
        }
    }


@router.delete("/{symbol}")
def remove_from_watchlist(
    symbol: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    symbol = symbol.upper().strip()
    entry = (
        db.query(Watchlist).filter(Watchlist.user_id == user.id, Watchlist.symbol == symbol).first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail=f"{symbol} not found on your watchlist")

    db.delete(entry)
    db.commit()
    return {"data": {"removed": symbol}}


@router.get("/check/{symbol}")
def check_watchlist(
    symbol: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    symbol = symbol.upper().strip()
    exists = (
        db.query(Watchlist).filter(Watchlist.user_id == user.id, Watchlist.symbol == symbol).first()
    )
    return {"data": WatchlistCheckResponse(watched=exists is not None).model_dump()}
