"""
Market IV (implied volatility) routes.

Per-symbol and batch IV-rank / IV-coverage read endpoints powering the
frontend ``useIvCoverage`` hook and the IV-Rank columns in watchlists
and scan tables (G5, ``docs/plans/G5_IV_RANK_SURFACE.md``).

The heavy lift -- daily ingest, rank math -- lives in
``app/services/market/historical_iv_service.py`` and
``app/tasks/market/iv.py``. These routes are thin reads.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_data_viewer
from app.database import get_db
from app.models.historical_iv import HistoricalIV
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["iv"])


# ``iv_rank_252`` needs 252 daily samples to be meaningful; below that
# threshold we return ``is_ramping=True`` and ``iv_rank=None`` so the UI
# can show "N/A" with a tooltip instead of pretending there's a value.
_RANK_READY_SAMPLES = 252


def _iv_coverage_for_symbol(symbol: str, db: Session) -> dict[str, Any]:
    sym = (symbol or "").upper().strip()
    if not sym:
        raise HTTPException(status_code=400, detail="symbol required")

    sample_count = int(
        db.query(HistoricalIV)
        .filter(
            HistoricalIV.symbol == sym,
            HistoricalIV.iv_30d.isnot(None),
        )
        .count()
        or 0
    )

    latest = (
        db.query(HistoricalIV)
        .filter(HistoricalIV.symbol == sym)
        .order_by(HistoricalIV.date.desc())
        .first()
    )

    iv_rank: float | None = None
    has_rank = False
    as_of: str | None = None
    if latest is not None:
        if latest.iv_rank_252 is not None:
            iv_rank = float(latest.iv_rank_252)
            has_rank = True
        as_of = str(latest.date) if latest.date is not None else None

    # "Ramping" iff we have at least one row but not enough history yet
    # to produce a stable 252-day percentile. Callers can render a
    # tooltip explaining the state instead of a silent dash.
    is_ramping = sample_count > 0 and sample_count < _RANK_READY_SAMPLES and not has_rank

    return {
        "symbol": sym,
        "iv_rank": iv_rank,
        "has_rank": has_rank,
        "is_ramping": is_ramping,
        "sample_count": sample_count,
        "as_of": as_of,
        # ``HistoricalIV`` does not yet store a provider tag; expose the
        # key so the hook is forward-compatible when that column lands.
        "source": None,
    }


@router.get("/iv/coverage/{symbol}")
def get_iv_coverage(
    symbol: str,
    db: Session = Depends(get_db),
    viewer: User = Depends(get_market_data_viewer),
) -> dict[str, Any]:
    """Return IV-rank / ramping state for one symbol."""
    try:
        return _iv_coverage_for_symbol(symbol, db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("iv/coverage failed for %s: %s", symbol, exc)
        raise HTTPException(status_code=500, detail="iv coverage unavailable")


@router.get("/iv/coverage")
def batch_iv_coverage(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    db: Session = Depends(get_db),
    viewer: User = Depends(get_market_data_viewer),
) -> dict[str, Any]:
    """Batch IV-coverage lookup for a watchlist / scan result page."""
    sym_list: list[str] = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="symbols required")
    if len(sym_list) > 500:
        raise HTTPException(status_code=400, detail="too many symbols (max 500)")

    out: list[dict[str, Any]] = []
    for sym in sym_list:
        try:
            out.append(_iv_coverage_for_symbol(sym, db))
        except Exception as exc:
            logger.warning("batch iv coverage: %s failed: %s", sym, exc)
            # Surface as a typed row rather than dropping silently so
            # the UI can decide what to do with failures.
            out.append(
                {
                    "symbol": sym,
                    "iv_rank": None,
                    "has_rank": False,
                    "is_ramping": False,
                    "sample_count": 0,
                    "as_of": None,
                    "source": None,
                    "error": str(exc)[:200],
                }
            )
    return {"count": len(out), "rows": out}
