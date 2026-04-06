"""
Implied volatility snapshot and IV rank maintenance tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta as td, timezone

from celery import shared_task

from backend.database import SessionLocal
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    soft_time_limit=300,
    time_limit=360,
)
@task_run("snapshot_iv_from_gateway")
def sync_gateway() -> dict:
    """Snapshot implied volatility for tracked positions from IB Gateway.

    Requires IB Gateway connection. Fetches ATM IV for positions and stores
    in HistoricalIV table for IV rank calculation.
    """
    logger.info(
        "snapshot_iv_from_gateway (sync_gateway): IV gateway sync not yet implemented; skipping work"
    )
    return {"status": "noop", "reason": "IV gateway sync not yet implemented"}


@shared_task(
    soft_time_limit=120,
    time_limit=180,
)
@task_run("compute_iv_rank")
def compute_rank(lookback_days: int = 252) -> dict:
    """Compute IV Rank/Percentile for symbols with historical IV data.

    IV Rank = (Current IV - 52w Low) / (52w High - 52w Low) * 100
    """
    session = SessionLocal()
    try:
        from backend.models.historical_iv import HistoricalIV

        today = datetime.now(timezone.utc).date()
        cutoff = today - td(days=lookback_days)
        updated = 0

        symbols = (
            session.query(HistoricalIV.symbol)
            .filter(HistoricalIV.date >= cutoff)
            .distinct()
            .all()
        )

        for (symbol,) in symbols:
            iv_rows = (
                session.query(HistoricalIV.iv_30d, HistoricalIV.date)
                .filter(
                    HistoricalIV.symbol == symbol,
                    HistoricalIV.date >= cutoff,
                    HistoricalIV.iv_30d.isnot(None),
                )
                .order_by(HistoricalIV.date.asc())
                .all()
            )

            if len(iv_rows) < 20:
                continue

            ivs = [r.iv_30d for r in iv_rows if r.iv_30d is not None]
            if not ivs:
                continue

            iv_high = max(ivs)
            iv_low = min(ivs)
            current_iv = ivs[-1]

            if iv_high > iv_low:
                iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
            else:
                iv_rank = 50.0

            latest = (
                session.query(HistoricalIV)
                .filter(HistoricalIV.symbol == symbol)
                .order_by(HistoricalIV.date.desc())
                .first()
            )

            if latest:
                latest.iv_rank_252 = round(iv_rank, 2)
                latest.iv_high_252 = iv_high
                latest.iv_low_252 = iv_low
                if len(ivs) >= 2:
                    latest.iv_hv_spread = current_iv - (latest.hv_20d or 0)
                updated += 1

        session.commit()
        return {
            "status": "ok",
            "symbols_processed": len(symbols),
            "updated": updated,
        }
    except Exception:
        logger.exception("compute_rank failed")
        raise
    finally:
        session.close()
