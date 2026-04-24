"""Celery tasks: per-tenant candidate generation (Beat schedule)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence

from app.database import SessionLocal
from app.models import User
from app.services.billing.entitlement_service import EntitlementService
from app.tasks.celery_app import celery_app
from app.tasks.utils.task_utils import task_run

from app.services.gold.picks import generators  # noqa: F401 — register generators
from app.services.gold.picks.candidate_generator import run_all_generators

logger = logging.getLogger(__name__)

_FEATURE_CANDIDATES = "picks.candidates"


@celery_app.task(
    name="app.tasks.candidates.generate_candidates_daily",
    soft_time_limit=570,
    time_limit=600,
    queue="heavy",
)
@task_run("generate_candidates_daily")
def generate_candidates_daily(only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Run candidate generators once per entitled user (Pro+ ``picks.candidates``).

    One DB session per user so a failure in one tenant does not roll back others.
    """
    list_session = SessionLocal()
    try:
        users: list = (
            list_session.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id.asc())
            .all()
        )
    finally:
        list_session.close()

    total_users = len(users)
    users_processed = 0
    users_skipped_no_tier = 0
    errors = 0
    symbols_scanned = 0
    candidates_written = 0

    for user in users:
        check_db = SessionLocal()
        try:
            decision = EntitlementService.check(check_db, user, _FEATURE_CANDIDATES)
        finally:
            check_db.close()

        if not decision.allowed:
            users_skipped_no_tier += 1
            continue

        db_u = SessionLocal()
        try:
            reports = run_all_generators(
                db_u, only=only, quality_score_user_id=user.id
            )
            db_u.commit()
            users_processed += 1
            for r in reports:
                symbols_scanned += r.produced
                candidates_written += r.created
        except Exception as e:  # noqa: BLE001
            db_u.rollback()
            errors += 1
            logger.exception(
                "generate_candidates_daily failed for user_id=%s: %s", user.id, e
            )
        finally:
            db_u.close()

    assert users_processed + users_skipped_no_tier + errors == total_users, (
        "user counter drift: processed=%s skipped_tier=%s errors=%s total=%s"
        % (users_processed, users_skipped_no_tier, errors, total_users)
    )

    payload: Dict[str, Any] = {
        "status": "ok",
        "users_processed": users_processed,
        "users_skipped_no_tier": users_skipped_no_tier,
        "errors": errors,
        "symbols_scanned": symbols_scanned,
        "candidates_written": candidates_written,
        "total_users": total_users,
    }
    if errors:
        payload["error"] = f"{errors} user(s) failed; see worker logs for tracebacks"
    return payload
