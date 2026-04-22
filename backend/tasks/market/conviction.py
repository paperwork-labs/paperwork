"""Celery task: nightly conviction pick generation.

Runs after the market snapshot pipeline so the generator reads the
freshest technical + fundamentals state. For each user with at least
one open position, writes a ranked ``ConvictionPick`` batch tagged with
the same ``generated_at`` timestamp; the public
``GET /api/v1/picks/conviction`` endpoint reads the latest batch per
user.

Why per-user rows when the source universe is shared
----------------------------------------------------

The generator's *candidate set* is the same for every user (it reads
``MarketSnapshot``), but the downstream story is per-user:

* Tier-based trimming of the visible list (D122).
* Exclusion of symbols the user already holds in the conviction sleeve.
* "Why this stock for *you*" AgentBrain narratives later.

Keeping persistence per-user means all of that lives on the read path
without a second JOIN. One-row-per-generation is also acceptable: the
table is small (N users * ~25 picks) and the write cost is dominated
by the generator's single scan, not the insert fan-out.

Per ``engineering.mdc``:

* ``time_limit`` / ``soft_time_limit`` match the ``job_catalog.py``
  entry (``timeout_s=900``).
* The task owns its own ``SessionLocal`` (top-level Celery entry
  point) and passes the session into the generator; commits exactly
  once on success.
* Per-user loop emits ``written / skipped / errors`` counters that
  sum to the number of users scanned (no silent fallback).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import shared_task
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models.conviction_pick import ConvictionPick
from backend.models.position import Position, PositionStatus, Sleeve
from backend.models.user import User
from backend.services.gold.conviction_pick_generator import (
    ConvictionPickGenerator,
    ConvictionThresholds,
    GenerationReport,
)
from backend.tasks.utils.task_utils import task_run

logger = logging.getLogger(__name__)

_DEFAULT_SOFT = 840
_DEFAULT_HARD = 900


def _active_user_ids(db: Session) -> set[int]:
    """Return the distinct user IDs the generator should run for.

    Heuristic: any user who owns at least one open ``Position`` is
    in-scope. Users with no book yet get skipped (we'd generate
    identical picks for them anyway — cheaper to light them up the
    first time they authenticate their broker).
    """
    rows = (
        db.query(Position.user_id)
        .filter(Position.status == PositionStatus.OPEN)
        .distinct()
        .all()
    )
    return {uid for (uid,) in rows if uid is not None}


def _user_conviction_holdings(db: Session, user_id: int) -> set[str]:
    """Symbols the user already owns in the conviction sleeve; excluded."""
    rows = (
        db.query(Position.symbol)
        .filter(
            Position.user_id == user_id,
            Position.status == PositionStatus.OPEN,
            Position.sleeve == Sleeve.CONVICTION.value,
        )
        .all()
    )
    return {(s or "").upper() for (s,) in rows}


def _persist_for_user(
    db: Session,
    *,
    user_id: int,
    report: GenerationReport,
    generated_at: datetime,
    exclude: Optional[set[str]] = None,
) -> int:
    """Write the generator's ranked list for one user; returns rows written."""
    exclude = exclude or set()
    written = 0
    rank_counter = 0
    for cand in report.candidates:
        if cand.symbol in exclude:
            continue
        rank_counter += 1
        db.add(
            ConvictionPick(
                user_id=user_id,
                symbol=cand.symbol,
                rank=rank_counter,
                score=cand.score,
                score_breakdown=cand.breakdown,
                rationale=cand.rationale,
                stage_label=cand.stage_label,
                generated_at=generated_at,
                generator_version=ConvictionPickGenerator.version,
            )
        )
        written += 1
    return written


@shared_task(
    name="backend.tasks.market.conviction.generate_conviction_picks",
    soft_time_limit=_DEFAULT_SOFT,
    time_limit=_DEFAULT_HARD,
    queue="celery",
)
@task_run("generate_conviction_picks")
def generate_conviction_picks(
    max_users: Optional[int] = None,
) -> Dict[str, Any]:
    """Nightly entry point. Runs the generator once, then fans out per user.

    Args:
        max_users: optional cap for dry runs / CI.

    Returns:
        JSON-serializable summary for ``JobRun.result``.
    """
    db = SessionLocal()
    try:
        gen = ConvictionPickGenerator(ConvictionThresholds())
        report = gen.generate(db)
        generated_at = datetime.now(timezone.utc)

        user_ids = sorted(_active_user_ids(db))
        if max_users is not None:
            user_ids = user_ids[:max_users]

        written, skipped, errors, rows_written = 0, 0, 0, 0
        for uid in user_ids:
            try:
                exclude = _user_conviction_holdings(db, uid)
                rows = _persist_for_user(
                    db,
                    user_id=uid,
                    report=report,
                    generated_at=generated_at,
                    exclude=exclude,
                )
                if rows == 0:
                    skipped += 1
                else:
                    written += 1
                    rows_written += rows
            except Exception as e:
                errors += 1
                logger.warning(
                    "conviction pick persist failed for user %s: %s", uid, e
                )

        assert written + skipped + errors == len(user_ids), "counter drift"

        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "conviction pick commit failed; rolling back entire run"
            )
            raise

        summary: Dict[str, Any] = {
            "status": "ok",
            "users_scanned": len(user_ids),
            "written": written,
            "rows_written": rows_written,
            "users_skipped": skipped,
            "errors": errors,
            "generator_report": report.to_dict(),
            "generator_version": ConvictionPickGenerator.version,
            "generated_at": generated_at.isoformat(),
        }
        logger.info("conviction pick generation complete: %s", summary)
        return summary
    finally:
        db.close()


__all__ = ["generate_conviction_picks"]
