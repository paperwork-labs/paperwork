"""
Market-domain Celery tasks.

Celery registers each task as ``backend.tasks.market.<module>.<function>``.
"""

from backend.tasks.market.backfill import (
    constituents,
    daily_bars,
    daily_since,
    full_historical,
    stale_daily,
    symbol,
    symbols,
    tracked_cache,
)
from backend.tasks.market.coverage import (
    daily_bootstrap,
    health_check,
)
from backend.tasks.market.fundamentals import (
    enrich_index,
    fill_missing,
    refresh_stale,
)
from backend.tasks.market.history import (
    record_daily,
    snapshot_for_date,
    snapshot_for_symbol,
    snapshot_last_n_days,
)
from backend.tasks.market.indicators import (
    position_metadata,
    stage_durations,
    stage_changes,
    recompute_universe,
)
from backend.tasks.market.institutional import sync_13f
from backend.tasks.market.intraday import bars_5m_last_n_days, bars_5m_symbols
from backend.tasks.market.iv import compute_rank, sync_gateway
from backend.tasks.market.maintenance import (
    STALE_JOB_RUN_MINUTES,
    audit_quality,
    prune_old_bars,
    recover_jobs,
    recover_jobs_impl,
)
from backend.tasks.market.regime import compute_daily, vix_alert

__all__ = [
    "STALE_JOB_RUN_MINUTES",
    "audit_quality",
    "bars_5m_last_n_days",
    "bars_5m_symbols",
    "constituents",
    "daily_bars",
    "daily_since",
    "position_metadata",
    "full_historical",
    "snapshot_for_date",
    "snapshot_for_symbol",
    "snapshot_last_n_days",
    "stage_durations",
    "stale_daily",
    "symbol",
    "symbols",
    "daily_bootstrap",
    "stage_changes",
    "compute_daily",
    "compute_rank",
    "enrich_index",
    "fill_missing",
    "health_check",
    "prune_old_bars",
    "record_daily",
    "recover_jobs",
    "recover_jobs_impl",
    "refresh_stale",
    "recompute_universe",
    "sync_13f",
    "sync_gateway",
    "vix_alert",
    "tracked_cache",
]
