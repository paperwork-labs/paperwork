"""Conviction pick read API.

Returns the current user's latest ranked conviction-pick batch (the
most recent ``generated_at`` timestamp — every row in that batch is
served in rank order).

Read-only: writes are owned by the nightly Celery task
``app.tasks.market.conviction.generate_conviction_picks``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.conviction_pick import ConvictionPick
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


def _serialize(row: ConvictionPick) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "rank": row.rank,
        "score": str(row.score) if row.score is not None else None,
        "stage_label": row.stage_label,
        "rationale": row.rationale,
        "breakdown": row.score_breakdown,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "generator_version": row.generator_version,
    }


@router.get("/conviction")
def list_conviction_picks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Return the caller's latest ranked conviction pick batch."""
    latest_generated_at: Any | None = (
        db.query(func.max(ConvictionPick.generated_at))
        .filter(ConvictionPick.user_id == current_user.id)
        .scalar()
    )
    if latest_generated_at is None:
        return {
            "items": [],
            "total": 0,
            "generated_at": None,
            "generator_version": None,
        }

    rows: list[ConvictionPick] = (
        db.query(ConvictionPick)
        .filter(
            ConvictionPick.user_id == current_user.id,
            ConvictionPick.generated_at == latest_generated_at,
        )
        .order_by(ConvictionPick.rank.asc())
        .limit(limit)
        .all()
    )
    return {
        "items": [_serialize(r) for r in rows],
        "total": len(rows),
        "generated_at": latest_generated_at.isoformat(),
        "generator_version": rows[0].generator_version if rows else None,
    }
