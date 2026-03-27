from celery import Celery
from kombu import Queue
from backend.config import settings

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
        "backend.tasks.market.regime",
        "backend.tasks.market.regime_alerts",
        # Portfolio
        "backend.tasks.portfolio.sync",
        "backend.tasks.portfolio.reconciliation",
        "backend.tasks.portfolio.orders",
        # Strategy
        "backend.tasks.strategy.tasks",
        "backend.tasks.strategy.exit_evaluation",
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
    beat_schedule={
        "auto-ops-health-check": {
            "task": "backend.tasks.auto_ops_tasks.auto_remediate_health",
            "schedule": 900.0,
        },
    },
)
