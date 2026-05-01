import asyncio
import hmac
import json
import logging
import os
import subprocess
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.anomaly_detection as anomaly_detection_svc
import app.services.app_registry as app_registry_svc
import app.services.coach_preflight as coach_preflight_svc
import app.services.kg_validation as kg_validation_svc
import app.services.operating_score as operating_score_svc
import app.services.pr_outcomes as pr_outcomes_service
import app.services.self_improvement as self_improvement_svc
import app.services.self_merge_gate as self_merge_gate
import app.services.self_prioritization as self_prioritization_svc
import app.services.sprint_velocity as sprint_velocity_svc
from app.config import settings
from app.database import async_session_factory, get_db
from app.models.episode import Episode
from app.models.scheduler_run import SchedulerRun
from app.personas import list_specs as list_persona_specs
from app.schemas.base import success_response
from app.schemas.coach_preflight import CoachPreflightRequest, CoachPreflightResponse, CostPredict
from app.services import decommissions as decommissions_svc
from app.services import iac_drift
from app.services.auto_revert import list_incidents
from app.services.blitz_progress_poster import blitz_status_snapshot
from app.services.continuous_learning import (
    ingest_decisions,
    ingest_merged_prs,
    ingest_postmortems,
)
from app.services.github_actions_quota_monitor import latest_github_actions_quota_snapshots
from app.services.pr_merge_sweep import merge_ready_prs
from app.services.pr_review import review_pr, sweep_open_prs
from app.services.procedural_memory import load_rules
from app.services.render_quota_monitor import (
    build_render_quota_admin_data,
    latest_render_quota_snapshot,
)
from app.services.seed import ingest_docs, ingest_sprint_lessons
from app.services.strategic_objectives import objectives_summary as strategic_objectives_summary
from app.services.system_health import system_health_snapshot
from app.services.vercel_quota_monitor import latest_vercel_quota_snapshots

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


def _require_learning_dashboard() -> None:
    if not settings.BRAIN_LEARNING_DASHBOARD_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Brain learning dashboard disabled (BRAIN_LEARNING_DASHBOARD_ENABLED=false)",
        )


def _repo_root() -> str:
    return os.environ.get(
        "REPO_ROOT",
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    )


def _monorepo_root() -> Path:
    env = os.environ.get("REPO_ROOT", "").strip()
    if env:
        return Path(env)
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".cursor" / "rules").is_dir() and (candidate / "apis" / "brain").is_dir():
            return candidate
    msg = "Paperwork monorepo root not found"
    raise RuntimeError(msg)


@router.post("/seed")
async def trigger_seed_ingestion(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    count = await ingest_docs(db, _repo_root())
    return success_response({"episodes_created": count})


@router.post("/seed-lessons")
async def trigger_sprint_lessons_ingestion(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Lift every sprint's `## What we learned` bullets into memory episodes.

    Idempotent — each lesson is keyed by SHA1 of its text under
    ``source = "sprint:lessons"``, so re-runs only insert new lessons.

    Driven on demand from CI (``scripts/ingest_sprint_lessons.py`` after a
    sprint markdown change merges) and on a 6-hour cadence by Brain's own
    scheduler (``app/schedulers/sprint_lessons.py``).
    """
    report = await ingest_sprint_lessons(db, _repo_root())
    return success_response(report)


class IngestOptionalBody(BaseModel):
    dry_run: bool = False
    limit: int | None = None


class RejectWorkstreamCandidateRequest(BaseModel):
    founder_reason: str = Field(..., min_length=1, max_length=500)


@router.post("/ingest-merged-prs")
async def trigger_merged_prs_ingestion(
    body: IngestOptionalBody | None = None,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Continuous learning: recently merged PRs (``source=merged_pr``)."""
    opts = body or IngestOptionalBody()
    report = await ingest_merged_prs(
        db,
        _repo_root(),
        dry_run=opts.dry_run,
        limit=opts.limit,
    )
    return success_response(report)


@router.post("/ingest-decisions")
async def trigger_decisions_ingestion(
    body: IngestOptionalBody | None = None,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Continuous learning: ADR-style decision docs (``source=decision``)."""
    opts = body or IngestOptionalBody()
    report = await ingest_decisions(
        db,
        _repo_root(),
        dry_run=opts.dry_run,
        limit=opts.limit,
    )
    return success_response(report)


@router.post("/ingest-postmortems")
async def trigger_postmortems_ingestion(
    body: IngestOptionalBody | None = None,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Continuous learning: sprint postmortems + runbook incidents (``source=postmortem``)."""
    opts = body or IngestOptionalBody()
    report = await ingest_postmortems(
        db,
        _repo_root(),
        dry_run=opts.dry_run,
        limit=opts.limit,
    )
    return success_response(report)


@router.get("/quota/github-actions")
async def get_github_actions_quota_snapshots(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Latest GitHub Actions billing/cache snapshots (Studio / infra dashboards)."""
    rows = await latest_github_actions_quota_snapshots(db)
    batch_at = rows[0].recorded_at.isoformat() if rows else None
    snapshots = [
        {
            "id": r.id,
            "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
            "repo": r.repo,
            "is_public": r.is_public,
            "minutes_used": r.minutes_used,
            "minutes_limit": r.minutes_limit,
            "included_minutes": r.included_minutes,
            "paid_minutes_used": r.paid_minutes_used,
            "total_paid_minutes_used_breakdown": r.total_paid_minutes_used_breakdown or {},
            "minutes_used_breakdown": r.minutes_used_breakdown or {},
            "cache_size_bytes": r.cache_size_bytes,
            "cache_count": r.cache_count,
            "extra_json": r.extra_json or {},
        }
        for r in rows
    ]
    return success_response({"batch_at": batch_at, "count": len(snapshots), "snapshots": snapshots})


@router.get("/render-quota")
async def get_render_quota(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Latest Render pipeline quota snapshot (`GET /api/v1/admin/render-quota`)."""
    row = await latest_render_quota_snapshot(db)
    return success_response(build_render_quota_admin_data(row))


@router.get("/system-health")
async def system_health_summary(
    _auth: None = Depends(_require_admin),
):
    """Operator snapshot for Studio admin; WS-43 freshness + WS-45 pause flag."""
    return success_response(system_health_snapshot())


@router.get("/app-registry")
async def get_app_registry(
    _auth: None = Depends(_require_admin),
):
    """Return Brain's source-of-truth monorepo app registry summary."""
    registry = app_registry_svc.load_registry()
    summary = app_registry_svc.conformance_summary()
    return success_response(
        {
            "generated_at": registry.generated_at,
            "total": summary["total"],
            "by_type": summary["by_type"],
            "conformance_summary": summary,
            "apps_low_conformance": summary["low_conformance"],
        }
    )


@router.post("/app-registry/regenerate")
async def regenerate_app_registry(
    _auth: None = Depends(_require_admin),
):
    """Regenerate app_registry.json with pwl and return the fresh summary."""
    root = _monorepo_root()
    try:
        result = subprocess.run(
            ["pwl", "registry-build"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as exc:
        detail = f"pwl registry-build failed to start: {exc}"
        raise HTTPException(status_code=500, detail=detail) from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "pwl registry-build failed"
        raise HTTPException(status_code=500, detail=detail)

    registry = app_registry_svc.load_registry()
    summary = app_registry_svc.conformance_summary()
    return success_response(
        {
            "generated_at": registry.generated_at,
            "total": summary["total"],
            "by_type": summary["by_type"],
            "conformance_summary": summary,
            "apps_low_conformance": summary["low_conformance"],
        }
    )


@router.get("/drift-status")
async def drift_status(
    _auth: None = Depends(_require_admin),
):
    """Latest IaC drift detector summary and open reconcile alerts."""
    return success_response(
        {
            "latest_run": iac_drift.latest_run_summary(),
            "open_alerts": iac_drift.open_alerts(),
        }
    )


def _rfc3339_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/workstreams-board")
async def get_workstreams_board(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Return ``workstreams.json`` as Brain sees it on disk (loader cache bypass).

    Proxied by Studio ``GET /api/admin/workstreams`` for a live admin board without
    waiting for a Studio redeploy. Wraps the file with provenance metadata expected
    by ``WorkstreamsBoardBrainEnvelopeSchema`` in ``apps/studio/src/lib/workstreams/schema.ts``.
    """
    from app.schemas.workstream import workstreams_file_to_json_dict
    from app.services.workstreams_loader import load_workstreams_file

    generated = datetime.now(UTC)
    wb_stmt = (
        select(SchedulerRun.finished_at)
        .where(
            SchedulerRun.job_id == "workstream_progress_writeback",
            SchedulerRun.status == "success",
        )
        .order_by(SchedulerRun.finished_at.desc())
        .limit(1)
    )
    wb_row = (await db.execute(wb_stmt)).scalar_one_or_none()
    writeback_last = _rfc3339_utc_z(wb_row) if wb_row is not None else None

    file = load_workstreams_file(bypass_cache=True)
    payload = workstreams_file_to_json_dict(file)
    payload["generated_at"] = _rfc3339_utc_z(generated)
    payload["source"] = "brain-writeback"
    payload["ttl_seconds"] = 60
    payload["writeback_last_run_at"] = writeback_last
    return payload


@router.get("/pr-outcomes")
async def get_pr_outcomes(
    workstream_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    _auth: None = Depends(_require_admin),
):
    """List recorded PR merge outcomes (WS-62), optionally filtered by workstream id."""
    rows = pr_outcomes_service.list_pr_outcomes_for_query(
        workstream_id=workstream_id,
        limit=limit,
    )
    return success_response(
        {
            "workstream_id": workstream_id,
            "limit": limit,
            "count": len(rows),
            "outcomes": [r.model_dump(mode="json") for r in rows],
        }
    )


@router.get("/workstream-candidates")
async def get_workstream_candidates(
    _auth: None = Depends(_require_admin),
):
    """List Brain-generated workstream proposals awaiting founder review."""
    file = self_prioritization_svc.load_candidates_file()
    cutoff = datetime.now(UTC) - timedelta(days=30)
    history_last_30 = [row for row in file.history if row.proposed_at.astimezone(UTC) >= cutoff]
    top_5 = sorted(file.candidates, key=lambda row: row.score, reverse=True)[:5]
    return success_response(
        {
            "generated_at": file.generated_at,
            "count": len(file.candidates),
            "top_5": [row.model_dump(mode="json") for row in top_5],
            "history_last_30": [row.model_dump(mode="json") for row in history_last_30],
        }
    )


@router.post("/workstream-candidates/{candidate_id}/promote")
async def promote_workstream_candidate(
    candidate_id: str,
    _auth: None = Depends(_require_admin),
):
    """Promote one proposed Brain candidate into Studio workstreams.json."""
    try:
        result = self_prioritization_svc.promote_candidate(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success_response(jsonable_encoder(result.workstream))


@router.post("/workstream-candidates/{candidate_id}/reject")
async def reject_workstream_candidate(
    candidate_id: str,
    body: RejectWorkstreamCandidateRequest,
    _auth: None = Depends(_require_admin),
):
    """Reject one proposed Brain candidate with the founder's reason."""
    try:
        candidate = self_prioritization_svc.reject_candidate(candidate_id, body.founder_reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return success_response(jsonable_encoder(candidate.model_dump(mode="json")))


@router.get("/self-merge-status")
async def get_self_merge_status(
    _auth: None = Depends(_require_admin),
):
    """Current Brain self-merge graduation status (WS-44)."""
    data = self_merge_gate.load_promotions_file()
    recent_merges = sorted(data.merges, key=lambda row: row.merged_at, reverse=True)[:10]
    recent_reverts = sorted(data.reverts, key=lambda row: row.reverted_at, reverse=True)[:5]
    return success_response(
        {
            "current_tier": data.current_tier,
            "clean_merge_count": self_merge_gate.clean_merge_count(),
            "eligible_for_promotion": self_merge_gate.eligible_for_promotion(),
            "recent_merges_last_10": [r.model_dump(mode="json") for r in recent_merges],
            "recent_reverts_last_5": [r.model_dump(mode="json") for r in recent_reverts],
        }
    )


@router.post("/self-merge-promote")
async def post_self_merge_promote(
    _auth: None = Depends(_require_admin),
):
    """Founder override endpoint for the WS-44 self-merge promotion gate."""
    record = self_merge_gate.promote()
    if record is None:
        raise HTTPException(status_code=409, detail="Self-merge promotion gate is not eligible")
    return success_response(jsonable_encoder(record.model_dump(mode="json")))


@router.get("/incidents")
async def get_incidents(
    limit: int = Query(20, ge=1, le=500),
    _auth: None = Depends(_require_admin),
):
    """List recent Brain operational incidents."""
    rows = list_incidents(limit=limit)
    return success_response(
        {
            "limit": limit,
            "count": len(rows),
            "incidents": [r.model_dump(mode="json") for r in rows],
        }
    )


@router.get("/vercel-quota")
async def get_vercel_quota_snapshots(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Latest Vercel quota snapshot batch (Studio / infra dashboards)."""
    rows = await latest_vercel_quota_snapshots(db)
    batch_at = rows[0].created_at.isoformat() if rows else None
    snapshots = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "project_id": r.project_id,
            "project_name": r.project_name,
            "window_days": r.window_days,
            "deploy_count": r.deploy_count,
            "build_minutes": r.build_minutes,
            "source_breakdown": r.source_breakdown or {},
            "meta": r.meta or {},
        }
        for r in rows
    ]
    return success_response({"batch_at": batch_at, "count": len(snapshots), "snapshots": snapshots})


@router.get("/personas")
async def list_personas(
    _auth: None = Depends(_require_admin),
):
    """Return the PersonaSpec registry so Studio can render /admin/agents."""
    specs = list_persona_specs()
    return success_response(
        {
            "count": len(specs),
            "personas": [spec.model_dump() for spec in specs],
        }
    )


def _agent_dispatch_log_path() -> Path:
    env = os.environ.get("BRAIN_AGENT_DISPATCH_LOG_JSON", "").strip()
    if env:
        return Path(env)
    return _monorepo_root() / "apis" / "brain" / "data" / "agent_dispatch_log.json"


@router.get("/agent-dispatch-log")
async def get_agent_dispatch_log(
    limit: int = Query(100, ge=1, le=500),
    since: str | None = Query(
        None,
        description="ISO-8601 lower bound for dispatched_at (inclusive)",
    ),
    _auth: None = Depends(_require_admin),
):
    """Recent persona dispatch rows from ``agent_dispatch_log.json`` (newest first)."""

    def _load() -> tuple[list[dict[str, Any]], str]:
        log_path = _agent_dispatch_log_path()
        if not log_path.is_file():
            return [], str(log_path)
        try:
            raw = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot read dispatch log: {exc}") from exc
        dispatches = raw.get("dispatches") if isinstance(raw, dict) else None
        if not isinstance(dispatches, list):
            return [], str(log_path)
        rows = [d for d in dispatches if isinstance(d, dict)]
        rows.sort(
            key=lambda d: str(d.get("dispatched_at") or ""),
            reverse=True,
        )
        if since:
            rows = [r for r in rows if str(r.get("dispatched_at") or "") >= since]
        return rows[:limit], str(log_path)

    try:
        rows, src = await asyncio.to_thread(_load)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return success_response({"dispatches": rows, "count": len(rows), "source_path": src})


def _load_dispatch_rows_all(max_rows: int = 10_000) -> tuple[list[dict[str, Any]], str]:
    """Read dispatch log entries (newest first), capped for aggregation."""

    log_path = _agent_dispatch_log_path()
    if not log_path.is_file():
        return [], str(log_path)
    try:
        raw = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], str(log_path)
    dispatches = raw.get("dispatches") if isinstance(raw, dict) else None
    if not isinstance(dispatches, list):
        return [], str(log_path)
    rows = [d for d in dispatches if isinstance(d, dict)]
    rows.sort(key=lambda d: str(d.get("dispatched_at") or ""), reverse=True)
    return rows[:max_rows], str(log_path)


def _dispatch_success_flag(row: dict[str, Any]) -> bool | None:
    outcome = row.get("outcome")
    if not isinstance(outcome, dict):
        return None
    merged_at = outcome.get("merged_at")
    if not merged_at:
        return None
    return outcome.get("reverted") is not True


@router.get("/persona-dispatch-summary")
async def get_persona_dispatch_summary(
    _auth: None = Depends(_require_admin),
):
    """Roll-up of dispatch counts and success signals per persona (Studio personas page)."""

    def _build() -> dict[str, Any]:
        rows, src = _load_dispatch_rows_all()
        since_cutoff = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        recent_cutoff_rows = [r for r in rows if str(r.get("dispatched_at") or "") >= since_cutoff]

        by_persona: dict[str, dict[str, Any]] = {}
        for r in rows:
            slug = str(r.get("persona_slug") or r.get("persona") or "unknown").strip() or "unknown"
            bucket = by_persona.setdefault(
                slug,
                {
                    "persona_slug": slug,
                    "dispatch_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "pending_outcome_count": 0,
                    "last_dispatch_at": None,
                    "recent_dispatch_count_30d": 0,
                },
            )
            bucket["dispatch_count"] += 1
            flag = _dispatch_success_flag(r)
            if flag is True:
                bucket["success_count"] += 1
            elif flag is False:
                bucket["failure_count"] += 1
            else:
                bucket["pending_outcome_count"] += 1
            ts = str(r.get("dispatched_at") or "")
            if ts and (bucket["last_dispatch_at"] is None or ts > bucket["last_dispatch_at"]):
                bucket["last_dispatch_at"] = ts

        for r in recent_cutoff_rows:
            slug = str(r.get("persona_slug") or r.get("persona") or "unknown").strip() or "unknown"
            if slug in by_persona:
                by_persona[slug]["recent_dispatch_count_30d"] += 1

        personas_out: list[dict[str, Any]] = []
        for _slug, b in by_persona.items():
            resolved = b["success_count"] + b["failure_count"]
            success_rate = round(b["success_count"] / resolved, 4) if resolved else None
            personas_out.append(
                {
                    **b,
                    "success_rate": success_rate,
                }
            )
        personas_out.sort(key=lambda x: x["dispatch_count"], reverse=True)

        tail = sorted(rows, key=lambda d: str(d.get("dispatched_at") or ""), reverse=True)[:15]
        recent_activity = [
            {
                "dispatched_at": d.get("dispatched_at"),
                "persona_slug": d.get("persona_slug") or d.get("persona"),
                "workstream_id": d.get("workstream_id"),
                "task_summary": d.get("task_summary"),
                "outcome": d.get("outcome"),
            }
            for d in tail
        ]

        return {
            "source_path": src,
            "window_days": 30,
            "dispatch_total": len(rows),
            "personas": personas_out,
            "recent_activity": recent_activity,
            "notes": (
                "success_rate counts resolved merges only (merged_at set, not reverted); "
                "pending_outcome_count covers open dispatches."
            ),
        }

    payload = await asyncio.to_thread(_build)
    return success_response(payload)


@router.get("/blitz-status")
async def get_blitz_status(
    _auth: None = Depends(_require_admin),
):
    """Current cheap-agent blitz queue state plus markdown hourly summary."""
    snapshot = blitz_status_snapshot()
    return {
        "queue_depth": snapshot.queue_depth,
        "current": snapshot.current,
        "last_complete": snapshot.last_complete,
        "hourly_summary": snapshot.hourly_summary,
    }


class PRSweepRequest(BaseModel):
    organization_id: str = Field("paperwork-labs")
    limit: int = Field(30, ge=1, le=100)
    force: bool = Field(
        False,
        description="Re-review PRs even if an episode already exists at the current head SHA.",
    )


@router.post("/pr-sweep")
async def trigger_pr_sweep(
    background_tasks: BackgroundTasks,
    body: PRSweepRequest | None = None,
    _auth: None = Depends(_require_admin),
):
    """Kick off Brain's self-driven PR review sweep.

    Brain uses its own GitHub tools + memory to decide which PRs need a fresh
    review. Returns 202; sweep runs in the background with a fresh DB session.
    """
    req = body or PRSweepRequest()

    async def _run() -> None:
        async with async_session_factory() as session:
            try:
                report = await sweep_open_prs(
                    session,
                    org_id=req.organization_id,
                    limit=req.limit,
                    force=req.force,
                )
                logger.info(
                    "pr-sweep complete: reviewed=%d skipped=%d errors=%d",
                    len(report.get("reviewed") or []),
                    len(report.get("skipped") or []),
                    len(report.get("errors") or []),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("pr-sweep failed")

    background_tasks.add_task(_run)
    return success_response({"accepted": True, "org_id": req.organization_id})


class PRReviewOneRequest(BaseModel):
    pr_number: int = Field(..., gt=0)
    organization_id: str = Field("paperwork-labs")


@router.post("/pr-review")
async def trigger_single_pr_review(
    body: PRReviewOneRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(_require_admin),
):
    """Review one specific PR now. Used when you want Brain to weigh in on a PR
    out-of-band (e.g. a major Dependabot bump with ``dependencies`` labels Brain
    would otherwise skip)."""

    async def _run(pr_number: int, org_id: str) -> None:
        async with async_session_factory() as session:
            try:
                result = await review_pr(session, pr_number=pr_number, org_id=org_id)
                logger.info(
                    "pr-review complete: #%s verdict=%s posted=%s",
                    pr_number,
                    result.get("verdict"),
                    result.get("posted"),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("pr-review failed for #%s", pr_number)

    background_tasks.add_task(_run, body.pr_number, body.organization_id)
    return success_response({"accepted": True, "pr_number": body.pr_number})


@router.post("/pr-merge-sweep")
async def trigger_pr_merge_sweep(
    _auth: None = Depends(_require_admin),
):
    """Squash-merge every open PR that is approved + green + mergeable.

    Runs synchronously (small budget, no LLM calls) so callers get the
    report back immediately.
    """
    report = await merge_ready_prs(limit=50)
    return success_response(report)


@router.get("/memory/episodes")
async def list_memory_episodes(
    source_prefix: str | None = Query(
        None,
        description=(
            "Filter episodes whose `source` starts with this prefix (e.g. `brain:pr-review`)."
        ),
    ),
    organization_id: str = Query("paperwork-labs"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Read recent episodes for dashboard consumers (Studio /admin/overview).

    Deliberately read-only and flat. Callers that need semantic search use the
    MCP tool ``search_memory`` — this endpoint is the "last 50 rows by source"
    utility.
    """
    stmt = select(Episode).where(Episode.organization_id == organization_id)
    if source_prefix:
        stmt = stmt.where(Episode.source.like(f"{source_prefix}%"))
    stmt = stmt.order_by(Episode.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    episodes = [
        {
            "id": ep.id,
            "source": ep.source,
            "source_ref": ep.source_ref,
            "channel": ep.channel,
            "persona": ep.persona,
            "product": ep.product,
            "summary": ep.summary,
            "importance": ep.importance,
            "metadata": ep.metadata_ or {},
            "model_used": ep.model_used,
            "tokens_in": ep.tokens_in,
            "tokens_out": ep.tokens_out,
            "user_id": ep.user_id,
            "created_at": ep.created_at.isoformat() if ep.created_at else None,
        }
        for ep in rows
    ]
    return success_response({"count": len(episodes), "episodes": episodes})


@router.get("/memory-stats")
async def get_memory_stats(
    organization_id: str = Query("paperwork-labs"),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Aggregate episode counts and a coarse storage estimate for Studio overview."""

    total_stmt = select(func.count(Episode.id)).where(Episode.organization_id == organization_id)
    total_episodes = int((await db.execute(total_stmt)).scalar_one() or 0)

    by_src_stmt = (
        select(Episode.source, func.count(Episode.id))
        .where(Episode.organization_id == organization_id)
        .group_by(Episode.source)
    )
    by_src_rows = (await db.execute(by_src_stmt)).all()
    by_src_rows.sort(key=lambda row: int(row[1] or 0), reverse=True)
    top_sources = [{"source": row[0], "count": int(row[1])} for row in by_src_rows[:50]]
    top_count = sum(r["count"] for r in top_sources)
    other_sources_episode_count = max(0, total_episodes - top_count)

    cutoff_30 = datetime.now(UTC) - timedelta(days=30)
    cnt_30_stmt = select(func.count(Episode.id)).where(
        Episode.organization_id == organization_id,
        Episode.created_at >= cutoff_30,
    )
    episodes_last_30_days = int((await db.execute(cnt_30_stmt)).scalar_one() or 0)
    average_per_day_trailing_30 = round(episodes_last_30_days / 30.0, 4)

    text_stmt = select(
        func.coalesce(func.sum(func.char_length(Episode.summary)), 0),
        func.coalesce(func.sum(func.char_length(Episode.full_context)), 0),
        func.sum(case((Episode.embedding.is_not(None), 1536 * 4), else_=0)),
    ).where(Episode.organization_id == organization_id)
    sum_summary, sum_full, emb_placeholder = (await db.execute(text_stmt)).one()
    text_bytes = int(sum_summary or 0) + int(sum_full or 0)
    embedding_assumed_bytes = int(emb_placeholder or 0)
    metadata_overhead = total_episodes * 512
    storage_estimate_bytes = text_bytes + embedding_assumed_bytes + metadata_overhead

    return success_response(
        {
            "organization_id": organization_id,
            "total_episodes": total_episodes,
            "episodes_by_source": top_sources,
            "other_sources_episode_count": other_sources_episode_count,
            "trailing_30_days": {
                "episode_count": episodes_last_30_days,
                "average_per_day": average_per_day_trailing_30,
            },
            "storage_estimate_bytes": storage_estimate_bytes,
            "storage_estimate_note": (
                "Coarse estimate: UTF-8 column lengths for summary/full_context, "
                "1536-dim embedding assumed 4 bytes/float when embedding present, "
                "plus fixed metadata overhead per row."
            ),
        }
    )


def _parse_iso_dt(raw: str) -> datetime:
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _utc_day_bounds(d: date_type) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _serialize_episode_row(ep: Episode) -> dict[str, Any]:
    return {
        "id": ep.id,
        "source": ep.source,
        "source_ref": ep.source_ref,
        "channel": ep.channel,
        "persona": ep.persona,
        "product": ep.product,
        "summary": ep.summary,
        "importance": ep.importance,
        "metadata": ep.metadata_ or {},
        "model_used": ep.model_used,
        "tokens_in": ep.tokens_in,
        "tokens_out": ep.tokens_out,
        "user_id": ep.user_id,
        "created_at": ep.created_at.isoformat() if ep.created_at else None,
    }


@router.get("/brain/episodes")
async def list_brain_learning_episodes(
    since: str = Query(..., description="ISO 8601 lower bound (UTC recommended)."),
    limit: int = Query(50, ge=1, le=200),
    persona: str | None = Query(None, description="Exact persona filter."),
    product: str | None = Query(
        None, description="Exact product filter (use empty to match null — omit for all)."
    ),
    organization_id: str = Query("paperwork-labs"),
    exclude_routing: bool = Query(
        True,
        description=(
            "If true (default), omit `source=model_router` rows (see `/admin/brain/decisions`)."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    """J2/J3: time-bounded episode rows for the Studio learning dashboard."""
    start_dt = _parse_iso_dt(since)
    stmt = select(Episode).where(
        Episode.organization_id == organization_id,
        Episode.created_at >= start_dt,
    )
    if exclude_routing:
        stmt = stmt.where(Episode.source != "model_router")
    if persona:
        stmt = stmt.where(Episode.persona == persona)
    if product is not None:
        if product == "":
            stmt = stmt.where(Episode.product.is_(None))
        else:
            stmt = stmt.where(Episode.product == product)
    stmt = stmt.order_by(Episode.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return success_response(
        {
            "count": len(rows),
            "episodes": [_serialize_episode_row(ep) for ep in rows],
        }
    )


@router.get("/brain/decisions")
async def list_brain_routing_decisions(
    since: str = Query(..., description="ISO 8601 lower bound."),
    limit: int = Query(100, ge=1, le=500),
    organization_id: str = Query("paperwork-labs"),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    """J2/J3: model routing / decision-quality rows (`source=model_router`)."""
    start_dt = _parse_iso_dt(since)
    stmt = (
        select(Episode)
        .where(
            Episode.organization_id == organization_id,
            Episode.source == "model_router",
            Episode.created_at >= start_dt,
        )
        .order_by(Episode.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    out: list[dict[str, Any]] = []
    for ep in rows:
        meta = ep.metadata_ or {}
        out.append(
            {
                "id": ep.id,
                "persona": ep.persona,
                "summary": ep.summary,
                "outcome": meta.get("outcome"),
                "model_used": ep.model_used,
                "tokens_in": ep.tokens_in,
                "tokens_out": ep.tokens_out,
                "created_at": ep.created_at.isoformat() if ep.created_at else None,
                "metadata": meta,
            }
        )
    return success_response({"count": len(out), "decisions": out})


@router.get("/brain/learning-summary")
async def brain_learning_summary(
    on_date: str | None = Query(
        None,
        alias="date",
        description="Anchor calendar day in UTC (YYYY-MM-DD). Defaults to today UTC.",
    ),
    spark_days: int = Query(
        14, ge=0, le=90, description="If >0, include daily series for the N days ending on `date`."
    ),
    organization_id: str = Query("paperwork-labs"),
    top_n: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
    _learning: None = Depends(_require_learning_dashboard),
):
    """J2/J3: aggregated counts, token totals, top importance, optional spark data."""
    if on_date:
        try:
            y, m, d = (int(p) for p in on_date.split("-", 2))
            anchor = date_type(y, m, d)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid date: {on_date!r} ({exc})"
            ) from exc
    else:
        anchor = datetime.now(UTC).date()

    day_start, day_end = _utc_day_bounds(anchor)

    # Episodes for the day excluding routing noise (align with `/brain/episodes` default)
    day_ep_stmt = select(Episode).where(
        Episode.organization_id == organization_id,
        Episode.created_at >= day_start,
        Episode.created_at < day_end,
        Episode.source != "model_router",
    )
    day_ep_result = await db.execute(day_ep_stmt)
    day_eps = day_ep_result.scalars().all()

    counts_map: dict[tuple[str | None, str | None], int] = {}
    for ep in day_eps:
        key = (ep.persona, ep.product)
        counts_map[key] = counts_map.get(key, 0) + 1
    counts_by_persona_product = [
        {
            "persona": p,
            "product": pr,
            "episode_count": c,
        }
        for (p, pr), c in sorted(counts_map.items(), key=lambda x: -x[1])
    ]

    top_rows = sorted(day_eps, key=lambda e: (e.importance, e.id or 0), reverse=True)[:top_n]
    top_by_importance = [_serialize_episode_row(ep) for ep in top_rows]

    # Token totals: all sources for the day (incl. model_router)
    tok_stmt = (
        select(
            Episode.model_used,
            func.coalesce(func.sum(Episode.tokens_in), 0),
            func.coalesce(func.sum(Episode.tokens_out), 0),
        )
        .where(
            Episode.organization_id == organization_id,
            Episode.created_at >= day_start,
            Episode.created_at < day_end,
        )
        .group_by(Episode.model_used)
    )
    tok_res = await db.execute(tok_stmt)
    model_token_totals = [
        {
            "model": row[0],
            "tokens_in": int(row[1] or 0),
            "tokens_out": int(row[2] or 0),
        }
        for row in tok_res.all()
    ]

    dec_stmt = (
        select(func.count())
        .select_from(Episode)
        .where(
            Episode.organization_id == organization_id,
            Episode.created_at >= day_start,
            Episode.created_at < day_end,
            Episode.source == "model_router",
        )
    )
    dec_count = int((await db.execute(dec_stmt)).scalar() or 0)

    day_stmt_tok = select(
        func.coalesce(func.sum(Episode.tokens_in), 0),
        func.coalesce(func.sum(Episode.tokens_out), 0),
    ).where(
        Episode.organization_id == organization_id,
        Episode.created_at >= day_start,
        Episode.created_at < day_end,
    )
    t_in, t_out = (await db.execute(day_stmt_tok)).one()
    t_in, t_out = int(t_in or 0), int(t_out or 0)

    spark: list[dict[str, Any]] = []
    if spark_days > 0:
        series_start_date = anchor - timedelta(days=spark_days - 1)
        range_start, _ = _utc_day_bounds(series_start_date)
        _, range_end = _utc_day_bounds(anchor)
        # Episode counts by UTC day
        day_bucket = func.date_trunc("day", Episode.created_at)
        e_stmt = (
            select(
                day_bucket.label("day"),
                func.count().label("n"),
            )
            .where(
                Episode.organization_id == organization_id,
                Episode.created_at >= range_start,
                Episode.created_at < range_end,
                Episode.source != "model_router",
            )
            .group_by(day_bucket)
        )
        e_map = {r[0].date() if r[0] else None: int(r[1]) for r in (await db.execute(e_stmt)).all()}
        d_stmt = (
            select(
                day_bucket.label("day"),
                func.count().label("n"),
            )
            .where(
                Episode.organization_id == organization_id,
                Episode.created_at >= range_start,
                Episode.created_at < range_end,
                Episode.source == "model_router",
            )
            .group_by(day_bucket)
        )
        d_map = {r[0].date() if r[0] else None: int(r[1]) for r in (await db.execute(d_stmt)).all()}
        for i in range(spark_days):
            d0 = series_start_date + timedelta(days=i)
            spark.append(
                {
                    "date": d0.isoformat(),
                    "episode_count": e_map.get(d0, 0),
                    "decision_count": d_map.get(d0, 0),
                }
            )

    return success_response(
        {
            "anchor_date": anchor.isoformat(),
            "day_start_utc": day_start.isoformat(),
            "day_end_utc": day_end.isoformat(),
            "counts_by_persona_product": counts_by_persona_product,
            "top_by_importance": top_by_importance,
            "model_token_totals": model_token_totals,
            "totals": {
                "episodes": len(day_eps),
                "routing_decisions": dec_count,
                "tokens_in": t_in,
                "tokens_out": t_out,
            },
            "spark": spark,
        }
    )


@router.get("/strategic-objectives")
async def get_strategic_objectives_summary(
    _auth: None = Depends(_require_admin),
):
    """Summary of ``docs/strategy/OBJECTIVES.yaml`` for Studio / ops dashboards."""
    return success_response(jsonable_encoder(strategic_objectives_summary()))


@router.get("/operating-score")
async def get_operating_score(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return latest POS snapshot + last week history tails for dashboards."""
    blob = operating_score_svc.read_operating_file()
    gate_payload = (
        blob.current.gates.model_dump(mode="json")
        if blob.current
        else {"l4_pass": False, "l5_pass": False, "lowest_pillar": ""}
    )
    payload = {
        "current": blob.current.model_dump(mode="json") if blob.current else None,
        "history_last_12": [h.model_dump(mode="json") for h in blob.history[-12:]],
        "gates": gate_payload,
    }
    return success_response(jsonable_encoder(payload))


@router.get("/operating-score/history")
async def get_operating_score_daily_history(
    days: int = Query(30, ge=1, le=90),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Daily POS series for Studio charts (forward-filled from weekly snapshots)."""

    blob = operating_score_svc.read_operating_file()
    entries: list[tuple[datetime, float]] = []
    for e in blob.history:
        try:
            entries.append((_parse_iso_dt(e.computed_at), float(e.total)))
        except Exception:
            continue
    if blob.current:
        with suppress(Exception):
            entries.append(
                (_parse_iso_dt(blob.current.computed_at), float(blob.current.total)),
            )
    entries.sort(key=lambda x: x[0])
    by_day: dict[date_type, float] = {}
    for dt, total in entries:
        by_day[dt.date()] = total
    sorted_known = sorted(by_day.keys())
    anchor = datetime.now(UTC).date()
    series: list[dict[str, Any]] = []
    for i in range(days - 1, -1, -1):
        day = anchor - timedelta(days=i)
        total: float | None = None
        for kd in reversed(sorted_known):
            if kd <= day:
                total = by_day[kd]
                break
        series.append({"date": day.isoformat(), "total": total})
    return success_response(
        {
            "days": days,
            "series": series,
            "source": "operating_score.json",
            "granularity": "daily_forward_fill",
        }
    )


@router.get("/cost-breakdown")
async def get_llm_cost_breakdown(
    organization_id: str = Query("paperwork-labs"),
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Token-derived LLM spend estimates by persona, model, and day (Studio infra cost tab).

    Uses conservative placeholder $/MTok rates until a unified LLM ledger lands.
    """

    in_usd_per_mtok = 3.0
    out_usd_per_mtok = 15.0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    base_where = (Episode.organization_id == organization_id, Episode.created_at >= cutoff)
    tok_sum = func.coalesce(Episode.tokens_in, 0) + func.coalesce(Episode.tokens_out, 0)

    persona_stmt = (
        select(
            func.coalesce(Episode.persona, "(unknown)").label("persona"),
            func.sum(func.coalesce(Episode.tokens_in, 0)),
            func.sum(func.coalesce(Episode.tokens_out, 0)),
        )
        .where(*base_where)
        .group_by(func.coalesce(Episode.persona, "(unknown)"))
        .order_by(func.sum(tok_sum).desc())
    )
    model_stmt = (
        select(
            func.coalesce(Episode.model_used, "(unknown)").label("model"),
            func.sum(func.coalesce(Episode.tokens_in, 0)),
            func.sum(func.coalesce(Episode.tokens_out, 0)),
        )
        .where(*base_where)
        .group_by(func.coalesce(Episode.model_used, "(unknown)"))
        .order_by(func.sum(tok_sum).desc())
    )
    day_stmt = (
        select(
            cast(Episode.created_at, Date).label("day"),
            func.sum(func.coalesce(Episode.tokens_in, 0)),
            func.sum(func.coalesce(Episode.tokens_out, 0)),
        )
        .where(*base_where)
        .group_by(cast(Episode.created_at, Date))
        .order_by(cast(Episode.created_at, Date))
    )

    persona_rows = (await db.execute(persona_stmt)).all()
    model_rows = (await db.execute(model_stmt)).all()
    day_rows = (await db.execute(day_stmt)).all()

    def _usd(t_in: int, t_out: int) -> float:
        return (t_in / 1_000_000.0) * in_usd_per_mtok + (t_out / 1_000_000.0) * out_usd_per_mtok

    by_persona = []
    total_in = 0
    total_out = 0
    total_usd = 0.0
    for persona, t_in, t_out in persona_rows:
        ti = int(t_in or 0)
        to = int(t_out or 0)
        u = round(_usd(ti, to), 6)
        total_in += ti
        total_out += to
        total_usd += u
        by_persona.append(
            {
                "persona": str(persona),
                "tokens_in": ti,
                "tokens_out": to,
                "estimated_usd": u,
            },
        )

    by_model = []
    for model, t_in, t_out in model_rows:
        ti = int(t_in or 0)
        to = int(t_out or 0)
        by_model.append(
            {
                "model": str(model),
                "tokens_in": ti,
                "tokens_out": to,
                "estimated_usd": round(_usd(ti, to), 6),
            }
        )

    by_day: list[dict[str, Any]] = []
    for day, t_in, t_out in day_rows:
        ti = int(t_in or 0)
        to = int(t_out or 0)
        if day is None:
            continue
        by_day.append(
            {
                "date": day.isoformat() if hasattr(day, "isoformat") else str(day),
                "tokens_in": ti,
                "tokens_out": to,
                "estimated_usd": round(_usd(ti, to), 6),
            }
        )

    return success_response(
        {
            "organization_id": organization_id,
            "window_days": days,
            "currency": "USD",
            "estimated": True,
            "pricing_note": (
                f"Blend placeholder: ${in_usd_per_mtok}/1M input tokens, "
                f"${out_usd_per_mtok}/1M output tokens from episode ledger rows."
            ),
            "by_persona": by_persona,
            "by_model": by_model,
            "by_day": by_day,
            "totals": {
                "tokens_in": total_in,
                "tokens_out": total_out,
                "estimated_usd": round(total_usd, 6),
            },
        }
    )


@router.get("/brain-fill-meter")
async def get_brain_fill_meter(
    organization_id: str = Query("paperwork-labs"),
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    """Tier utilization snapshot for episodic / procedural / semantic memory."""

    total_stmt = select(func.count(Episode.id)).where(Episode.organization_id == organization_id)
    embedded_stmt = select(func.count(Episode.id)).where(
        Episode.organization_id == organization_id,
        Episode.embedding.is_not(None),
    )
    total_episodes = int((await db.execute(total_stmt)).scalar_one() or 0)
    embedded_episodes = int((await db.execute(embedded_stmt)).scalar_one() or 0)

    rules = load_rules()
    procedural_rules = len(rules)

    episodic_capacity = 500_000
    procedural_capacity = 5_000
    semantic_embedding_target = max(total_episodes, 1)

    episodic_pct = round(min(100.0, (total_episodes / episodic_capacity) * 100.0), 2)
    procedural_pct = round(min(100.0, (procedural_rules / procedural_capacity) * 100.0), 2)
    semantic_pct = round(min(100.0, (embedded_episodes / semantic_embedding_target) * 100.0), 2)
    overall = round((episodic_pct + procedural_pct + semantic_pct) / 3.0, 2)

    return success_response(
        {
            "organization_id": organization_id,
            "overall_utilization_pct": overall,
            "tiers": {
                "episodic": {
                    "label": "Episodic (episode rows)",
                    "used_units": total_episodes,
                    "capacity_units": episodic_capacity,
                    "utilization_pct": episodic_pct,
                },
                "procedural": {
                    "label": "Procedural (YAML rules)",
                    "used_units": procedural_rules,
                    "capacity_units": procedural_capacity,
                    "utilization_pct": procedural_pct,
                },
                "semantic": {
                    "label": "Semantic (embedded episodes)",
                    "used_units": embedded_episodes,
                    "capacity_units": semantic_embedding_target,
                    "utilization_pct": semantic_pct,
                    "note": (
                        "Capacity mirrors live episode count; "
                        "embedding coverage vs corpus size."
                    ),
                },
            },
            "notes": (
                "Caps are planning defaults for Studio; tune when formal quotas exist."
            ),
        }
    )


@router.post("/operating-score/recompute")
async def post_operating_score_recompute(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Admin-only synchronous POS recomputation — persists snapshot like the weekly cron."""
    entry = operating_score_svc.compute_score()
    operating_score_svc.record_score(entry)
    return success_response(jsonable_encoder(entry.model_dump(mode="json")))


@router.get("/weekly-retros")
async def get_weekly_retros(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return Brain weekly retrospectives and a quarter summary."""
    retros = self_improvement_svc.latest_retros(52)
    latest_4 = retros[:4]
    quarter = retros[:13]
    avg_pos_change = (
        round(sum(row.summary.pos_total_change for row in quarter) / len(quarter), 4)
        if quarter
        else 0.0
    )
    payload = {
        "count": len(retros),
        "latest_4": [row.model_dump(mode="json") for row in latest_4],
        "summary_quarter": {
            "avg_pos_change": avg_pos_change,
            "total_merges": sum(row.summary.merges for row in quarter),
            "total_reverts": sum(row.summary.reverts for row in quarter),
        },
    }
    return success_response(jsonable_encoder(payload))


@router.get("/sprint-velocity")
async def get_sprint_velocity(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return latest sprint velocity snapshot + bounded history for dashboards."""
    blob = sprint_velocity_svc.read_velocity_file()
    payload = {
        "current": blob.current.model_dump(mode="json", by_alias=True) if blob.current else None,
        "history_last_12": [h.model_dump(mode="json", by_alias=True) for h in blob.history[-12:]],
    }
    return success_response(jsonable_encoder(payload))


@router.post("/sprint-velocity/recompute")
async def post_sprint_velocity_recompute(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Admin-only synchronous sprint velocity recomputation — persists like the weekly cron."""
    entry = sprint_velocity_svc.record_weekly_velocity()
    return success_response(jsonable_encoder(entry.model_dump(mode="json", by_alias=True)))


@router.post("/weekly-retros/recompute")
async def post_weekly_retros_recompute(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Admin-only synchronous weekly retro recomputation for the current UTC week ending."""
    retro = self_improvement_svc.compute_weekly_retro()
    self_improvement_svc.record_retro(retro)
    return success_response(jsonable_encoder(retro.model_dump(mode="json")))


@router.get("/anomaly-alerts")
async def get_anomaly_alerts(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return the latest anomaly alerts blob (WS-50)."""
    file = anomaly_detection_svc.read_alerts_file()
    open_alerts = [a for a in file.alerts if a.resolved_at is None]
    return success_response(
        {
            "schema": file.schema_,
            "total": len(file.alerts),
            "open": len(open_alerts),
            "alerts": [a.model_dump(mode="json") for a in file.alerts],
        }
    )


@router.get("/kg-validation")
async def get_kg_validation(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return the latest KG validation snapshot plus recent history (WS-52)."""
    file = kg_validation_svc.load_validation_file()
    return success_response(
        {
            "current": file.current.model_dump(mode="json") if file.current else None,
            "history_last_10": [h.model_dump(mode="json") for h in (file.history or [])[:10]],
            "passed": file.current.passed if file.current else None,
        }
    )


@router.post("/anomaly-alerts/recompute")
async def post_anomaly_alerts_recompute(
    background_tasks: BackgroundTasks,
    _auth: None = Depends(_require_admin),
) -> Any:
    """Trigger manual anomaly recompute + auto-resolve pass in the background (WS-50)."""

    def _run() -> None:
        try:
            anomaly_detection_svc.compute_anomalies()
            anomaly_detection_svc.auto_resolve_alerts()
        except Exception:
            logger.exception("anomaly-alerts/recompute background task raised")

    background_tasks.add_task(_run)
    return success_response({"accepted": True})


@router.post("/kg-validation/recompute")
async def post_kg_validation_recompute(
    background_tasks: BackgroundTasks,
    _auth: None = Depends(_require_admin),
) -> Any:
    """Trigger an immediate KG validation run in the background (WS-52)."""

    async def _run() -> None:
        try:
            run = await asyncio.to_thread(kg_validation_svc.validate)
            await asyncio.to_thread(kg_validation_svc.record_validation_run, run)
            logger.info(
                "kg-validation/recompute: passed=%s violations=%d",
                run.passed,
                len(run.violations),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("kg-validation/recompute background task failed")

    background_tasks.add_task(_run)
    return success_response({"accepted": True})


@router.get("/decommissions")
async def get_decommissions(
    status: str | None = Query(None, description="Filter by status: proposed | scheduled | done"),
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return decommissions.json entries (WS-48).

    Optionally filter by ``status`` (proposed | scheduled | done).
    Always bypasses the service cache for freshness.
    """
    entries = decommissions_svc.list_entries(status=status, bypass_cache=True)
    return success_response(
        {
            "count": len(entries),
            "status_filter": status,
            "entries": [e.model_dump(mode="json") for e in entries],
        }
    )


@router.get("/procedural-memory")
async def get_procedural_memory(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return all procedural rules for the admin dashboard.

    Reads ``apis/brain/data/procedural_memory.yaml`` on every call.
    ``last_consolidated_at`` is null until WS-64 writes it.
    """
    rules = load_rules()
    serialised = [
        {
            "id": r.id,
            "when": r.when,
            "do": r.do,
            "source": r.source,
            "learned_at": r.learned_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "confidence": r.confidence,
            "applies_to": list(r.applies_to),
        }
        for r in rules
    ]
    return success_response(
        {
            "rules": serialised,
            "count": len(serialised),
            "last_consolidated_at": None,
        }
    )


# ---------------------------------------------------------------------------
# WS-67.A — Coach preflight
# ---------------------------------------------------------------------------


@router.post("/coach/preflight", response_model=CoachPreflightResponse)
async def post_coach_preflight(
    body: CoachPreflightRequest,
    _auth: None = Depends(_require_admin),
) -> CoachPreflightResponse:
    """WS-67.A — Brain coach preflight.

    Surfaces relevant procedural rules, recent incidents, and cost predictions
    for Opus before non-trivial dispatches/merges.  Always returns 200; uses
    degraded mode on data errors so callers are never blocked by a 500.
    """
    try:
        return coach_preflight_svc.run_preflight(body)
    except Exception as exc:
        logger.exception("coach/preflight service error")
        return CoachPreflightResponse(
            matched_rules=[],
            recent_incidents=[],
            predicted_cost=CostPredict(note=f"service error: {exc}"),
            degraded=True,
            degraded_reason=str(exc),
        )


# ---------------------------------------------------------------------------
# WS-69 PR D — Brain Improvement Index
# ---------------------------------------------------------------------------


@router.get("/brain-improvement-index")
async def get_brain_improvement_index(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return the current Brain Improvement Index score and sub-metrics.

    Composite 0-100 score from three sub-metrics in v1:
    acceptance_rate (40%), promotion_progress (30%), rules_learning (20%),
    retro_delta (10%). Empty data returns honest zero — never fabricated.
    History_12w is empty until a weekly cron persists scores (planned PR P+).
    """
    response = self_improvement_svc.brain_improvement_response()
    return success_response(response.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# WS-69 PR I — Web Push (VAPID)
# ---------------------------------------------------------------------------


class WebPushSubscribeBody(BaseModel):
    user_id: str = Field(default="founder")
    endpoint: str
    p256dh: str
    auth: str = Field(alias="auth")

    model_config = {"populate_by_name": True}


class WebPushUnsubscribeBody(BaseModel):
    endpoint: str


@router.get("/web-push/vapid-public-key")
async def get_vapid_public_key(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return the VAPID public key for client-side push subscription."""
    import app.services.web_push as wp_svc
    from app.services.web_push import VapidConfigError

    try:
        pub = wp_svc.get_vapid_public_key()
    except VapidConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return success_response({"vapid_public_key": pub})


@router.post("/web-push/subscribe")
async def web_push_subscribe(
    body: WebPushSubscribeBody,
    _auth: None = Depends(_require_admin),
) -> Any:
    """Register a PushSubscription for the founder."""
    import app.services.web_push as wp_svc

    wp_svc.subscribe(
        user_id=body.user_id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
    )
    return success_response({"subscribed": True})


@router.post("/web-push/unsubscribe")
async def web_push_unsubscribe(
    body: WebPushUnsubscribeBody,
    _auth: None = Depends(_require_admin),
) -> Any:
    """Remove a PushSubscription by endpoint (idempotent)."""
    import app.services.web_push as wp_svc

    wp_svc.unsubscribe(endpoint=body.endpoint)
    return success_response({"unsubscribed": True})
