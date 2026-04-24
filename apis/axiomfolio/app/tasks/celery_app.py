import logging
from datetime import datetime

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "axiomfolio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        # Market data (Celery names: app.tasks.market.<module>.<task>)
        "app.tasks.market.backfill",
        "app.tasks.market.coverage",
        "app.tasks.market.earnings",
        "app.tasks.market.fundamentals",
        "app.tasks.market.history",
        "app.tasks.market.indicators",
        "app.tasks.market.institutional",
        "app.tasks.market.intraday",
        "app.tasks.market.iv",
        "app.tasks.market.options_chain",
        "app.tasks.market.maintenance",
        "app.tasks.market.reconciliation",
        "app.tasks.market.regime",
        "app.tasks.market.regime_alerts",
        # Portfolio
        "app.tasks.portfolio.sync",
        "app.tasks.portfolio.reconciliation",
        "app.tasks.portfolio.orders",
        "app.tasks.portfolio.daily_narrative",
        "app.tasks.portfolio.oauth_token_refresh",
        "app.tasks.portfolio.historical_import",
        # Per-broker fan-outs (E*TRADE, Tradier, …). Separate include lines
        # so new brokers add a module without editing shared sync tasks.
        "app.tasks.portfolio.etrade_sync",
        "app.tasks.portfolio.tradier_sync",
        "app.tasks.portfolio.coinbase_sync",
        # Strategy
        "app.tasks.strategy.tasks",
        "app.tasks.strategy.exit_evaluation",
        "app.tasks.strategy.auto_backtest",
        # Intelligence
        "app.tasks.intelligence.tasks",
        # Operations
        "app.tasks.ops.auto_ops",
        "app.tasks.ops.explain_anomaly",
        "app.tasks.ops.ibkr_watchdog",
        "app.tasks.agent.explain_recent_trades",
        # Data quality (cross-provider quorum + drift sweeps)
        "app.tasks.data_quality.scheduled_quorum_check",
        # Nightly pipeline orchestrator (step-tracked 10-step run)
        "app.tasks.pipeline.orchestrator",
        "app.tasks.picks.generate_candidates",
        "app.tasks.candidates",
        "app.tasks.picks.parse_inbound",
        "app.tasks.picks.external_signals",
        # Multi-tenant hardening (GDPR + cost rollup)
        "app.tasks.multitenant.gdpr",
        "app.tasks.multitenant.cost_rollup",
        # Backtest hyperparameter optimization (heavy queue)
        "app.tasks.backtest.walk_forward_runner",
        # Corporate actions (splits, dividends, mergers)
        "app.tasks.corporate_actions.daily_apply",
        # Shadow (paper) orders — mark-to-market refresh (15m beat; see job_catalog)
        "app.services.execution.shadow_mark_to_market",
        # Deploy-health guardrail (G28) — poll Render deploy state every 5 min
        "app.tasks.deploys.poll_deploy_health",
    ],
)

celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

celery_app.conf.task_queues = (
    Queue("celery"),
    Queue("account_sync"),
    Queue("orders"),
    Queue("heavy"),
)

# Routing policy:
#   - Default `celery` queue: short-running tasks (<60s) handled by the fast worker.
#   - `account_sync`: broker syncs, handled by the fast worker.
#   - `orders`: order lifecycle + watchdogs, handled by the fast worker.
#   - `heavy`: long-running market-data jobs (>5 min) handled exclusively
#     by axiomfolio-worker-heavy. A single `repair_stage_history` previously
#     blocked the only worker for an hour, starving dashboard warming and
#     causing the "Queued but never started" failure mode.
#
# When adding a new task, route to `heavy` if its `time_limit > 300` OR if
# it iterates over the full tracked universe (~2,500 symbols).
celery_app.conf.task_routes = {
    "app.tasks.portfolio.sync.*": {"queue": "account_sync"},
    "app.tasks.portfolio.orders.*": {"queue": "orders"},
    "app.tasks.portfolio.historical_import.*": {"queue": "heavy"},
    # Market-data heavy jobs (snapshot history backfills, indicator repair,
    # multi-day OHLCV backfills, fundamentals fill, intraday backfill).
    "app.tasks.market.history.*": {"queue": "heavy"},
    "app.tasks.market.fundamentals.*": {"queue": "heavy"},
    "app.tasks.market.intraday.*": {"queue": "heavy"},
    "app.tasks.market.backfill.symbol": {"queue": "heavy"},
    "app.tasks.market.backfill.symbols": {"queue": "heavy"},
    "app.tasks.market.backfill.daily_bars": {"queue": "heavy"},
    "app.tasks.market.backfill.daily_since": {"queue": "heavy"},
    "app.tasks.market.backfill.full_historical": {"queue": "heavy"},
    "app.tasks.market.maintenance.*": {"queue": "heavy"},
    # Reconciliation spot-check is also long-running.
    "app.tasks.market.reconciliation.spot_check": {"queue": "heavy"},
    # GDPR data export & delete: long-running per-user jobs that walk
    # every user-scoped table. Route to heavy so they don't starve the
    # regular API/celery worker. Cost rollup is fast (default queue).
    "app.tasks.multitenant.gdpr.*": {"queue": "heavy"},
    "app.tasks.multitenant.cost_rollup.*": {"queue": "celery"},
    # Walk-forward optimizer trials can run 30+ min each.
    "app.tasks.backtest.walk_forward_runner.*": {"queue": "heavy"},
    "backtest.walk_forward_run": {"queue": "heavy"},
    # Corporate-action engine (full universe + per-user position rewrite).
    "app.tasks.corporate_actions.*": {"queue": "heavy"},
    "app.tasks.candidates.*": {"queue": "heavy"},
}

def _build_beat_schedule():
    """Generate beat_schedule from the job catalog.

    Each JobTemplate's 5-field cron expression is converted to a
    celery.schedules.crontab.  This replaces the old 3-entry hardcoded dict
    and eliminates the need for Render cron jobs.
    """
    from app.tasks.job_catalog import CATALOG

    schedule = {}
    for job in CATALOG:
        if not job.enabled:
            logger.info("Skipping disabled catalog entry: %s", job.id)
            continue
        parts = job.default_cron.strip().split()
        if len(parts) == 6:
            minute, hour, dom, month, dow = parts[1], parts[2], parts[3], parts[4], parts[5]
        elif len(parts) == 5:
            minute, hour, dom, month, dow = parts
        else:
            logger.warning("Skipping catalog entry %s: invalid cron %r", job.id, job.default_cron)
            continue

        nowfun = None
        if job.default_tz and job.default_tz != "UTC":
            from zoneinfo import ZoneInfo
            from functools import partial
            _zi = ZoneInfo(job.default_tz)
            nowfun = partial(datetime.now, _zi)

        entry = {
            "task": job.task,
            "schedule": crontab(
                minute=minute, hour=hour,
                day_of_week=dow, day_of_month=dom,
                month_of_year=month,
                nowfun=nowfun,
            ),
        }
        if job.kwargs:
            entry["kwargs"] = job.kwargs
        if job.args:
            entry["args"] = job.args
        if job.queue:
            entry["options"] = {"queue": job.queue}

        schedule[job.id] = entry

    return schedule


celery_app.conf.update(
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    beat_schedule=_build_beat_schedule(),
)


from celery.signals import worker_process_init, worker_ready  # noqa: E402


@worker_process_init.connect
def _dispose_engine_on_fork(**kwargs):
    """Reset the SQLAlchemy connection pool after Celery forks a child process.

    Without this, forked children inherit the parent's stale connections,
    exhausting the QueuePool (pool_size=10 + max_overflow=20) because the
    inherited slots appear occupied but are actually dead.
    """
    from app.database import engine
    engine.dispose()
    logger.info("Disposed SQLAlchemy engine pool for new worker child")


@worker_process_init.connect
def _init_otel_on_fork(**kwargs):
    """Install OpenTelemetry providers in each worker child process.

    Auto-instrumentation patches must be re-applied after the prefork
    because the parent process's instrumentation hooks do not survive
    fork on every platform. ``init_tracing`` / ``init_metrics`` are
    idempotent and degrade to no-op when no OTLP endpoint is configured,
    so this is safe to call unconditionally.
    """
    import os

    if os.getenv("AXIOMFOLIO_TESTING") == "1":
        return
    try:
        from app.observability import init_metrics, init_tracing

        environment = "production" if not settings.DEBUG else "dev"
        init_tracing(
            service_name="axiomfolio-worker",
            environment=environment,
            fastapi_app=None,
            instrument_fastapi=False,
        )
        init_metrics(service_name="axiomfolio-worker")
    except Exception as exc:  # noqa: BLE001 — observability must never crash worker
        logger.warning(
            "OTel init in worker child failed (continuing without instrumentation): %s",
            exc,
            exc_info=True,
        )


@worker_ready.connect
def _warm_caches(sender, **kwargs):
    """Pre-populate expensive Redis caches on worker start.

    Only warms from MVs to avoid expensive raw-table fallback queries
    that could delay worker readiness or hit statement_timeout.
    """
    try:
        from app.services.market.market_mv_service import market_mv_service
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            if not market_mv_service.any_mv_exists(db):
                logger.info("Cache warmup skipped: no MVs available yet")
                return
            series = market_mv_service.get_breadth_series(db, days=120)
            logger.info(
                "Cache warmup: breadth_series (%d points)", len(series)
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning("Cache warmup failed (non-fatal): %s", e)
