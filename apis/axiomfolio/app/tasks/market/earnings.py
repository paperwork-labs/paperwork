"""Earnings calendar sync task.

Daily task that fetches upcoming earnings for tracked symbols using
FMP (premium) with yfinance fallback, and upserts into the
earnings_calendar table.
"""

import logging
from typing import Optional

from celery import shared_task

from app.database import SessionLocal
from app.services.market.earnings_calendar_service import earnings_calendar_service
from app.tasks.utils.task_utils import _get_tracked_symbols_safe, _set_task_status, task_run

logger = logging.getLogger(__name__)

_DEFAULT_SOFT = 600
_DEFAULT_HARD = 660


@shared_task(
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
)
@task_run("sync_earnings_calendar")
def sync_earnings_calendar(lookback_days: int = 7, lookahead_days: int = 90) -> dict:
    """Sync upcoming earnings for all tracked symbols.

    Args:
        lookback_days: days in the past to capture recent actuals.
        lookahead_days: days ahead to capture upcoming estimates.

    Returns:
        Counters dict for JobRun persistence.
    """
    from datetime import datetime, timedelta, timezone

    _set_task_status("sync_earnings_calendar", "running")
    session = SessionLocal()
    try:
        symbols = _get_tracked_symbols_safe(session)
        if not symbols:
            logger.warning("sync_earnings_calendar: no tracked symbols found")
            return {"status": "ok", "symbols": 0, "fetched": 0, "upserted": 0}

        today = datetime.now(timezone.utc).date()
        from_date = today - timedelta(days=lookback_days)
        to_date = today + timedelta(days=lookahead_days)

        result = earnings_calendar_service.sync_earnings(
            db=session,
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
        )
        logger.info(
            "sync_earnings_calendar done: source=%s fetched=%d upserted=%d errors=%d",
            result["source"], result["fetched"], result["upserted"], result["errors"],
        )
        return {
            "status": "ok",
            "symbols": len(symbols),
            **result,
        }
    except Exception as exc:
        logger.exception("sync_earnings_calendar failed: %s", exc)
        raise
    finally:
        session.close()
