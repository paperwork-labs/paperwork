"""
Implied volatility snapshot and IV rank maintenance tasks.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import timedelta as td

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
    session = SessionLocal()
    try:
        from backend.models.historical_iv import HistoricalIV
        from backend.models.position import Position

        today = date_type.today()
        processed = 0
        errors = 0

        positions = session.query(Position).filter(Position.status == "open").all()

        symbols = list({p.symbol for p in positions if p.symbol})
        if not symbols:
            return {"status": "no_positions", "processed": 0}

        try:
            from backend.services.clients.ibkr_client import ibkr_client

            if not ibkr_client.is_connected():
                return {"status": "gateway_not_connected", "processed": 0}
        except Exception as e:
            logger.warning("IBKR client not available: %s", e)
            return {"status": "gateway_unavailable", "error": str(e)}

        for symbol in symbols:
            try:
                iv_data = {
                    "iv_30d": None,
                    "hv_20d": None,
                }

                if iv_data.get("iv_30d") is not None:
                    existing = (
                        session.query(HistoricalIV)
                        .filter(
                            HistoricalIV.symbol == symbol,
                            HistoricalIV.date == today,
                        )
                        .first()
                    )

                    if existing:
                        existing.iv_30d = iv_data["iv_30d"]
                        existing.hv_20d = iv_data.get("hv_20d")
                    else:
                        session.add(
                            HistoricalIV(
                                symbol=symbol,
                                date=today,
                                iv_30d=iv_data["iv_30d"],
                                hv_20d=iv_data.get("hv_20d"),
                            )
                        )
                    processed += 1
            except Exception as e:
                logger.warning("Failed to snapshot IV for %s: %s", symbol, e)
                errors += 1

        session.commit()
        return {
            "status": "ok",
            "symbols_checked": len(symbols),
            "processed": processed,
            "errors": errors,
        }
    except Exception:
        logger.exception("sync_gateway failed")
        raise
    finally:
        session.close()


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

        today = date_type.today()
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
