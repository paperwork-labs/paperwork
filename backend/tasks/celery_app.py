import logging
from datetime import datetime

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from backend.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "axiomfolio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        # Market data (Celery names: backend.tasks.market.<module>.<task>)
        "backend.tasks.market.backfill",
        "backend.tasks.market.coverage",
        "backend.tasks.market.fundamentals",
        "backend.tasks.market.history",
        "backend.tasks.market.indicators",
        "backend.tasks.market.institutional",
        "backend.tasks.market.intraday",
        "backend.tasks.market.iv",
        "backend.tasks.market.maintenance",
        "backend.tasks.market.reconciliation",
        "backend.tasks.market.regime",
        "backend.tasks.market.regime_alerts",
        # Portfolio
        "backend.tasks.portfolio.sync",
        "backend.tasks.portfolio.reconciliation",
        "backend.tasks.portfolio.orders",
        # Strategy
        "backend.tasks.strategy.tasks",
        "backend.tasks.strategy.exit_evaluation",
        "backend.tasks.strategy.auto_backtest",
        # Intelligence
        "backend.tasks.intelligence.tasks",
        # Operations
        "backend.tasks.ops.auto_ops",
        "backend.tasks.ops.ibkr_watchdog",
        # Nightly pipeline orchestrator (step-tracked 10-step run)
        "backend.tasks.pipeline.orchestrator",
    ],
)

celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

celery_app.conf.task_queues = (
    Queue("celery"),
    Queue("account_sync"),
    Queue("orders"),
)

celery_app.conf.task_routes = {
    "backend.tasks.portfolio.sync.*": {"queue": "account_sync"},
    "backend.tasks.portfolio.orders.*": {"queue": "orders"},
}

def _build_beat_schedule():
    """Generate beat_schedule from the job catalog.

    Each JobTemplate's 5-field cron expression is converted to a
    celery.schedules.crontab.  This replaces the old 3-entry hardcoded dict
    and eliminates the need for Render cron jobs.
    """
    from backend.tasks.job_catalog import CATALOG

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
