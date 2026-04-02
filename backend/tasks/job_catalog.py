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
    job_run_label: Optional[str] = None  # @task_run() label for JobRun lookup
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
        id="recover-stale-syncs",
        display_name="Recover Stale Syncs",
        group="portfolio",
        task="backend.tasks.account_sync.recover_stale_syncs",
        description="Reset broker accounts stuck in RUNNING state for > 10 min",
        default_cron="*/5 * * * *",
        default_tz="UTC",
        queue="account_sync",
        timeout_s=120,
    ),
    # ── Market Data ────────────────────────────────────────────────
    # THE nightly pipeline: constituents, tracked, bars, indicators, history, regime, coverage
    JobTemplate(
        id="admin_coverage_backfill",
        display_name="Nightly Coverage Pipeline",
        group="market_data",
        task="backend.tasks.market.coverage.daily_bootstrap",
        description="Full nightly chain: constituents, tracked, daily bars, indicators, snapshot history, regime, coverage",
        default_cron="0 1 * * *",
        default_tz="UTC",
        job_run_label="admin_coverage_backfill",
        kwargs={"history_days": 20, "history_batch_size": 25},
    ),
    JobTemplate(
        id="fundamentals_fill",
        display_name="Market Snapshots Fundamentals Fill",
        group="market_data",
        task="backend.tasks.market.fundamentals.fill_missing",
        description="Backfill missing fundamentals on MarketSnapshot rows after nightly indicator recompute",
        default_cron="15 3 * * *",
        default_tz="UTC",
        job_run_label="market_snapshots_fundamentals_fill",
        timeout_s=3600,
    ),
    JobTemplate(
        id="check_regime_alerts",
        display_name="Regime Alert Monitor",
        group="market_data",
        task="market.check_regime_alerts",
        description="VIX spike and regime-shift checks using latest MarketRegime row; schedule every 5 min during RTH",
        default_cron="*/5 9-16 * * 1-5",
        default_tz="America/New_York",
        job_run_label="check_regime_alerts",
        timeout_s=60,
    ),
    # ── Orders ─────────────────────────────────────────────────────
    JobTemplate(
        id="monitor-open-orders",
        display_name="Monitor Open Orders",
        group="portfolio",
        task="backend.tasks.portfolio.orders.monitor_open_orders_task",
        description="Poll broker for status updates on submitted/partially-filled orders and flag stale entries",
        default_cron="* * * * *",
        default_tz="UTC",
        queue="orders",
    ),
    JobTemplate(
        id="ibkr-gateway-watchdog",
        display_name="IBKR Gateway Watchdog",
        group="portfolio",
        task="backend.tasks.ibkr_watchdog.ping_ibkr_connection",
        description="Health-check IB Gateway connection; reconnect and alert on repeated failure",
        default_cron="*/5 * * * *",
        default_tz="UTC",
        queue="orders",
    ),
    JobTemplate(
        id="reconcile-order-fills",
        display_name="Reconcile Order Fills",
        group="portfolio",
        task="backend.tasks.reconciliation_tasks.reconcile_orders",
        description="Match filled orders to trades and update position/P&L attribution",
        default_cron="*/10 * * * *",
        default_tz="UTC",
        queue="orders",
    ),
    # ── Strategy ────────────────────────────────────────────────────
    JobTemplate(
        id="evaluate-strategy-entries",
        display_name="Evaluate Strategy Entry Rules",
        group="strategy",
        task="backend.tasks.strategy_tasks.evaluate_strategies_task",
        description="Evaluate entry rules for all active strategies against latest snapshots",
        default_cron="0 2 * * 1-5",
        default_tz="America/New_York",
        timeout_s=660,
    ),
    JobTemplate(
        id="evaluate-exit-cascade",
        display_name="Evaluate Exit Cascade",
        group="strategy",
        task="backend.tasks.strategy.exit_evaluation.evaluate_exits_task",
        description="Evaluate 9-tier exit cascade for open positions — stop loss, trailing, stage, regime, time",
        default_cron="30 2 * * 1-5",
        default_tz="America/New_York",
        timeout_s=660,
    ),
    JobTemplate(
        id="sweep-stale-approvals",
        display_name="Sweep Stale Trade Approvals",
        group="portfolio",
        task="backend.tasks.portfolio.orders.sweep_stale_approvals",
        description="Auto-reject orders stuck in PENDING_APPROVAL beyond timeout",
        default_cron="*/5 * * * *",
        default_tz="UTC",
        timeout_s=30,
        queue="orders",
    ),
    # ── Maintenance ───────────────────────────────────────────────
    JobTemplate(
        id="admin_retention_enforce",
        display_name="Data Retention Cleanup",
        group="maintenance",
        task="backend.tasks.market.maintenance.prune_old_bars",
        description="Purge 5-minute bars older than the configured retention window",
        default_cron="30 4 * * *",
        default_tz="UTC",
        job_run_label="admin_retention_enforce",
        kwargs={"max_days_5m": 90},
    ),
    JobTemplate(
        id="admin_recover_stale_job_runs",
        display_name="Recover Stale Job Runs",
        group="maintenance",
        task="backend.tasks.market.maintenance.recover_jobs",
        description="Mark job runs stuck in RUNNING (e.g. cron timeout, worker restart) as cancelled so jobs list and health go green",
        default_cron="0 */6 * * *",
        default_tz="UTC",
        job_run_label="admin_recover_stale_job_runs",
        kwargs={"stale_minutes": 120},
    ),

    # ── Intelligence Briefs ──

    JobTemplate(
        id="generate_daily_digest",
        display_name="Daily Intelligence Digest",
        group="intelligence",
        task="backend.tasks.intelligence_tasks.generate_daily_digest",
        description="Generate daily intelligence brief after nightly pipeline — regime, transitions, breadth, exit alerts",
        default_cron="30 1 * * 1-5",
        default_tz="America/New_York",
        job_run_label="intelligence_daily_digest",
    ),
    JobTemplate(
        id="generate_weekly_brief",
        display_name="Weekly Strategy Brief",
        group="intelligence",
        task="backend.tasks.intelligence_tasks.generate_weekly_brief",
        description="Generate weekly strategy brief — regime trend, top picks, sector rotation, portfolio review",
        default_cron="0 7 * * 1",
        default_tz="America/New_York",
        job_run_label="intelligence_weekly_brief",
    ),
    JobTemplate(
        id="generate_monthly_review",
        display_name="Monthly Review",
        group="intelligence",
        task="backend.tasks.intelligence_tasks.generate_monthly_review",
        description="Generate monthly performance review — regime transitions, performance attribution",
        default_cron="0 8 1 * *",
        default_tz="America/New_York",
        job_run_label="intelligence_monthly_review",
    ),

    # ── Coverage & Quality ─────────────────────────────────────────
    JobTemplate(
        id="audit_quality_refresh",
        display_name="Audit Quality Refresh",
        group="market_data",
        task="backend.tasks.market.maintenance.audit_quality",
        description="Audit market data coverage and snapshot history consistency; writes market_audit:last Redis key",
        default_cron="0 */2 * * *",
        default_tz="UTC",
        job_run_label="admin_market_data_audit",
        timeout_s=360,
    ),
    JobTemplate(
        id="constituents_refresh",
        display_name="Index Constituents Refresh",
        group="market_data",
        task="backend.tasks.market.backfill.constituents",
        description="Refresh S&P 500, NASDAQ-100, Russell 2000 constituent lists from FMP",
        default_cron="30 0 * * *",
        default_tz="UTC",
        job_run_label="market_indices_constituents_refresh",
        timeout_s=300,
    ),
    JobTemplate(
        id="tracked_cache_refresh",
        display_name="Tracked Universe Cache Rebuild",
        group="market_data",
        task="backend.tasks.market.backfill.tracked_cache",
        description="Rebuild tracked symbol cache in Redis from DB (indices + holdings)",
        default_cron="45 0 * * *",
        default_tz="UTC",
        job_run_label="market_universe_tracked_refresh",
        timeout_s=120,
    ),
    JobTemplate(
        id="intraday_5m_backfill",
        display_name="5-Minute Candle Backfill",
        group="market_data",
        task="backend.tasks.market.intraday.bars_5m_last_n_days",
        description="Backfill 5-minute candles for tracked universe during market hours",
        default_cron="30 13-21 * * 1-5",
        default_tz="UTC",
        job_run_label="admin_backfill_5m",
        timeout_s=1800,
    ),

    # ── Auto-Ops ────────────────────────────────────────────────────
    JobTemplate(
        id="auto_ops_health_check",
        display_name="Auto-Ops Health Remediation",
        group="maintenance",
        task="backend.tasks.auto_ops_tasks.auto_remediate_health",
        description="Check admin health dimensions every 15 min and dispatch remediation tasks for any that are red/yellow",
        default_cron="*/15 * * * *",
        default_tz="UTC",
        job_run_label="auto_ops_health_check",
        timeout_s=90,
    ),

    # ── Deep Backfill ────────────────────────────────────────────────
    JobTemplate(
        id="full_historical_backfill",
        display_name="Full Historical Backfill",
        group="market",
        task="backend.tasks.market.backfill.full_historical",
        description="One-time deep backfill for HISTORY_TARGET_YEARS of daily bars, indicators, and snapshot history",
        default_cron="0 3 * * 0",
        default_tz="UTC",
        job_run_label="admin_backfill_since_date",
        timeout_s=14400,
    ),
]
