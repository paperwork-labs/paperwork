"""Today's trade candidates (ranked by pick quality score)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user
from backend.database import get_db
from backend.models.picks import Candidate
from backend.models.user import User

router = APIRouter()


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _serialize_today_row(c: Candidate) -> Dict[str, Any]:
    breakdown = c.pick_quality_breakdown
    score_payload: Optional[Dict[str, Any]] = None
    if breakdown is not None:
        score_payload = {
            "total_score": breakdown.get("total_score"),
            "components": breakdown.get("components"),
            "regime_multiplier": breakdown.get("regime_multiplier"),
            "computed_at": breakdown.get("computed_at"),
        }
    return {
        "id": c.id,
        "ticker": c.symbol,
        "action": c.action_suggestion.value.upper(),
        "generator_name": c.generator_name,
        "generator_version": c.generator_version,
        "generator_score": str(c.score) if c.score is not None else None,
        "pick_quality_score": (
            str(c.pick_quality_score) if c.pick_quality_score is not None else None
        ),
        "score": score_payload,
        "thesis": c.rationale_summary,
        "signals": c.signals,
        "generated_at": c.generated_at.isoformat() if c.generated_at else None,
    }


@router.get("/candidates/today")
def list_candidates_today(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Return today's system-generated candidates, highest pick quality first."""
    start = _today_utc_start()
    base_filter = (Candidate.generated_at >= start,)
    total = (
        db.query(func.count(Candidate.id)).filter(*base_filter).scalar() or 0
    )
    rows: List[Candidate] = (
        db.query(Candidate)
        .filter(*base_filter)
        .order_by(
            Candidate.pick_quality_score.desc().nullslast(),
            Candidate.score.desc().nullslast(),
            Candidate.id.desc(),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )
    return {
        "items": [_serialize_today_row(c) for c in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
