"""Bulk EOD daily bar fill via FMP's eod-bulk endpoint.

Replaces ~2300 per-symbol API calls with 1 call per date.
The endpoint returns EOD bars for ALL US stocks; we filter to our tracked
universe in memory, then persist in a single bulk INSERT.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import pandas as pd
import requests
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.services.market.market_data_service import infra
from backend.services.market.rate_limiter import provider_rate_limiter
from backend.tasks.utils.task_utils import (
    _get_tracked_symbols_safe,
    _set_task_status,
    task_run,
)

logger = logging.getLogger(__name__)

_FMP_BULK_EOD_URL = "https://financialmodelingprep.com/stable/eod-bulk"
_FMP_BULK_TIMEOUT_S = 60


class BulkEndpointUnavailable(RuntimeError):
    """Raised when the FMP bulk EOD endpoint returns 402 (plan too low)."""


def _fetch_bulk_eod_for_date(date_str: str) -> List[Dict[str, Any]]:
    """Fetch bulk EOD bars from FMP for a single date.

    Returns a list of dicts with keys: symbol, date, open, high, low, close,
    adjClose, volume, etc.  Raises on HTTP or parse errors.
    Raises BulkEndpointUnavailable on 402 so callers can fall back.
    """
    api_key = settings.FMP_API_KEY
    if not api_key:
        raise RuntimeError("FMP_API_KEY not configured")

    provider_rate_limiter.acquire_sync("fmp")

    resp = requests.get(
        _FMP_BULK_EOD_URL,
        params={"date": date_str, "apikey": api_key},
        timeout=_FMP_BULK_TIMEOUT_S,
    )
    if resp.status_code == 402:
        raise BulkEndpointUnavailable(
            "FMP bulk EOD endpoint requires a paid plan (got 402)"
        )
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict):
        msg = data.get("Error Message") or data.get("error") or data.get("message")
        if msg:
            raise RuntimeError(f"FMP bulk EOD error: {msg}")

    if not isinstance(data, list):
        raise RuntimeError(f"FMP bulk EOD unexpected response type: {type(data).__name__}")

    infra._record_provider_call_sync("fmp", n=1)

    return data


def _validate_and_build_rows(
    raw_bars: List[Dict[str, Any]],
    tracked_set: Set[str],
) -> List[Dict[str, Any]]:
    """Filter bulk EOD bars to tracked universe and validate OHLCV.

    Returns a list of dicts ready for pg_insert into PriceData.
    """
    rows: List[Dict[str, Any]] = []
    skipped = 0

    for bar in raw_bars:
        sym = str(bar.get("symbol", "")).upper()
        if sym not in tracked_set:
            continue

        date_str = bar.get("date")
        if not date_str:
            skipped += 1
            continue

        try:
            pd_date = pd.Timestamp(date_str).to_pydatetime()
            if pd_date.tzinfo is not None:
                pd_date = pd_date.replace(tzinfo=None)
        except Exception:
            skipped += 1
            continue

        raw_close = bar.get("close")
        adj_close = bar.get("adjClose")
        close_val = raw_close if raw_close is not None else adj_close
        if close_val is None:
            skipped += 1
            continue
        try:
            close_val = float(close_val)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if close_val <= 0 or math.isnan(close_val) or math.isinf(close_val):
            skipped += 1
            continue

        def _safe_float(v, fallback):
            if v is None:
                return fallback
            try:
                f = float(v)
                return fallback if (math.isnan(f) or math.isinf(f)) else f
            except (TypeError, ValueError):
                return fallback

        open_val = _safe_float(bar.get("open"), close_val)
        high_val = _safe_float(bar.get("high"), close_val)
        low_val = _safe_float(bar.get("low"), close_val)
        volume = int(_safe_float(bar.get("volume"), 0))
        adj = _safe_float(adj_close, close_val)

        synthetic = (
            open_val == close_val and bar.get("open") is None
            or high_val == close_val and bar.get("high") is None
            or low_val == close_val and bar.get("low") is None
        )

        if high_val < low_val:
            high_val, low_val = low_val, high_val

        rows.append({
            "symbol": sym,
            "date": pd_date,
            "open_price": open_val,
            "high_price": high_val,
            "low_price": low_val,
            "close_price": close_val,
            "adjusted_close": adj,
            "volume": volume,
            "interval": "1d",
            "data_source": "fmp_bulk_eod",
            "is_adjusted": True,
            "is_synthetic_ohlc": synthetic,
        })

    if skipped:
        logger.debug("bulk_eod: skipped %d bars during validation", skipped)
    return rows


def _persist_bulk_rows(session: Session, rows: List[Dict[str, Any]]) -> int:
    """Persist validated bulk EOD rows via single INSERT...ON CONFLICT."""
    if not rows:
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import or_
    from backend.models import PriceData

    stmt = pg_insert(PriceData).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_symbol_date_interval",
        set_={
            "open_price": stmt.excluded.open_price,
            "high_price": stmt.excluded.high_price,
            "low_price": stmt.excluded.low_price,
            "close_price": stmt.excluded.close_price,
            "adjusted_close": stmt.excluded.adjusted_close,
            "volume": stmt.excluded.volume,
            "data_source": stmt.excluded.data_source,
            "is_synthetic_ohlc": stmt.excluded.is_synthetic_ohlc,
            "is_adjusted": stmt.excluded.is_adjusted,
        },
        where=or_(
            PriceData.data_source.is_(None),
            PriceData.data_source.in_(["provider", "fmp_td_yf", "fmp_bulk_eod", "fmp"]),
        ),
    )
    session.execute(stmt)
    session.commit()
    return len(rows)


def _last_n_trading_dates(n: int = 5) -> List[str]:
    """Return the last N completed trading session dates as YYYY-MM-DD strings."""
    try:
        import exchange_calendars as xcals
        from zoneinfo import ZoneInfo

        nyse = xcals.get_calendar("XNYS")
        today = pd.Timestamp.now(tz="UTC").normalize()
        schedule = nyse.sessions_in_range(today - pd.Timedelta(days=30), today)

        et_now = datetime.now(ZoneInfo("America/New_York"))
        if et_now.hour < 16:
            closed = schedule[schedule < today]
        else:
            closed = schedule[schedule <= today]

        dates = [d.strftime("%Y-%m-%d") for d in closed[-n:]]
        return dates
    except Exception as e:
        logger.warning("_last_n_trading_dates failed, using calendar day fallback: %s", e)
        today = datetime.now(timezone.utc).date()
        return [(today - timedelta(days=i)).isoformat() for i in range(1, n + 1)]


def _find_missing_dates(session: Session, tracked: List[str], lookback: int = 5) -> List[str]:
    """Find recent trading dates where coverage is below threshold."""
    from sqlalchemy import func, distinct
    from backend.models import PriceData

    dates = _last_n_trading_dates(lookback)
    tracked_set = set(s.upper() for s in tracked)
    threshold = len(tracked_set) * 0.95
    missing = []

    for date_str in dates:
        try:
            dt = pd.Timestamp(date_str).to_pydatetime()
            count = (
                session.query(func.count(distinct(PriceData.symbol)))
                .filter(
                    PriceData.interval == "1d",
                    PriceData.symbol.in_(tracked_set),
                    func.date(PriceData.date) == dt.date(),
                )
                .scalar()
            ) or 0
            if count < threshold:
                missing.append(date_str)
        except Exception as e:
            logger.warning("_find_missing_dates check failed for %s: %s", date_str, e)
            missing.append(date_str)

    return missing


@shared_task(
    soft_time_limit=300,
    time_limit=360,
)
@task_run("admin_bulk_daily_fill", lock_key=lambda date=None, **_: f"bulk_daily_fill:{date or 'latest'}")
def bulk_daily_fill(date: Optional[str] = None) -> dict:
    """Fetch bulk EOD bars for a single date and persist for tracked universe.

    If date is None, fills the most recent completed trading session.
    """
    _set_task_status("admin_bulk_daily_fill", "running", {"date": date})
    t0 = time.monotonic()

    if not settings.FMP_API_KEY:
        return {"status": "skipped", "reason": "FMP_API_KEY not configured"}

    if date is None:
        dates = _last_n_trading_dates(1)
        if not dates:
            return {"status": "error", "error": "Could not determine latest trading date"}
        date = dates[-1]

    session = SessionLocal()
    try:
        tracked = _get_tracked_symbols_safe(session)
        tracked_set = set(s.upper() for s in tracked)

        if not tracked_set:
            return {"status": "error", "error": "No tracked symbols"}

        try:
            raw_bars = _fetch_bulk_eod_for_date(date)
        except BulkEndpointUnavailable:
            logger.warning("Bulk EOD requires paid FMP plan (got 402)")
            return {
                "status": "error",
                "error": "FMP bulk EOD requires a paid plan. "
                         "Set MARKET_PROVIDER_POLICY=paid and use a paid FMP_API_KEY.",
                "date": date,
                "tracked_total": len(tracked_set),
            }

        rows = _validate_and_build_rows(raw_bars, tracked_set)
        persisted = _persist_bulk_rows(session, rows)

        elapsed = time.monotonic() - t0
        res = {
            "status": "ok",
            "date": date,
            "tracked_total": len(tracked_set),
            "api_bars_returned": len(raw_bars),
            "matched_tracked": len(rows),
            "persisted": persisted,
            "elapsed_s": round(elapsed, 2),
            "api_calls": 1,
        }
        logger.info(
            "bulk_daily_fill: date=%s tracked=%d matched=%d persisted=%d in %.1fs",
            date, len(tracked_set), len(rows), persisted, elapsed,
        )
        _set_task_status("admin_bulk_daily_fill", "ok", res)
        return res
    except SoftTimeLimitExceeded:
        logger.warning("bulk_daily_fill hit soft time limit for date=%s", date)
        raise
    except Exception as e:
        logger.exception("bulk_daily_fill failed for date=%s: %s", date, e)
        return {"status": "error", "date": date, "error": str(e)}
    finally:
        session.close()


@shared_task(
    soft_time_limit=1800,
    time_limit=2100,
)
@task_run("admin_bulk_stale_recovery", lock_key=lambda: "admin_bulk_stale_recovery")
def bulk_stale_recovery(lookback_days: int = 5) -> dict:
    """Find recent trading dates with incomplete coverage and bulk-fill them.

    Much more efficient than per-symbol stale_daily: instead of 2300 API calls
    per missing date, this makes 1 call per missing date.
    """
    _set_task_status("admin_bulk_stale_recovery", "running")
    t0 = time.monotonic()

    if not settings.FMP_API_KEY:
        return {"status": "skipped", "reason": "FMP_API_KEY not configured"}

    session = SessionLocal()
    try:
        tracked = _get_tracked_symbols_safe(session)
        if not tracked:
            return {"status": "error", "error": "No tracked symbols"}

        missing_dates = _find_missing_dates(session, tracked, lookback=lookback_days)

        if not missing_dates:
            res = {
                "status": "ok",
                "tracked_total": len(tracked),
                "missing_dates": 0,
                "note": "All recent trading dates have adequate coverage",
            }
            _set_task_status("admin_bulk_stale_recovery", "ok", res)
            return res

        fills = []
        for date_str in missing_dates:
            try:
                fill_res = bulk_daily_fill(date=date_str)
                fills.append(fill_res)
            except SoftTimeLimitExceeded:
                raise
            except Exception as e:
                logger.warning("bulk_stale_recovery: fill failed for %s: %s", date_str, e)
                fills.append({"status": "error", "date": date_str, "error": str(e)})

        from backend.tasks.market.coverage import health_check
        try:
            health_check()
        except Exception as e:
            logger.warning("bulk_stale_recovery: post-fill health_check failed: %s", e)

        elapsed = time.monotonic() - t0
        total_persisted = sum(f.get("persisted", 0) for f in fills)
        errors = sum(1 for f in fills if f.get("status") == "error")
        res = {
            "status": "ok" if errors == 0 else "partial",
            "tracked_total": len(tracked),
            "missing_dates": len(missing_dates),
            "dates_filled": missing_dates,
            "total_persisted": total_persisted,
            "errors": errors,
            "api_calls": len(missing_dates),
            "elapsed_s": round(elapsed, 2),
            "fills": fills,
        }
        _set_task_status("admin_bulk_stale_recovery", res["status"], res)
        return res
    except SoftTimeLimitExceeded:
        logger.warning("bulk_stale_recovery hit soft time limit")
        raise
    finally:
        session.close()
