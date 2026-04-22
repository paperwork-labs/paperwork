from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from backend.config import settings as _settings


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
    enabled: bool = True

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
    # E*TRADE sandbox direct-OAuth sync. Scheduled 15 min
    # after Schwab so the account_sync worker isn't pinned by two fan-outs at
    # once. ``timeout_s`` matches the task's ``time_limit`` (iron-law; see
    # engineering.mdc). Sandbox tokens expire at midnight US/Eastern, so the
    # oauth_token_refresh task (runs every 30 min) keeps tokens alive before
    # this fan-out fires.
    JobTemplate(
        id="etrade-daily-sync",
        display_name="E*TRADE Daily Sync",
        group="portfolio",
        task="backend.tasks.account_sync.sync_all_etrade_accounts",
        description=(
            "Sync all enabled E*TRADE accounts (positions, options, "
            "transactions, balances) via the sandbox OAuth 1.0a data API."
        ),
        default_cron="45 2 * * *",
        default_tz="UTC",
        queue="account_sync",
        timeout_s=960,
    ),
    JobTemplate(
        id="tradier-daily-sync",
        display_name="Tradier Daily Sync",
        group="portfolio",
        task="backend.tasks.account_sync.sync_all_tradier_accounts",
        description=(
            "Sync all enabled Tradier accounts (positions, options, "
            "transactions, trades, dividends, balances) via the Tradier "
            "v1 OAuth 2.0 data API (live + sandbox)."
        ),
        # 03:00 UTC — staggered 15 min after E*TRADE's 02:45 fan-out so
        # worker pressure spreads evenly across the 02:xx–03:xx window.
        default_cron="0 3 * * *",
        default_tz="UTC",
        queue="account_sync",
        # Iron law: timeout_s must match ``sync_all_tradier_accounts``
        # ``time_limit`` in ``backend/tasks/portfolio/tradier_sync.py``.
        timeout_s=960,
    ),
    JobTemplate(
        id="coinbase-daily-sync",
        display_name="Coinbase Daily Sync",
        group="portfolio",
        task="backend.tasks.account_sync.sync_all_coinbase_accounts",
        description=(
            "Sync all enabled Coinbase accounts (crypto wallets, transactions, "
            "trades, FIFO closing lots) via the v2 OAuth 2.0 wallet API."
        ),
        default_cron="15 3 * * *",
        default_tz="UTC",
        queue="account_sync",
        timeout_s=960,
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
    JobTemplate(
        id="oauth-token-refresh",
        display_name="OAuth Broker Token Refresh",
        group="portfolio",
        task="backend.tasks.portfolio.oauth_token_refresh.refresh_expiring_tokens",
        description=(
            "Refresh OAuth broker access tokens for connections expiring within "
            "the next 60 minutes. Permanent provider failures mark the "
            "connection REFRESH_FAILED so the user is prompted to re-authorize."
        ),
        default_cron="*/30 * * * *",
        default_tz="UTC",
        timeout_s=300,
        retries=0,
        queue="account_sync",
    ),
    JobTemplate(
        id="historical-import-backfill",
        display_name="Historical Portfolio Import Backfill",
        group="portfolio",
        task="backend.tasks.portfolio.historical_import.run_historical_import",
        description=(
            "User-initiated IBKR historical backfill from Flex XML/CSV. "
            "Event-driven only (no schedule)."
        ),
        default_cron="0 0 1 1 *",
        default_tz="UTC",
        timeout_s=3600,
        queue="heavy",
        enabled=False,
    ),
    JobTemplate(
        id="daily_portfolio_narrative_fanout",
        display_name="Daily Portfolio Narrative (Fanout)",
        group="portfolio",
        task="backend.tasks.portfolio.daily_narrative.fanout_daily_narratives",
        description=(
            "After US market close (weekdays): enqueue per-user AI daily portfolio narratives "
            "for accounts with open stock positions"
        ),
        default_cron="0 21 * * 1-5",
        default_tz="America/New_York",
        timeout_s=600,
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
        kwargs={"history_days": 20, "history_batch_size": 25, "backfill_days": 10},
        timeout_s=7200,
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
    JobTemplate(
        # The DAG bootstrap (`admin_coverage_backfill` at 01:00 UTC) does
        # invoke regime computation as a step, but a standalone catalog
        # entry is needed so that:
        #   1. operators can trigger / inspect regime independently from
        #      the Admin → Jobs panel,
        #   2. a fresh `MarketRegime` row exists by the time intelligence
        #      briefs and exit-cascade evaluation run later in the morning,
        #   3. when the nightly DAG fails partway, regime still gets
        #      computed at 03:20 UTC and the `regime` SystemStatus dim
        #      stays green.
        # Cron `'20 3 * * *'` is intentionally after `fundamentals_fill`
        # (03:15 UTC) and before `sync_earnings_calendar` (03:30 UTC), so
        # regime refresh does not overlap the heavy fundamentals run.
        id="compute_daily_regime",
        display_name="Daily Market Regime (R1-R5)",
        group="market_data",
        task="backend.tasks.market.regime.compute_daily",
        description=(
            "Compute the day's MarketRegime row (R1-R5) from VIX, breadth, and "
            "advance/decline inputs. Idempotent (upsert on as_of_date). Acts as a "
            "safety net so regime stays fresh even when the nightly DAG fails."
        ),
        default_cron="20 3 * * *",
        default_tz="UTC",
        job_run_label="compute_daily_regime",
        timeout_s=180,
    ),
    JobTemplate(
        id="sync_earnings_calendar",
        display_name="Earnings Calendar Sync",
        group="market_data",
        task="backend.tasks.market.earnings.sync_earnings_calendar",
        description="Sync upcoming earnings dates and estimates for tracked symbols (FMP premium + yfinance fallback)",
        default_cron="30 3 * * *",
        default_tz="UTC",
        job_run_label="sync_earnings_calendar",
        timeout_s=660,
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
        timeout_s=180,
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
        timeout_s=60,
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
        timeout_s=360,
    ),
    JobTemplate(
        id="fanout-daily-portfolio-narratives",
        display_name="Daily Portfolio Narratives (fanout)",
        group="portfolio",
        task="backend.tasks.portfolio.daily_narrative.fanout_daily_narratives",
        description=(
            "After US market close (weekdays), enqueue per-user AI narratives summarizing "
            "movers, stage transitions, ex-dividends, vs SPY, and macro regime."
        ),
        default_cron="0 21 * * 1-5",
        default_tz="America/New_York",
        job_run_label="fanout_daily_narratives",
        timeout_s=600,
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
        enabled=not _settings.PIPELINE_DAG_ENABLED,
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
        timeout_s=720,
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
        timeout_s=180,
    ),
    JobTemplate(
        id="data_quality_quorum_sweep",
        display_name="Cross-Provider Quorum Sweep",
        group="maintenance",
        task="backend.tasks.data_quality.scheduled_quorum_check.run",
        description=(
            "Sample ~5% of recent MarketSnapshot writes and cross-validate "
            "the LAST_PRICE field across configured market data providers. "
            "Logs QUORUM_REACHED / DISAGREEMENT / INSUFFICIENT_PROVIDERS rows "
            "to provider_quorum_log so the admin Data Quality dashboard can "
            "surface drift before it poisons indicators."
        ),
        default_cron="20 13-21 * * 1-5",  # hourly during US market hours
        default_tz="UTC",
        job_run_label="data_quality_quorum_sweep",
        kwargs={
            "sample_pct": 0.05,
            "max_sample": 50,
            "lookback_minutes": 60,
        },
        timeout_s=600,
        queue="celery",
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
        enabled=not _settings.PIPELINE_DAG_ENABLED,
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
        id="coverage_health_check",
        display_name="Coverage Health Refresh",
        group="market_data",
        task="backend.tasks.market.coverage.health_check",
        description="Snapshot coverage health into Redis for Admin UI stale counts and health dimension",
        default_cron="0 * * * *",
        default_tz="UTC",
        job_run_label="admin_coverage_refresh",
        timeout_s=180,
    ),
    JobTemplate(
        id="stale_daily_backfill",
        display_name="Stale Coverage Repair",
        group="market_data",
        task="backend.tasks.market.backfill.stale_daily",
        description="Backfill daily bars for stale/missing symbols detected by coverage analytics",
        default_cron="30 * * * *",
        default_tz="UTC",
        job_run_label="admin_coverage_backfill_stale",
        timeout_s=7200,
    ),
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
        enabled=not _settings.PIPELINE_DAG_ENABLED,
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
        enabled=not _settings.PIPELINE_DAG_ENABLED,
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

    # ── Dashboard cache warming ────────────────────────────────────
    # The /market-data/dashboard endpoint reads exclusively from Redis. On a cache
    # miss it returns 202 ("warming") and triggers a Celery task. Without periodic
    # warming the cache goes cold between nightly runs (especially after any worker
    # restart), forcing every dashboard load to wait 30+ s for the first computation.
    # 15-min refresh keeps every universe hot and absorbs worker recycles cleanly.
    JobTemplate(
        id="warm_dashboard_all",
        display_name="Warm Dashboard Cache (all)",
        group="market_data",
        task="backend.tasks.market.maintenance.warm_dashboard_cache",
        description="Refresh the 'all' dashboard cache key every 15 minutes",
        default_cron="*/15 * * * *",
        default_tz="UTC",
        job_run_label="admin_warm_dashboard",
        kwargs={"universe": "all"},
        timeout_s=180,
    ),
    JobTemplate(
        id="warm_dashboard_etf",
        display_name="Warm Dashboard Cache (etf)",
        group="market_data",
        task="backend.tasks.market.maintenance.warm_dashboard_cache",
        description="Refresh the 'etf' dashboard cache key every 15 minutes (offset by 5 min)",
        default_cron="5-59/15 * * * *",
        default_tz="UTC",
        job_run_label="admin_warm_dashboard",
        kwargs={"universe": "etf"},
        timeout_s=180,
    ),
    JobTemplate(
        id="warm_dashboard_holdings",
        display_name="Warm Dashboard Cache (holdings)",
        group="market_data",
        task="backend.tasks.market.maintenance.warm_dashboard_cache",
        description="Refresh the 'holdings' dashboard cache key every 15 minutes (offset by 10 min)",
        default_cron="10-59/15 * * * *",
        default_tz="UTC",
        job_run_label="admin_warm_dashboard",
        kwargs={"universe": "holdings"},
        timeout_s=180,
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
        timeout_s=180,
    ),

    # ── Deploy Health (G28) ─────────────────────────────────────────
    JobTemplate(
        id="deploy_health_poll",
        display_name="Deploy Health Poll (Render)",
        group="maintenance",
        task="backend.tasks.deploys.poll_deploy_health.poll_deploy_health",
        description=(
            "Poll Render deploy status for the services listed in "
            "DEPLOY_HEALTH_SERVICE_IDS every 5 minutes and persist events "
            "to deploy_health_events. Surfaces consecutive build_failed "
            "streaks that would otherwise go silent (D120)."
        ),
        default_cron="*/5 * * * *",
        default_tz="UTC",
        job_run_label="deploy_health_poll",
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
        enabled=False,
    ),
    # ── OHLCV Reconciliation ──────────────────────────────────────────
    JobTemplate(
        id="ohlcv_reconciliation",
        display_name="OHLCV Spot-Check Reconciliation",
        group="market_data",
        task="backend.tasks.market.reconciliation.spot_check",
        description="Weekly OHLCV spot-check reconciliation",
        default_cron="30 5 * * 0",
        default_tz="UTC",
        job_run_label="ohlcv_reconciliation",
        timeout_s=720,
    ),
    # ── Stage History Repair ──────────────────────────────────────────
    JobTemplate(
        id="repair_stage_history",
        display_name="Repair Stage History Monotonicity",
        group="maintenance",
        task="backend.tasks.market.indicators.repair_stage_history",
        description="Walk MarketSnapshotHistory and fix current_stage_days monotonicity violations",
        default_cron="0 4 * * 0",
        default_tz="UTC",
        job_run_label="admin_repair_stage_history",
        timeout_s=3600,
    ),
    # ── Picks Pipeline ────────────────────────────────────────────────
    JobTemplate(
        id="generate_candidates",
        display_name="Generate Trade Candidates",
        group="picks",
        task="backend.tasks.picks.generate_candidates",
        description=(
            "Run all registered candidate generators (Stage 2A + RS strong, etc.) "
            "and persist results to the candidates table for validator review"
        ),
        default_cron="30 5 * * 1-5",  # 05:30 UTC weekdays (after nightly pipeline)
        default_tz="UTC",
        job_run_label="generate_candidates",
        timeout_s=600,
    ),
    JobTemplate(
        id="parse_inbound_email",
        display_name="Parse Inbound Newsletter (Postmark)",
        group="picks",
        task="backend.tasks.picks.parse_inbound_email",
        description=(
            "Event-driven: invoked when Postmark inbound webhook stores an EmailInbox row; "
            "LLM parse implementation is scheduled separately"
        ),
        default_cron="0 0 1 1 *",  # not scheduled — triggered from webhook only
        default_tz="UTC",
        timeout_s=30,
        enabled=False,
    ),
    # ── Trade Decision Explainer ──────────────────────────────────────
    JobTemplate(
        id="explain_recent_trades",
        display_name="Explain Recent Trades (24h backfill)",
        group="intelligence",
        task="backend.tasks.agent.explain_recent_trades.explain_recent_trades",
        description=(
            "Daily: walk every executed order from the past 24h and "
            "generate a TradeDecisionExplanation if one does not exist. "
            "Idempotent — orders that already have a row are skipped."
        ),
        default_cron="30 4 * * *",
        default_tz="UTC",
        job_run_label="explain_recent_trades",
        kwargs={"lookback_hours": 24},
        timeout_s=900,
    ),
    JobTemplate(
        id="walk_forward_optimizer_run",
        display_name="Walk-Forward Optimizer Run",
        group="research",
        task="backend.tasks.backtest.walk_forward_runner.run_walk_forward_study",
        description=(
            "User-initiated Optuna hyperparameter study over rolling train/test "
            "windows. Triggered from POST /api/v1/backtest/walk-forward/studies; "
            "the cron entry is a no-op (enabled=False)."
        ),
        default_cron="0 0 1 1 *",  # event-driven only
        default_tz="UTC",
        queue="heavy",
        timeout_s=3600,
        # Per-row tasks: each WalkForwardStudy.id is its own work unit, so the
        # global singleflight lock would incorrectly serialize unrelated user
        # studies.
        singleflight=False,
        enabled=False,
    ),
    # ── Benchmark History (portfolio regression beta) ─────────
    JobTemplate(
        id="spy-history-daily",
        display_name="SPY Benchmark History Backfill",
        group="market_data",
        task="backend.tasks.market.benchmark_history.backfill_spy_history",
        description=(
            "Ensure daily MarketSnapshotHistory rows exist for SPY (fallback "
            "^GSPC) so PortfolioAnalyticsService can compute a real "
            "portfolio-vs-benchmark regression beta. No-op fast path when "
            "today's row already exists."
        ),
        default_cron="10 22 * * 1-5",  # 22:10 UTC weekdays (after US close)
        default_tz="UTC",
        job_run_label="market_benchmark_spy_history_backfill",
        queue="market",
        timeout_s=300,
    ),
    # ── Conviction Picks (multi-year horizon) ─────────────────────────
    # Nightly job that ranks the market universe for conviction-sleeve
    # candidates and writes a per-user batch to ``conviction_picks``.
    # Scheduled after ``admin_coverage_backfill`` (01:00 UTC) and
    # ``fundamentals_fill`` (03:15 UTC) so the generator reads the
    # freshest technical + fundamentals state. ``timeout_s`` matches
    # ``time_limit`` on ``generate_conviction_picks``.
    JobTemplate(
        id="generate_conviction_picks",
        display_name="Generate Conviction Picks",
        group="picks",
        task="backend.tasks.market.conviction.generate_conviction_picks",
        description=(
            "Rank the tracked universe for multi-year conviction-sleeve "
            "picks (stage 2 posture, sustained RS, earnings trajectory, "
            "valuation proxy) and persist a per-user ranked batch to the "
            "conviction_picks table."
        ),
        default_cron="45 3 * * *",  # 03:45 UTC nightly
        default_tz="UTC",
        job_run_label="generate_conviction_picks",
        timeout_s=900,
    ),
    # ── Corporate Actions ─────────────────────────────────────────────
    JobTemplate(
        id="daily_corporate_actions",
        display_name="Daily Corporate Actions Sync + Apply",
        group="market_data",
        task="backend.tasks.corporate_actions.daily_apply.daily_corporate_actions",
        description=(
            "Fetch new corporate actions (splits, dividends) from FMP for the "
            "tracked universe and apply every PENDING action whose ex_date "
            "has passed. Adjusts user positions, tax lots, and (when "
            "FEATURE_BACK_ADJUST_OHLCV=1) historical OHLCV. Idempotent."
        ),
        default_cron="0 4 * * *",  # 04:00 UTC daily (after nightly pipeline)
        default_tz="UTC",
        job_run_label="daily_corporate_actions",
        kwargs={"fetch_lookback_days": 7},
        timeout_s=1800,
        queue="heavy",
    ),
    # ── Options chain (gold surface) ────────────────────────────
    JobTemplate(
        id="options-chain-refresh-symbol",
        display_name="Options chain refresh (symbol)",
        group="market_data",
        task="backend.tasks.market.options_chain.refresh_options_chain_for_symbol",
        description="Refresh one symbol's options surface snapshot.",
        default_cron="0 0 1 1 *",
        default_tz="UTC",
        job_run_label="options_chain_symbol",
        timeout_s=60,
        queue="celery",
        enabled=False,
    ),
    JobTemplate(
        id="options-chain-refresh-universe",
        display_name="Options chain refresh (tracked universe fan-out)",
        group="market_data",
        task=(
            "backend.tasks.market.options_chain."
            "refresh_options_chains_for_tracked_universe"
        ),
        description="Enqueue one per-symbol options chain task (tracked).",
        default_cron="0 0 1 1 *",
        default_tz="UTC",
        job_run_label="options_chain_universe",
        timeout_s=600,
        queue="celery",
        enabled=False,
    ),
]

# Alias for callers that expect JOB_CATALOG (e.g. task_run singleflight lookup).
JOB_CATALOG: List[JobTemplate] = CATALOG
