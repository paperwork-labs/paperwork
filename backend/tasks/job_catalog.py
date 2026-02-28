from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class JobTemplate:
    id: str
    display_name: str
    group: str  # market_data | portfolio | maintenance
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
    # ── Portfolio ──────────────────────────────────────────────────
    JobTemplate(
        id="ibkr-daily-flex-sync",
        display_name="IBKR Daily Sync",
        group="portfolio",
        task="backend.tasks.account_sync.sync_all_ibkr_accounts",
        description="Sync all enabled IBKR accounts daily via FlexQuery",
        default_cron="15 2 * * *",
        default_tz="UTC",
        queue="account_sync",
    ),
    JobTemplate(
        id="schwab-daily-sync",
        display_name="Schwab Daily Sync",
        group="portfolio",
        task="backend.tasks.account_sync.sync_all_schwab_accounts",
        description="Sync all enabled Schwab accounts (positions, transactions, balances)",
        default_cron="30 2 * * *",
        default_tz="UTC",
        queue="account_sync",
    ),
    JobTemplate(
        id="stale-sync-recovery",
        display_name="Stale Sync Recovery",
        group="portfolio",
        task="backend.tasks.account_sync.recover_stale_syncs",
        description="Auto-reset accounts stuck in RUNNING state for >10 minutes",
        default_cron="*/5 * * * *",
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
        default_cron="0 1 * * *",
        default_tz="UTC",
        kwargs={"history_days": 20, "history_batch_size": 25},
    ),
    JobTemplate(
        id="admin_snapshots_history_record",
        display_name="Daily Snapshot Archive",
        group="market_data",
        task="backend.tasks.market_data_tasks.record_daily_history",
        description="Archive today's market snapshot to immutable history",
        default_cron="20 1 * * *",
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
    JobTemplate(
        id="market_snapshots_fundamentals_refresh",
        display_name="Refresh Stale Fundamentals",
        group="market_data",
        task="backend.tasks.market_data_tasks.refresh_stale_fundamentals",
        description="Re-fetch EPS, PE, and other fundamentals for snapshots older than 7 days",
        default_cron="0 4 * * 0",
        default_tz="UTC",
    ),
    JobTemplate(
        id="backfill_position_metadata",
        display_name="Backfill Position Metadata",
        group="market_data",
        task="backend.tasks.market_data_tasks.backfill_position_metadata",
        description="Fill NULL sector/market_cap on open positions from MarketSnapshot",
        default_cron="30 1 * * *",
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
    JobTemplate(
        id="admin_recover_stale_job_runs",
        display_name="Recover Stale Job Runs",
        group="maintenance",
        task="backend.tasks.market_data_tasks.recover_stale_job_runs",
        description="Mark job runs stuck in RUNNING (e.g. cron timeout, worker restart) as cancelled so jobs list and health go green",
        default_cron="0 */6 * * *",
        default_tz="UTC",
        kwargs={"stale_minutes": 120},
    ),
]
