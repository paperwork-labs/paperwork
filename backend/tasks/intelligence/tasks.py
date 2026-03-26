"""Celery tasks for intelligence brief generation and delivery."""

import asyncio
import json
import logging
from datetime import date, datetime, timezone

from backend.database import SessionLocal
from backend.tasks.celery_app import celery_app
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)


def _setup_loop():
    return asyncio.new_event_loop()


@celery_app.task(
    name="backend.tasks.intelligence_tasks.generate_daily_digest",
    soft_time_limit=300,
    time_limit=360,
)
@task_run("intelligence_daily_digest")
def generate_daily_digest_task(deliver_discord: bool = True) -> dict:
    """Generate daily intelligence digest and optionally deliver to Discord."""
    from backend.services.intelligence.brief_generator import generate_daily_digest

    session = SessionLocal()
    try:
        brief = generate_daily_digest(session)

        _store_brief(session, brief)

        if deliver_discord:
            from backend.services.intelligence.brief_delivery import deliver_daily_digest_discord
            loop = _setup_loop()
            try:
                loop.run_until_complete(deliver_daily_digest_discord(brief))
            finally:
                loop.close()

        logger.info(
            "Daily digest generated: regime=%s, transitions=%d, snapshots=%d",
            brief.get("regime", {}).get("state"),
            len(brief.get("stage_transitions", [])),
            brief.get("snapshot_count", 0),
        )
        return {"status": "ok", "type": "daily", "as_of": brief.get("as_of")}
    except Exception as e:
        logger.exception("Daily digest generation failed: %s", e)
        return {"status": "error", "error": str(e)}
    finally:
        session.close()


@celery_app.task(
    name="backend.tasks.intelligence_tasks.generate_weekly_brief",
    soft_time_limit=600,
    time_limit=660,
)
@task_run("intelligence_weekly_brief")
def generate_weekly_brief_task(deliver_discord: bool = True) -> dict:
    """Generate weekly strategy brief and optionally deliver to Discord."""
    from backend.services.intelligence.brief_generator import generate_weekly_brief

    session = SessionLocal()
    try:
        brief = generate_weekly_brief(session)

        _store_brief(session, brief)

        if deliver_discord:
            from backend.services.intelligence.brief_delivery import deliver_weekly_brief_discord
            loop = _setup_loop()
            try:
                loop.run_until_complete(deliver_weekly_brief_discord(brief))
            finally:
                loop.close()

        logger.info(
            "Weekly brief generated: set1_entries=%d, snapshots=%d",
            len(brief.get("set1_entries", [])),
            brief.get("snapshot_count", 0),
        )
        return {"status": "ok", "type": "weekly", "as_of": brief.get("as_of")}
    except Exception as e:
        logger.exception("Weekly brief generation failed: %s", e)
        return {"status": "error", "error": str(e)}
    finally:
        session.close()


@celery_app.task(
    name="backend.tasks.intelligence_tasks.generate_monthly_review",
    soft_time_limit=600,
    time_limit=660,
)
@task_run("intelligence_monthly_review")
def generate_monthly_review_task(deliver_discord: bool = True) -> dict:
    """Generate monthly review."""
    from backend.services.intelligence.brief_generator import generate_monthly_review

    session = SessionLocal()
    try:
        brief = generate_monthly_review(session)
        _store_brief(session, brief)

        logger.info(
            "Monthly review generated: regime_transitions=%d",
            brief.get("regime_transitions", 0),
        )
        return {"status": "ok", "type": "monthly", "as_of": brief.get("as_of")}
    except Exception as e:
        logger.exception("Monthly review generation failed: %s", e)
        return {"status": "error", "error": str(e)}
    finally:
        session.close()


def _store_brief(session: SessionLocal, brief: dict) -> None:
    """Persist brief as a JobRun metadata entry for retrieval via API."""
    from backend.models.market_data import JobRun

    try:
        run = JobRun(
            task_name=f"intelligence_{brief['type']}_brief",
            status="ok",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            result_meta=brief,
        )
        session.add(run)
        session.commit()
    except Exception as e:
        logger.warning("Failed to store brief: %s", e)
        session.rollback()
