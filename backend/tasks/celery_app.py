from celery import Celery
from celery.schedules import crontab
from backend.config import settings
import os

ENABLE_CELERY_BEAT = bool(settings.ENABLE_CELERY_BEAT)
USE_REDBEAT = bool(settings.ENABLE_REDBEAT)

celery_app = Celery(
    "quantmatrix",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.account_sync",
        "backend.tasks.market_data_tasks",
    ],
)

# Use values provided by settings (from .env/docker-compose)
celery_app.conf.broker_url = settings.CELERY_BROKER_URL
celery_app.conf.result_backend = settings.CELERY_RESULT_BACKEND

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "backend.tasks.account_sync.*": {"queue": "account_sync"},
    },
    # Worker configuration
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    # Task execution
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Results
    result_expires=3600,  # 1 hour
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Beat schedule for periodic tasks (bootstrap defaults; RedBeat may override)
    beat_schedule={},
)

# -------------------- Bootstrap static schedules (cleanly grouped) --------------------
# Note: These serve as defaults when RedBeat is empty (e.g., first boot). With RedBeat,
# schedules are stored dynamically in Redis and can be created/edited via Admin UI.
if ENABLE_CELERY_BEAT:
    ACCOUNT_BEAT_SCHEDULE = {
        # Nightly (UTC) – Accounts
        "ibkr-daily-flex-sync": {
            "task": "backend.tasks.account_sync.sync_all_ibkr_accounts",
            "schedule": crontab(hour=2, minute=15),
            "args": (),
        },
    }

    MARKET_DATA_BEAT_SCHEDULE = {
        # Nightly (UTC) – Market Data
        "restore-daily-coverage-tracked": {
            "task": "backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked",
            "schedule": crontab(hour=3, minute=0),
            "args": (),
            # Nightly should be fast: keep snapshot history refresh to a small rolling window.
            "kwargs": {"history_days": 5, "history_batch_size": 25},
        },
        "monitor-coverage-health-hourly": {
            "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
            "schedule": crontab(minute=0, hour="*"),
            "args": (),
        },
    }

    # Merge grouped defaults into the bootstrap beat_schedule
    celery_app.conf.beat_schedule.update(ACCOUNT_BEAT_SCHEDULE)
    celery_app.conf.beat_schedule.update(MARKET_DATA_BEAT_SCHEDULE)

# -------------------- RedBeat Scheduler (dynamic schedules) --------------------
if ENABLE_CELERY_BEAT and USE_REDBEAT:
    # Use RedBeat scheduler backed by Redis for dynamic CRUD of schedules
    celery_app.conf.beat_scheduler = "redbeat.schedulers:RedBeatScheduler"
    # Configure RedBeat redis URL; default to CELERY_BROKER_URL or REDIS_URL
    celery_app.conf.redbeat_redis_url = (
        os.getenv("REDBEAT_REDIS_URL")
        or settings.CELERY_BROKER_URL
        or settings.REDIS_URL
    )
    # Optional: lock key and key prefix
    celery_app.conf.redbeat_key_prefix = "redbeat:"

# Optional: Seed RedBeat from catalog if empty
if ENABLE_CELERY_BEAT and USE_REDBEAT:
    try:
        from backend.tasks.job_catalog import seed_redbeat_if_empty
        seed_redbeat_if_empty(celery_app)
    except Exception:
        pass

# Preserve schedule object
celery_app.conf.beat_schedule = celery_app.conf.beat_schedule
