from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from backend.tasks.schedule_helpers import build_crontab_schedule
from backend.tasks.schedule_metadata import (
    HookConfig,
    MaintenanceWindow,
    ScheduleMetadata,
    SafetyConfig,
    metadata_to_options,
    save_schedule_metadata,
)

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
    # Safety defaults
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
    JobTemplate(
        id="market_indices_constituents_refresh",
        display_name="Refresh Index Constituents",
        group="market_data",
        task="backend.tasks.market_data_tasks.refresh_index_constituents",
        description="Fetch SP500 / NASDAQ100 / DOW30 constituents and update DB",
        default_cron="0 2 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="ibkr-daily-flex-sync",
        display_name="IBKR Daily Flex Sync",
        group="accounts",
        task="backend.tasks.account_sync.sync_all_ibkr_accounts",
        description="IBKR FlexQuery daily sync",
        default_cron="15 2 * * *",
        default_tz="UTC",
        queue="account_sync",
    ),
    JobTemplate(
        id="market_universe_tracked_refresh",
        display_name="Update Tracked Symbol Cache",
        group="market_data",
        task="backend.tasks.market_data_tasks.update_tracked_symbol_cache",
        description="Compute union of tracked symbols and publish deltas",
        default_cron="30 2 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_market_data_audit",
        display_name="Market Data Quality Audit",
        group="market_data",
        task="backend.tasks.market_data_tasks.audit_market_data_quality",
        description="Audit latest daily bars and snapshot history completeness",
        default_cron="45 2 * * *",
        default_tz="UTC",
        kwargs={"sample_limit": 25},
    ),
    JobTemplate(
        id="admin_coverage_backfill",
        display_name="Backfill Daily Coverage (Tracked)",
        group="market_data",
        task="backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked",
        description="Nightly guided backfill chain: refresh → tracked → daily backfill → recompute → snapshot history (rolling 20d) → coverage refresh (no 5m)",
        default_cron="0 3 * * *",
        default_tz="UTC",
        kwargs={"history_days": 20, "history_batch_size": 25},
    ),
    JobTemplate(
        id="admin_snapshots_history_record",
        display_name="Record Daily Analysis History",
        group="market_data",
        task="backend.tasks.market_data_tasks.record_daily_history",
        description="Record immutable daily analysis history",
        default_cron="20 3 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_indicators_recompute_universe",
        display_name="Recompute Indicators (Universe)",
        group="market_data",
        task="backend.tasks.market_data_tasks.recompute_indicators_universe",
        description="Recompute indicators for tracked universe from DB",
        default_cron="35 3 * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_backfill_5m",
        display_name="Backfill 5m Bars (D-1)",
        group="market_data",
        task="backend.tasks.market_data_tasks.backfill_5m_last_n_days",
        description="Backfill 5m bars for D-1",
        default_cron="10 4 * * *",
        default_tz="UTC",
        kwargs={"n_days": 1, "batch_size": 50},
    ),
    JobTemplate(
        id="admin_coverage_refresh",
        display_name="Monitor Coverage Health",
        group="market_data",
        task="backend.tasks.market_data_tasks.monitor_coverage_health",
        description="Snapshot coverage freshness and persist stale symbol metrics",
        default_cron="0 * * * *",
        default_tz="UTC",
    ),
    JobTemplate(
        id="admin_retention_enforce",
        display_name="Enforce 5m Retention",
        group="market_data",
        task="backend.tasks.market_data_tasks.enforce_price_data_retention",
        description="Delete 5m bars older than the retention window",
        default_cron="30 4 * * *",
        default_tz="UTC",
        kwargs={"max_days_5m": 90},
    ),
]


def _metadata_from_template(tmpl: JobTemplate) -> ScheduleMetadata:
    maint_windows = [
        MaintenanceWindow(**window) if not isinstance(window, MaintenanceWindow) else window
        for window in (tmpl.maintenance_windows or [])
    ]
    meta = ScheduleMetadata(
        queue=tmpl.queue,
        priority=None,
        dependencies=[],
        maintenance_windows=maint_windows,
        preflight_checks=[],
        safety=SafetyConfig(
            singleflight=tmpl.singleflight,
            max_concurrency=tmpl.max_concurrency,
            timeout_s=tmpl.timeout_s,
            retries=tmpl.retries,
            backoff_s=tmpl.backoff_s,
        ),
        hooks=HookConfig(),
        notes=None,
    )
    meta.touch_audit(actor="catalog_seed", is_create=True)
    return meta


def seed_redbeat_if_empty(celery_app) -> Dict[str, int]:
    """Seed RedBeat schedules from catalog when empty."""
    try:
        from redbeat import schedulers as rb
    except Exception:
        return {"seeded": 0}
    try:
        scheduler = rb.RedBeatScheduler(app=celery_app)
        # If there is at least one key, skip seeding
        existing = list(scheduler.rdb.scan_iter(match="redbeat:*:task"))
        if existing:
            return {"seeded": 0}
        seeded = 0
        for tmpl in CATALOG:
            minute, hour, dom, month, dow = tmpl.default_cron.split()
            meta = _metadata_from_template(tmpl)
            options = metadata_to_options(meta)
            schedule = build_crontab_schedule(
                minute=minute,
                hour=hour,
                day_of_month=dom,
                month_of_year=month,
                day_of_week=dow,
                timezone=tmpl.default_tz,
            )
            entry = rb.RedBeatSchedulerEntry(
                name=tmpl.id,
                task=tmpl.task,
                schedule=schedule,
                args=tmpl.args or (),
                kwargs=tmpl.kwargs or {},
                options=options,
                app=celery_app,
            )
            entry.save()
            save_schedule_metadata(tmpl.id, meta)
            seeded += 1
        return {"seeded": seeded}
    except Exception:
        return {"seeded": 0}


