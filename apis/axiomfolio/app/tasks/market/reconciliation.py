"""OHLCV Spot-Check Reconciliation — weekly data accuracy verification.

Compares a sample of price_data rows against yfinance as a reference source.
Results are cached in Redis and consumed by the data_accuracy health dimension.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List

from celery import shared_task
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)

INDEX_ETFS = ["SPY", "QQQ", "DIA", "IWM"]
SAMPLE_SIZE = 50
MISMATCH_THRESHOLD_PCT = 0.5
RECONCILIATION_BARS = 5
REDIS_KEY = "ohlcv:reconciliation:last"
REDIS_TTL = 86400 * 10  # 10 days


def _fetch_yfinance_bars(symbol: str, bars: int = 5) -> list:
    """Fetch recent daily bars from yfinance as reference data."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo", interval="1d")
        if df is None or df.empty:
            return []
        df = df.sort_index(ascending=False).head(bars)
        result = []
        for ts, row in df.iterrows():
            result.append({
                "date": ts.strftime("%Y-%m-%d"),
                "close": float(row.get("Close", 0)),
                "open": float(row.get("Open", 0)),
                "high": float(row.get("High", 0)),
                "low": float(row.get("Low", 0)),
                "volume": int(row.get("Volume", 0)),
            })
        return result
    except Exception as exc:
        logger.warning("yfinance fetch for %s failed: %s", symbol, exc)
        return []


def _get_db_bars(db: Session, symbol: str, dates: list) -> dict:
    """Get price_data rows for specific dates."""
    from app.models import PriceData
    from sqlalchemy import func

    result = {}
    for date_str in dates:
        row = (
            db.query(PriceData)
            .filter(
                PriceData.symbol == symbol,
                PriceData.interval == "1d",
                func.date(PriceData.date) == date_str,
            )
            .first()
        )
        if row:
            result[date_str] = {
                "close": float(row.close_price),
                "open": float(row.open_price) if row.open_price else 0,
                "high": float(row.high_price) if row.high_price else 0,
                "low": float(row.low_price) if row.low_price else 0,
                "volume": int(row.volume) if row.volume else 0,
                "data_source": row.data_source,
            }
    return result


def run_reconciliation(db: Session) -> Dict[str, Any]:
    """Run spot-check reconciliation against yfinance reference data."""
    from app.tasks.utils.task_utils import get_tracked_symbols_safe

    tracked = get_tracked_symbols_safe(db)
    if not tracked:
        return {"status": "error", "error": "no tracked symbols"}

    sample_set = set(INDEX_ETFS)
    non_etf = [s for s in tracked if s not in sample_set]
    sample_count = min(SAMPLE_SIZE, len(non_etf))
    sample_set.update(random.sample(non_etf, sample_count))
    sample = sorted(sample_set)

    mismatches: List[Dict[str, Any]] = []
    checked = 0
    matched = 0
    missing_in_db = 0
    errors = 0

    for symbol in sample:
        try:
            ref_bars = _fetch_yfinance_bars(symbol, RECONCILIATION_BARS)
            if not ref_bars:
                errors += 1
                continue

            dates = [b["date"] for b in ref_bars]
            db_bars = _get_db_bars(db, symbol, dates)

            for ref in ref_bars:
                checked += 1
                date_str = ref["date"]
                db_bar = db_bars.get(date_str)

                if not db_bar:
                    missing_in_db += 1
                    mismatches.append({
                        "symbol": symbol,
                        "date": date_str,
                        "type": "missing_in_db",
                        "ref_close": ref["close"],
                    })
                    continue

                if ref["close"] > 0 and db_bar["close"] > 0:
                    pct_diff = abs(ref["close"] - db_bar["close"]) / ref["close"] * 100
                    if pct_diff > MISMATCH_THRESHOLD_PCT:
                        mismatches.append({
                            "symbol": symbol,
                            "date": date_str,
                            "type": "close_divergence",
                            "ref_close": round(ref["close"], 4),
                            "db_close": round(db_bar["close"], 4),
                            "pct_diff": round(pct_diff, 2),
                            "data_source": db_bar.get("data_source"),
                        })
                    else:
                        matched += 1
                else:
                    matched += 1
        except Exception as exc:
            errors += 1
            logger.warning("reconciliation check for %s failed: %s", symbol, exc)

    result = {
        "status": "ok" if not mismatches else "warning",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(sample),
        "bars_checked": checked,
        "bars_matched": matched,
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
        "missing_in_db": missing_in_db,
        "errors": errors,
        "match_rate": round((matched / max(checked, 1)) * 100, 1),
    }

    try:
        from app.services.market.market_data_service import infra

        r = infra.redis_client
        r.setex(REDIS_KEY, REDIS_TTL, json.dumps(result))
    except Exception as exc:
        logger.warning("reconciliation redis cache failed: %s", exc)

    return result


@shared_task(
    name="app.tasks.market.reconciliation.spot_check",
    soft_time_limit=600,
    time_limit=720,
)
@task_run("ohlcv_reconciliation")
def spot_check() -> dict:
    """Weekly OHLCV spot-check reconciliation task."""
    db = SessionLocal()
    try:
        return run_reconciliation(db)
    finally:
        db.close()
