"""
Backfill Tasks
==============

Celery tasks for daily bar and historical data backfill.
"""

import logging
from typing import List
from celery import shared_task

from backend.database import SessionLocal
from backend.tasks.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    name="backend.tasks.market.backfill.backfill_symbols",
    soft_time_limit=1800,
    time_limit=2100,
)
@task_run("backfill_symbols")
def backfill_symbols(symbols: List[str], days: int = 200) -> dict:
    """Backfill daily bars for specified symbols.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.backfill_symbols
    """
    # Delegate to the original implementation
    from backend.tasks.market_data_tasks import backfill_symbols as _backfill
    return _backfill(symbols, days)


@shared_task(
    name="backend.tasks.market.backfill.backfill_last_bars",
    soft_time_limit=1800,
    time_limit=2100,
)
@task_run("backfill_last_bars")
def backfill_last_bars(days: int = 200) -> dict:
    """Backfill daily bars for the tracked universe.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.backfill_last_bars
    """
    from backend.tasks.market_data_tasks import backfill_last_bars as _backfill
    return _backfill(days)


@shared_task(
    name="backend.tasks.market.backfill.backfill_stale_daily_tracked",
    soft_time_limit=900,
    time_limit=1200,
)
@task_run("backfill_stale_daily_tracked")
def backfill_stale_daily_tracked() -> dict:
    """Backfill stale daily bars for tracked symbols missing recent data.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.backfill_stale_daily_tracked
    """
    from backend.tasks.market_data_tasks import backfill_stale_daily_tracked as _backfill
    return _backfill()
