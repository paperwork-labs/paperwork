"""Read-only admin JSON for Studio Brain Self-improvement (WS-69 PR G)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

import app.services.self_merge_gate as self_merge_gate
import app.services.self_prioritization as self_prioritization_svc
from app.database import get_db
from app.models.scheduler_run import SchedulerRun
from app.routers.admin import _require_admin
from app.schedulers.introspect import list_apscheduler_jobs
from app.schemas.base import success_response
from app.schemas.pr_outcomes import PrOutcome  # noqa: TC001
from app.services import pr_outcomes as pr_outcomes_service
from app.services import self_improvement as self_improvement_svc
from app.services.procedural_memory import load_rules

router = APIRouter(prefix="/admin/self-improvement", tags=["admin-self-improvement"])

_GRADUATION_N = 50

OutcomeBucket = Literal[
    "reverted",
    "7d_still_passing",
    "24h_still_passing",
    "1h_pass",
    "pending_observation",
]


def _pr_outcome_bucket(row: PrOutcome) -> OutcomeBucket:
    oc = row.outcomes
    h1 = oc.h1
    h24 = oc.h24
    if h1 is not None and h1.reverted:
        return "reverted"
    if h24 is not None and h24.reverted:
        return "reverted"
    if h24 is not None and h24.ci_pass and not h24.reverted:
        if oc.d7 is not None:
            return "7d_still_passing"
        return "24h_still_passing"
    if h1 is not None and h1.ci_pass and not h1.reverted:
        return "1h_pass"
    return "pending_observation"


@router.get("/learning-state")
async def get_learning_state(_auth: None = Depends(_require_admin)) -> Any:
    """WS-64 workstream candidate funnel from ``workstream_candidates.json``."""
    try:
        file = self_prioritization_svc.load_candidates_file()
    except (OSError, ValueError, ValidationError) as exc:
        return success_response(
            {
                "ok": False,
                "error": str(exc),
                "open_candidates": 0,
                "accepted_candidates": 0,
                "declined_candidates": 0,
                "superseded_candidates": 0,
                "conversion_rate": None,
                "generated_at": None,
            }
        )

    open_c = [c for c in file.candidates if c.status == "proposed"]
    hist = file.history
    accepted = sum(1 for c in hist if c.status == "approved_to_workstream")
    declined = sum(1 for c in hist if c.status == "rejected")
    superseded = sum(1 for c in hist if c.status == "superseded")
    denom = accepted + declined
    rate = round(100.0 * accepted / denom, 2) if denom else None

    return success_response(
        {
            "ok": True,
            "error": None,
            "generated_at": file.generated_at.isoformat() if file.generated_at else None,
            "open_candidates": len(open_c),
            "accepted_candidates": accepted,
            "declined_candidates": declined,
            "superseded_candidates": superseded,
            "conversion_rate": rate,
        }
    )


@router.get("/promotions")
async def get_promotions(_auth: None = Depends(_require_admin)) -> Any:
    """Self-merge tier + progress (extends ``/admin/self-merge-status`` fields)."""
    data = self_merge_gate.load_promotions_file()
    recent_merges = sorted(data.merges, key=lambda row: row.merged_at, reverse=True)[:10]
    recent_reverts = sorted(data.reverts, key=lambda row: row.reverted_at, reverse=True)[:5]
    clean = self_merge_gate.clean_merge_count()
    if data.current_tier == "app-code":
        progress_pct = 100.0
    else:
        progress_pct = min(100.0, round(100.0 * clean / _GRADUATION_N, 2))
    return success_response(
        {
            "current_tier": data.current_tier,
            "clean_merge_count": clean,
            "eligible_for_promotion": self_merge_gate.eligible_for_promotion(),
            "progress_to_next_tier_pct": progress_pct,
            "merges_required_for_next_tier": _GRADUATION_N,
            "recent_merges_last_10": [r.model_dump(mode="json") for r in recent_merges],
            "recent_reverts_last_5": [r.model_dump(mode="json") for r in recent_reverts],
            "graduation_rules_doc_slug": "brain-self-merge-graduation",
        }
    )


@router.get("/outcomes")
async def get_outcomes(
    limit: int = Query(200, ge=1, le=500),
    _auth: None = Depends(_require_admin),
) -> Any:
    """PR outcomes grouped by coarse health bucket, sorted by merge recency."""
    rows = pr_outcomes_service.list_pr_outcomes_for_query(workstream_id=None, limit=limit)
    buckets: dict[str, list[dict[str, Any]]] = {
        "reverted": [],
        "7d_still_passing": [],
        "24h_still_passing": [],
        "1h_pass": [],
        "pending_observation": [],
    }
    for row in sorted(rows, key=lambda r: r.merged_at, reverse=True):
        b = _pr_outcome_bucket(row)
        buckets[b].append(row.model_dump(mode="json"))
    return success_response(
        {
            "limit": limit,
            "count": len(rows),
            "buckets": buckets,
        }
    )


@router.get("/retros")
async def get_retros(
    limit: int = Query(12, ge=1, le=52),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Latest weekly retros (newest first)."""
    rows = self_improvement_svc.latest_retros(limit)
    return success_response(
        {
            "limit": limit,
            "count": len(rows),
            "retros": [r.model_dump(mode="json") for r in rows],
        }
    )


@router.get("/automation-state")
async def get_automation_state(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
) -> Any:
    """APScheduler jobs plus last persisted run from ``agent_scheduler_runs`` (when present)."""
    jobs = list_apscheduler_jobs()
    if not jobs:
        return success_response(
            {
                "scheduler_running": False,
                "jobs": [],
                "note": (
                    "No in-process scheduler jobs (BRAIN_SCHEDULER_ENABLED=false or not started)."
                ),
            }
        )

    ids = [j["id"] for j in jobs]
    stmt = (
        select(SchedulerRun)
        .where(SchedulerRun.job_id.in_(ids))
        .order_by(SchedulerRun.finished_at.desc())
    )
    scan = (await db.execute(stmt)).scalars().all()
    latest: dict[str, SchedulerRun] = {}
    for row in scan:
        if row.job_id not in latest:
            latest[row.job_id] = row

    merged: list[dict[str, Any]] = []
    for j in jobs:
        rid = j["id"]
        lr = latest.get(rid)
        merged.append(
            {
                **j,
                "last_run_at": lr.finished_at.isoformat() if lr else None,
                "last_result": lr.status if lr else None,
                "last_error_preview": (lr.error_text[:400] + "…")
                if lr and lr.error_text and len(lr.error_text) > 400
                else (lr.error_text if lr else None),
            }
        )
    return success_response({"scheduler_running": True, "jobs": merged, "note": None})


@router.get("/procedural-memory")
async def get_procedural_memory(_auth: None = Depends(_require_admin)) -> Any:
    """Validated procedural rules for search/filter in Studio."""
    try:
        rules = load_rules()
    except FileNotFoundError:
        return success_response(
            {"count": 0, "rules": [], "error": "procedural_memory.yaml missing"},
        )
    except Exception as exc:
        return success_response({"count": 0, "rules": [], "error": str(exc)})
    payload = [r.model_dump(mode="json") for r in rules]
    applies = sorted({scope for r in rules for scope in r.applies_to})
    return success_response(
        {
            "count": len(payload),
            "rules": payload,
            "applies_to_values": applies,
            "error": None,
        },
    )


@router.get("/summary")
async def get_summary(_auth: None = Depends(_require_admin)) -> Any:
    """Light bundle for the index tab (tier, streak heuristic, spotlight rule)."""
    promos = self_merge_gate.load_promotions_file()
    clean = self_merge_gate.clean_merge_count()
    if promos.current_tier == "app-code":
        progress_pct = 100.0
    else:
        progress_pct = min(100.0, round(100.0 * clean / _GRADUATION_N, 2))

    streak_weeks = 0
    try:
        retros = self_improvement_svc.latest_retros(52)
        for retro in retros:
            s = retro.summary
            if s.pos_total_change > 0 and s.merges >= s.reverts:
                streak_weeks += 1
            else:
                break
    except (OSError, ValueError):
        streak_weeks = 0

    spotlight: dict[str, Any] | None = None
    try:
        rules = load_rules()
        if rules:
            spotlight_rule = max(rules, key=lambda r: r.learned_at)
            spotlight = {
                "id": spotlight_rule.id,
                "when": spotlight_rule.when[:240],
                "confidence": spotlight_rule.confidence,
                "note": "Most recently learned rule (no usage counter in v1).",
            }
    except (FileNotFoundError, ValueError):
        spotlight = None

    return success_response(
        {
            "current_tier": promos.current_tier,
            "clean_merge_count": clean,
            "progress_to_next_tier_pct": progress_pct,
            "positive_retro_streak_weeks": streak_weeks,
            "spotlight_rule": spotlight,
        }
    )
