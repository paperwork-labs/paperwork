"""Scheduled generation of per-user daily portfolio narratives."""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from celery import shared_task

from app.database import SessionLocal
from app.models.position import Position, PositionStatus
from app.models.user import User
from app.services.narrative.builder import build_portfolio_summary, render_narrative
from app.services.narrative.persistence import fetch_fresh_narrative, persist_narrative
from app.services.narrative.providers.openai_chat import OpenAIChatProvider

logger = logging.getLogger(__name__)


def _target_date(iso: str | None) -> date:
    if iso:
        return date.fromisoformat(iso)
    return datetime.now(ZoneInfo("America/New_York")).date()


@shared_task(
    name="app.tasks.portfolio.daily_narrative.generate_daily_narrative",
    soft_time_limit=90,
    time_limit=120,
)
def generate_daily_narrative(user_id: int, target_date_iso: str | None = None) -> dict:
    """Build summary, call LLM (or fallback), persist one row per user per date."""
    d = _target_date(target_date_iso)
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            return {"status": "error", "error": "user not found", "user_id": user_id}

        fresh = fetch_fresh_narrative(db, user_id, d)
        if fresh is not None:
            return {
                "status": "skipped",
                "reason": "fresh_narrative_exists",
                "user_id": user_id,
                "narrative_id": fresh.id,
                "provider": fresh.provider,
                "is_fallback": fresh.is_fallback,
            }

        summary = build_portfolio_summary(db, user_id, d)
        provider = OpenAIChatProvider()
        result = render_narrative(summary, provider)
        row = persist_narrative(db, user_id, summary, result, d)
        db.commit()
        return {
            "status": "ok",
            "user_id": user_id,
            "narrative_id": row.id,
            "provider": result.provider,
            "is_fallback": result.is_fallback,
        }
    except Exception as e:
        logger.exception("generate_daily_narrative failed user=%s: %s", user_id, e)
        db.rollback()
        raise
    finally:
        db.close()


@shared_task(
    name="app.tasks.portfolio.daily_narrative.fanout_daily_narratives",
    soft_time_limit=540,
    time_limit=600,
)
def fanout_daily_narratives() -> dict:
    """Dispatch per-user narrative generation for users with open stock positions."""
    db = SessionLocal()
    dispatched = 0
    try:
        q = (
            db.query(Position.user_id)
            .filter(
                Position.status == PositionStatus.OPEN,
                Position.instrument_type == "STOCK",
            )
            .distinct()
            .all()
        )
        for (uid,) in q:
            if uid is None:
                continue
            generate_daily_narrative.delay(int(uid))
            dispatched += 1
        return {"status": "ok", "dispatched": dispatched}
    finally:
        db.close()
