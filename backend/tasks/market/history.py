"""
Snapshot History Tasks
======================

Celery tasks for recording and managing MarketSnapshotHistory.
"""

import logging
from typing import List, Optional
from celery import shared_task

from backend.database import SessionLocal
from backend.tasks.task_utils import task_run

logger = logging.getLogger(__name__)


@shared_task(
    name="backend.tasks.market.history.record_daily_history",
    soft_time_limit=300,
    time_limit=600,
)
@task_run("record_daily_history")
def record_daily_history(symbols: Optional[List[str]] = None) -> dict:
    """Record today's snapshot values to MarketSnapshotHistory.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.record_daily_history
    """
    from backend.tasks.market_data_tasks import record_daily_history as _record
    return _record(symbols)


@shared_task(
    name="backend.tasks.market.history.backfill_snapshot_history_last_n_days",
    soft_time_limit=3600,
    time_limit=4200,
)
@task_run("backfill_snapshot_history_last_n_days")
def backfill_snapshot_history_last_n_days(
    n_days: int = 90,
    batch_size: int = 50,
    skip_already_present: bool = True,
) -> dict:
    """Backfill snapshot history for the last N days.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.backfill_snapshot_history_last_n_days
    """
    from backend.tasks.market_data_tasks import backfill_snapshot_history_last_n_days as _backfill
    return _backfill(n_days, batch_size, skip_already_present)


@shared_task(
    name="backend.tasks.market.history.backfill_snapshot_history_for_symbol",
    soft_time_limit=600,
    time_limit=900,
)
@task_run("backfill_snapshot_history_for_symbol")
def backfill_snapshot_history_for_symbol(
    symbol: str,
    n_days: int = 365,
    skip_already_present: bool = True,
) -> dict:
    """Backfill snapshot history for a specific symbol.

    This is the modular version. The original is still available at
    backend.tasks.market_data_tasks.backfill_snapshot_history_for_symbol
    """
    from backend.tasks.market_data_tasks import backfill_snapshot_history_for_symbol as _backfill
    return _backfill(symbol, n_days, skip_already_present)
