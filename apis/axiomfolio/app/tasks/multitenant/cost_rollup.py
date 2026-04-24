"""Daily per-tenant cost rollup task."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

from app.database import SessionLocal
from app.services.multitenant.cost_attribution import CostAttributionService

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.multitenant.cost_rollup.rollup_yesterday",
    queue="celery",
    soft_time_limit=240,
    time_limit=300,
)
def rollup_yesterday() -> dict:
    """Compute the rollup for yesterday (UTC). Returns ``{day, written}``.

    Scheduled by Celery beat (catalog entry to be added in a follow-up
    that wires beat schedules; until then, trigger manually via
    ``/api/v1/admin/jobs/run-now``).
    """
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    db = SessionLocal()
    try:
        written = CostAttributionService(db).rollup_day(yesterday)
    finally:
        db.close()
    logger.info("cost_rollup.rollup_yesterday: day=%s written=%d", yesterday, written)
    return {"day": yesterday.isoformat(), "written": written}


@shared_task(
    name="app.tasks.multitenant.cost_rollup.rollup_day",
    queue="celery",
    soft_time_limit=240,
    time_limit=300,
)
def rollup_day(day_iso: str) -> dict:
    """Recompute the rollup for an arbitrary ``YYYY-MM-DD`` (admin tool)."""
    day = datetime.fromisoformat(day_iso).date()
    db = SessionLocal()
    try:
        written = CostAttributionService(db).rollup_day(day)
    finally:
        db.close()
    return {"day": day.isoformat(), "written": written}
