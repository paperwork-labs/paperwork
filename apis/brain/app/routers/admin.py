import asyncio
import hmac
import logging
import os
import subprocess
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, select
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
from app.services.persona_surface import (
    aggregate_persona_cost,
    list_cursor_rule_personas,
    load_persona_activity,
    load_routing_rules,
)
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


@router.get("/scheduler/n8n-mirror/status")
async def n8n_mirror_scheduler_status(
    _auth: None = Depends(_require_admin),
):
    """Legacy endpoint: n8n shadow APScheduler jobs were removed (Track K complete).

    First-party crons register when ``BRAIN_SCHEDULER_ENABLED`` is true; see
    ``docs/infra/BRAIN_SCHEDULER.md``.
    """
    return success_response(
        {
            "retired": True,
            "message": (
                "n8n mirror rows retired in chore/brain-delete-legacy-owns-flags — "
                "Brain owns these schedules permanently."
            ),
            "global_enabled": False,
            "per_job": [],
        }
    )


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


@router.get("/personas/list")
async def list_personas_cursor_rules(
    _auth: None = Depends(_require_admin),
):
    """Structured rows for every ``.cursor/rules/*.mdc`` (Studio Personas tab)."""
    try:
        rows = list_cursor_rule_personas()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return success_response({"count": len(rows), "personas": rows})


@router.get("/personas/cost")
async def get_personas_cost(
    window: str = Query("7d", description="Aggregation window: 7d or 30d."),
    _auth: None = Depends(_require_admin),
):
    """Token + USD aggregates from ``apis/brain/data/persona_cost.json`` when present."""
    w = window if window in ("7d", "30d") else "7d"
    payload = aggregate_persona_cost(window=w)
    return success_response(payload)


@router.get("/personas/routing")
async def get_personas_routing(
    _auth: None = Depends(_require_admin),
):
    """Persona routing tables (JSON file or derived from ``routing.py``)."""
    return success_response(load_routing_rules())


@router.get("/personas/activity")
async def get_personas_activity(
    limit: int = Query(50, ge=1, le=200),
    _auth: None = Depends(_require_admin),
):
    """Recent persona invocations from ``apis/brain/data/persona_activity.json``."""
    return success_response(load_persona_activity(limit=limit))


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
# WS-53 — Slack routing admin
# ---------------------------------------------------------------------------


class SlackRoutingTestRequest(BaseModel):
    event_type: str = Field(..., description="Event type to route (e.g. 'pr_merged')")
    severity: str = Field("low", description="Severity: low | medium | high")
    message: str = Field("", description="Preview message (not posted to Slack)")


@router.get("/slack-routing")
async def get_slack_routing(
    _auth: None = Depends(_require_admin),
) -> Any:
    """Return the active Slack routing config and current dedup/rate-limit state."""
    from app.services import slack_router
    from app.services.slack_router import _load_config

    cfg = _load_config()
    dedup_state = slack_router.get_dedup_state()
    return success_response(
        {
            "config": cfg.model_dump(mode="json", by_alias=False),
            "dedup_state": dedup_state,
        }
    )


@router.post("/slack-routing/test")
async def post_slack_routing_test(
    body: SlackRoutingTestRequest,
    _auth: None = Depends(_require_admin),
) -> Any:
    """Dry-run routing decision for a given event_type + severity.

    Does NOT post to Slack. Returns the RoutingDecision the router would
    make if called right now.
    """
    from app.services import slack_router

    decision = slack_router.route(
        event_type=body.event_type,
        severity=body.severity,
        key=f"admin-test:{body.event_type}",
    )
    return success_response(
        {
            "event_type": body.event_type,
            "severity": body.severity,
            "message_preview": body.message[:200] if body.message else "",
            "decision": decision.model_dump(mode="json"),
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
