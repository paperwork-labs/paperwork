"""User-scoped options chain (surface) read API."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import SessionLocal, get_db
from app.models.market.options_chain_snapshot import OptionsChainSnapshot
from app.models.position import Position, PositionStatus
from app.models.user import User
from app.models.watchlist import Watchlist
from app.services.gold.options_chain_surface import (
    ChainSourceUnavailableError,
    OptionsChainSurface,
)

router = APIRouter(prefix="/options", tags=["Options"])


def _latest_snapshot_ts(db: Session, sym: str, expiry: date | None) -> datetime | None:
    """Max snapshot time for this symbol, optionally restricted to one expiry."""
    max_ts_q = db.query(func.max(OptionsChainSnapshot.snapshot_taken_at)).filter(
        OptionsChainSnapshot.symbol == sym
    )
    if expiry is not None:
        max_ts_q = max_ts_q.filter(OptionsChainSnapshot.expiry == expiry)
    return max_ts_q.scalar()


def _user_may_read_chain(db: Session, user_id: int, symbol: str) -> bool:
    u = (symbol or "").upper().strip()
    if not u:
        return False
    w = (
        db.query(Watchlist.id)
        .filter(
            Watchlist.user_id == user_id,
            Watchlist.symbol == u,
        )
        .first()
    )
    if w:
        return True
    p = (
        db.query(Position.id)
        .filter(
            Position.user_id == user_id,
            Position.status == PositionStatus.OPEN,
            Position.symbol == u,
        )
        .first()
    )
    if p:
        return True
    return False


def _row_to_dict(row: OptionsChainSnapshot) -> dict[str, Any]:
    def d(v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v)
        return v

    return {
        "strike": d(row.strike),
        "option_type": row.option_type,
        "bid": d(row.bid),
        "ask": d(row.ask),
        "mid": d(row.mid),
        "spread_abs": d(row.spread_abs),
        "spread_rel": d(row.spread_rel),
        "open_interest": row.open_interest,
        "volume": row.volume,
        "implied_vol": d(row.implied_vol),
        "iv_pctile_1y": d(row.iv_pctile_1y),
        "iv_rank_1y": d(row.iv_rank_1y),
        "liquidity_score": d(row.liquidity_score),
        "delta": d(row.delta),
        "gamma": d(row.gamma),
        "theta": d(row.theta),
        "vega": d(row.vega),
    }


@router.get("/chain/{symbol}")
async def get_options_chain(
    symbol: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    expiry: date | None = Query(None, description="Filter to one expiry (ISO)"),
    fresh: int = Query(0, ge=0, le=1, description="1 = recompute (sync, <=30s)"),
) -> dict[str, Any]:
    """Latest snapshot of the options surface, or a fresh recompute if requested."""
    sym = (symbol or "").upper().strip()
    if not _user_may_read_chain(db, int(user.id), sym):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Symbol not in your watchlist or open positions",
        )
    ex_list: list[date] | None = [expiry] if expiry is not None else None

    last_compute: dict[str, Any] = {}
    if fresh == 1:
        surface = OptionsChainSurface()
        uid = int(user.id)

        def _compute_in_thread() -> None:
            thread_session = SessionLocal()
            try:
                r = surface.compute(
                    sym,
                    uid,
                    expiries=ex_list,
                    session=thread_session,
                )
                last_compute["result"] = r
            finally:
                thread_session.close()

        try:
            await asyncio.wait_for(
                asyncio.to_thread(_compute_in_thread),
                timeout=30.0,
            )
        except TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Options chain recompute timed out",
            ) from None
        except ChainSourceUnavailableError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e

    max_ts = _latest_snapshot_ts(db, sym, expiry)
    if max_ts is None and fresh == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No options chain snapshot for this symbol yet; try fresh=1",
        )
    if max_ts is None:
        return {
            "symbol": sym,
            "snapshot_taken_at": None,
            "source": None,
            "expiries": [],
            "counters": {},
        }
    _order = (
        OptionsChainSnapshot.snapshot_taken_at.desc(),
        OptionsChainSnapshot.expiry.asc(),
        OptionsChainSnapshot.strike.asc(),
        OptionsChainSnapshot.option_type.asc(),
    )
    if expiry is not None:
        rows = (
            db.query(OptionsChainSnapshot)
            .filter(
                OptionsChainSnapshot.symbol == sym,
                OptionsChainSnapshot.snapshot_taken_at == max_ts,
                OptionsChainSnapshot.expiry == expiry,
            )
            .order_by(*_order)
            .all()
        )
    else:
        rows = (
            db.query(OptionsChainSnapshot)
            .filter(
                OptionsChainSnapshot.symbol == sym,
                OptionsChainSnapshot.snapshot_taken_at == max_ts,
            )
            .order_by(*_order)
            .all()
        )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No options chain data for the requested filter",
        )
    by_exp: dict[date, list[OptionsChainSnapshot]] = {}
    for r in rows:
        by_exp.setdefault(r.expiry, []).append(r)
    expiries_out = []
    for e in sorted(by_exp):
        cr = sorted(
            by_exp[e],
            key=lambda x: (x.option_type, x.strike),
        )
        expiries_out.append(
            {
                "expiry": e.isoformat(),
                "contracts": [_row_to_dict(x) for x in cr],
            }
        )
    first = rows[0]
    ctr: dict[str, Any] = {
        "row_count": len(rows),
    }
    if last_compute.get("result") is not None:
        r = last_compute["result"]
        ctr.update(
            {
                "contracts_processed": r.contracts_processed,
                "contracts_persisted": r.contracts_persisted,
                "contracts_skipped_no_iv": r.contracts_skipped_no_iv,
                "contracts_errored": r.contracts_errored,
                "contracts_skipped_malformed": r.contracts_skipped_malformed,
                "iv_history_queries": r.iv_history_queries,
            }
        )
    return {
        "symbol": sym,
        "snapshot_taken_at": first.snapshot_taken_at,
        "source": first.source,
        "expiries": expiries_out,
        "counters": ctr,
    }
