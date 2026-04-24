"""Published picks feed (tier-gated)."""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.picks import Candidate, CandidateQueueState
from backend.models.user import User
from backend.services.billing.entitlement_service import EntitlementService

router = APIRouter()


def _serialize_public(c: Candidate) -> dict[str, Any]:
    return {
        "id": c.id,
        "ticker": c.symbol,
        "action": c.action_suggestion.value.upper(),
        "thesis": c.rationale_summary,
        "target_price": str(c.suggested_target) if c.suggested_target is not None else None,
        "stop_loss": str(c.suggested_stop) if c.suggested_stop is not None else None,
        "source": c.generator_name,
        "published_at": c.published_at.isoformat() if c.published_at else None,
    }


def _preview_candidates(db: Session, limit: int) -> List[Candidate]:
    """Latest published row per ``generator_name`` (source), newest first.

    Uses ``row_number()`` so we return up to ``limit`` distinct sources without
    scanning an arbitrary row cap in Python.
    """
    row_num = func.row_number().over(
        partition_by=Candidate.generator_name,
        order_by=(Candidate.published_at.desc(), Candidate.id.desc()),
    ).label("rn")
    ranked = (
        select(Candidate.id, row_num)
        .where(
            Candidate.status == CandidateQueueState.PUBLISHED,
            Candidate.published_at.isnot(None),
        )
        .subquery()
    )
    stmt = (
        select(Candidate)
        .join(ranked, Candidate.id == ranked.c.id)
        .where(ranked.c.rn == 1)
        .order_by(Candidate.published_at.desc(), Candidate.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


@router.get("/published")
def list_published_picks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Return published candidates; free tier receives one preview per source."""
    decision = EntitlementService.check(db, user, "picks.feed_full")
    is_preview = not decision.allowed

    if is_preview:
        rows = _preview_candidates(db, limit)
    else:
        rows = (
            db.query(Candidate)
            .filter(
                Candidate.status == CandidateQueueState.PUBLISHED,
                Candidate.published_at.isnot(None),
            )
            .order_by(Candidate.published_at.desc(), Candidate.id.desc())
            .limit(limit)
            .all()
        )

    return {
        "items": [_serialize_public(c) for c in rows],
        "is_preview": is_preview,
    }
