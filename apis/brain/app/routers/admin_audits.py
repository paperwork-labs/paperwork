"""Admin router — Brain audit registry and run management.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import app.services.audits as audits_svc
from app.schemas.base import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/audits", tags=["admin-audits"])

_VALID_CADENCES = frozenset({"weekly", "monthly", "quarterly"})


class CadenceOverrideRequest(BaseModel):
    cadence: str


@router.get("")
def list_audits() -> Any:
    """List all audit definitions with last run state."""
    defs = audits_svc.load_registry()
    all_runs = audits_svc.load_runs()
    latest_by_id: dict[str, Any] = {}
    for run in all_runs:
        prev = latest_by_id.get(run.audit_id)
        if prev is None or run.ran_at > prev["ran_at_dt"]:
            latest_by_id[run.audit_id] = {
                "ran_at_dt": run.ran_at,
                "dump": run.model_dump(),
            }

    result = []
    for d in defs:
        last_info = latest_by_id.get(d.id)
        result.append(
            {
                **d.model_dump(),
                "last_run": last_info["dump"] if last_info else None,
            }
        )
    return success_response(result)


@router.post("/{audit_id}/run")
def trigger_run(audit_id: str) -> Any:
    """Trigger a manual audit run."""
    defn = audits_svc.get_audit_def(audit_id)
    if defn is None:
        raise HTTPException(status_code=404, detail=f"audit not found: {audit_id}")
    try:
        run = audits_svc.run_audit(audit_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(run.model_dump())


@router.get("/{audit_id}/runs")
def list_runs(
    audit_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Any:
    """Paginated audit run history for a single audit."""
    defn = audits_svc.get_audit_def(audit_id)
    if defn is None:
        raise HTTPException(status_code=404, detail=f"audit not found: {audit_id}")
    runs = audits_svc.load_runs_for(audit_id)
    runs_sorted = sorted(runs, key=lambda r: r.ran_at, reverse=True)
    offset = (page - 1) * page_size
    page_items = runs_sorted[offset : offset + page_size]
    return success_response(
        {
            "total": len(runs_sorted),
            "page": page,
            "page_size": page_size,
            "items": [r.model_dump() for r in page_items],
        }
    )


@router.put("/{audit_id}/cadence")
def override_cadence(audit_id: str, body: CadenceOverrideRequest) -> Any:
    """Manually override the cadence for an audit."""
    defn = audits_svc.get_audit_def(audit_id)
    if defn is None:
        raise HTTPException(status_code=404, detail=f"audit not found: {audit_id}")
    if body.cadence not in _VALID_CADENCES:
        raise HTTPException(status_code=422, detail=f"invalid cadence: {body.cadence}")
    try:
        audits_svc.set_audit_cadence(
            audit_id,
            body.cadence,  # type: ignore[arg-type]
            manual=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return success_response(
        {"audit_id": audit_id, "cadence": body.cadence, "manual_override": True}
    )


@router.get("/freshness")
def get_freshness() -> Any:
    """POS pillar value for audit_freshness."""
    score, measured, notes = audits_svc.audit_freshness()
    return success_response({"score": score, "measured": measured, "notes": notes})
