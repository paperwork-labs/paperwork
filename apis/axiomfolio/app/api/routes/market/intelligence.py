"""
Intelligence Routes
===================

Endpoints for intelligence briefs (daily, weekly, monthly).
"""

from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.dependencies import get_market_data_viewer
from app.models.market_data import JobRun
from app.models.user import User

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _brief_summary(meta: dict) -> dict:
    """Extract a compact summary from brief metadata."""
    return {
        "regime_state": meta.get("regime", {}).get("state"),
        "snapshot_count": meta.get("snapshot_count"),
        "as_of": meta.get("as_of"),
        "transitions": len(meta.get("stage_transitions", [])),
    }


@router.get("/briefs")
def list_intelligence_briefs(
    brief_type: Optional[str] = Query(None, description="daily, weekly, or monthly"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, description="Number of briefs to skip for pagination"),
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
):
    """List stored intelligence briefs."""
    q = db.query(JobRun).filter(JobRun.task_name.like("intelligence_%_brief"))
    if brief_type:
        q = q.filter(JobRun.task_name == f"intelligence_{brief_type}_brief")
    rows = q.order_by(JobRun.finished_at.desc().nullslast()).offset(offset).limit(limit).all()
    return {
        "briefs": [
            {
                "id": r.id,
                "type": r.task_name.replace("intelligence_", "").replace("_brief", ""),
                "status": r.status,
                "generated_at": r.finished_at.isoformat() if r.finished_at else None,
                "summary": _brief_summary(r.result_meta) if r.result_meta else None,
            }
            for r in rows
        ]
    }


@router.get("/briefs/{brief_id}")
def get_intelligence_brief(
    brief_id: int,
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
):
    """Get a specific intelligence brief by ID."""
    row = (
        db.query(JobRun)
        .filter(JobRun.id == brief_id, JobRun.task_name.like("intelligence_%_brief"))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Brief not found")
    return {
        "brief": row.result_meta,
        "id": row.id,
        "type": row.task_name.replace("intelligence_", "").replace("_brief", ""),
        "generated_at": row.finished_at.isoformat() if row.finished_at else None,
    }


@router.get("/latest")
def get_latest_brief(
    brief_type: str = Query("daily", description="daily, weekly, or monthly"),
    db: Session = Depends(get_db),
    _viewer: User = Depends(get_market_data_viewer),
):
    """Get the most recent brief of a given type."""
    row = (
        db.query(JobRun)
        .filter(JobRun.task_name == f"intelligence_{brief_type}_brief", JobRun.status == "ok")
        .order_by(JobRun.finished_at.desc().nullslast())
        .first()
    )
    if not row or not row.result_meta:
        return {"brief": None, "message": f"No {brief_type} brief available"}
    return {
        "brief": row.result_meta,
        "id": row.id,
        "generated_at": row.finished_at.isoformat() if row.finished_at else None,
    }
