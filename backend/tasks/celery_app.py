from celery import Celery
from kombu import Queue
from backend.config import settings

celery_app = Celery(
    "axiomfolio",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.account_sync",
        "backend.tasks.market_data_tasks",
        "backend.tasks.order_tasks",
        "backend.tasks.strategy_tasks",
        "backend.tasks.ibkr_watchdog",
        "backend.tasks.reconciliation_tasks",
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
    "backend.tasks.account_sync.*": {"queue": "account_sync"},
    "backend.tasks.order_tasks.*": {"queue": "orders"},
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
    beat_schedule={},
)
