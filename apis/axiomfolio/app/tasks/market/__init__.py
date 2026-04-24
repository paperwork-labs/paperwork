"""
Market-domain Celery tasks.

Celery registers each task as ``app.tasks.market.<module>.<function>``.
"""

from app.tasks.market.backfill import (
    constituents,
    daily_bars,
    daily_since,
    full_historical,
    stale_daily,
    symbol,
    symbols,
    tracked_cache,
)
from app.tasks.market.conviction import generate_conviction_picks
from app.tasks.market.coverage import (
    daily_bootstrap,
    health_check,
)
from app.tasks.market.fundamentals import (
    enrich_index,
    fill_missing,
    refresh_stale,
)
from app.tasks.market.history import (
    record_daily,
    snapshot_for_date,
    snapshot_for_symbol,
    snapshot_last_n_days,
)
from app.tasks.market.indicators import (
    position_metadata,
    recompute_universe,
    stage_changes,
    stage_durations,
)
from app.tasks.market.institutional import sync_13f
from app.tasks.market.intraday import bars_5m_last_n_days, bars_5m_symbols
from app.tasks.market.iv import compute_rank, sync_gateway
from app.tasks.market.maintenance import (
    STALE_JOB_RUN_MINUTES,
    audit_quality,
    prune_old_bars,
    recover_jobs,
    recover_jobs_impl,
)
from app.tasks.market.regime import compute_daily, vix_alert
from app.tasks.market.regime_alerts import check_regime_alerts

__all__ = [
    "STALE_JOB_RUN_MINUTES",
    "audit_quality",
    "bars_5m_last_n_days",
    "bars_5m_symbols",
    "check_regime_alerts",
    "compute_daily",
    "compute_rank",
    "constituents",
    "daily_bars",
    "daily_bootstrap",
    "daily_since",
    "enrich_index",
    "fill_missing",
    "full_historical",
    "generate_conviction_picks",
    "health_check",
    "position_metadata",
    "prune_old_bars",
    "recompute_universe",
    "record_daily",
    "recover_jobs",
    "recover_jobs_impl",
    "refresh_stale",
    "snapshot_for_date",
    "snapshot_for_symbol",
    "snapshot_last_n_days",
    "stage_changes",
    "stage_durations",
    "stale_daily",
    "symbol",
    "symbols",
    "sync_13f",
    "sync_gateway",
    "tracked_cache",
    "vix_alert",
]
