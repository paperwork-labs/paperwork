from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class JobTemplate:
    id: str
    display_name: str
    group: str  # market_data | accounts | maintenance
    task: str
    description: str
    default_cron: str  # standard 5-field cron
    default_tz: str  # e.g., UTC
    args: List[Any] | None = None
    kwargs: Dict[str, Any] | None = None
    singleflight: bool = True
    max_concurrency: int = 1
    timeout_s: int = 3600
    retries: int = 0
    backoff_s: int = 0
    maintenance_windows: List[Dict[str, str]] | None = None
    queue: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


CATALOG: List[JobTemplate] = [
    # ── Accounts ──────────────────────────────────────────────────
    JobTemplate(
        id="ibkr-daily-flex-sync",
        display_name="IBKR Flex Sync",
        group="accounts",
        task="backend.tasks.account_sync.sync_all_ibkr_accounts",
        description="Daily FlexQuery sync for all linked IBKR accounts",
        default_cron="15 2 * * *",
        default_tz="UTC",
        queue="account_sync",
    ),
    # ── Market Data (nightly pipeline, ordered by run time) ──────
    JobTemplate(
        id="market_indices_constituents_refresh",
        display_name="Index Constituents",
        group="market_data",
        task="backend.tasks.market_data_tasks.refresh_index_constituents",
        description="Refresh S&P 500, NASDAQ-100, and Dow 30 member lists",
        default_cron="0 2 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="market_universe_tracked_refresh",
        display_name="Tracked Symbols",
        group="market_data",
        task="backend.tasks.market_data_tasks.update_tracked_symbol_cache",
        description="Recompute the union of all tracked symbols and publish changes",
        default_cron="30 2 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_market_data_audit",
        display_name="Data Quality Audit",
        group="market_data",
        task="backend.tasks.market_data_tasks.audit_market_data_quality",
        description="Check daily bars and snapshot completeness for the tracked universe",
        default_cron="45 2 * * *",
        default_tz="UTC",
        kwargs={"sample_limit": 25},
    ),
    JobTemplate(
        id="admin_coverage_backfill",
        display_name="Nightly Coverage Pipeline",
        group="market_data",
        task="backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked",
        description="Full nightly chain: constituents, tracked, daily bars, indicators, snapshot history, coverage",
        default_cron="0 3 * * *",
        default_tz="UTC",
        kwargs={"history_days": 20, "history_batch_size": 25},
    ),
    JobTemplate(
        id="admin_snapshots_history_record",
        display_name="Daily Snapshot Archive",
        group="market_data",
        task="backend.tasks.market_data_tasks.record_daily_history",
        description="Archive today's market snapshot to immutable history",
        default_cron="20 3 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_indicators_recompute_universe",
        display_name="Indicator Recompute",
        group="market_data",
        task="backend.tasks.market_data_tasks.recompute_indicators_universe",
        description="Recompute Weinstein stage, RS, and ATR indicators for all tracked symbols",
        default_cron="35 3 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_backfill_5m",
        display_name="Intraday Bars (D-1)",
        group="market_data",
        task="backend.tasks.market_data_tasks.backfill_5m_last_n_days",
        description="Backfill 5-minute bars for the previous trading day",
        default_cron="10 4 * * *",
        default_tz="UTC",
        kwargs={"n_days": 1, "batch_size": 50},
    ),
    JobTemplate(
        id="admin_coverage_refresh",
        display_name="Coverage Health Check",
        group="market_data",
        task="backend.tasks.market_data_tasks.monitor_coverage_health",
        description="Measure data freshness and flag stale symbols",
        default_cron="0 * * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="market_snapshots_fundamentals_fill",
        display_name="Fill Missing Snapshot Data",
        group="market_data",
        task="backend.tasks.market_data_tasks.fill_missing_snapshot_fundamentals",
        description="Backfill missing name, sector, industry, PE, EPS, revenue growth, etc. on tracked snapshots",
        default_cron="45 4 * * *",
        default_tz="UTC",
    ),
    # ── Maintenance ───────────────────────────────────────────────
    JobTemplate(
        id="admin_retention_enforce",
        display_name="Data Retention Cleanup",
        group="maintenance",
        task="backend.tasks.market_data_tasks.enforce_price_data_retention",
        description="Purge 5-minute bars older than the configured retention window",
        default_cron="30 4 * * *",
        default_tz="UTC",
        kwargs={"max_days_5m": 90},
    ),
]
