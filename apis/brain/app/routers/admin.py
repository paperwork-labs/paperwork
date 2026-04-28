import asyncio
import hmac
import logging
import os
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.pr_outcomes as pr_outcomes_service
from app.config import settings
from app.database import async_session_factory, get_db
from app.models.episode import Episode
from app.models.scheduler_run import SchedulerRun
from app.personas import list_specs as list_persona_specs
from app.schemas.base import success_response
from app.services.continuous_learning import (
    ingest_decisions,
    ingest_merged_prs,
    ingest_postmortems,
)
from app.services.github_actions_quota_monitor import latest_github_actions_quota_snapshots
from app.services.kill_switch import is_brain_paused
from app.services.kill_switch import reason as brain_pause_reason
from app.services.pr_merge_sweep import merge_ready_prs
from app.services.pr_review import review_pr, sweep_open_prs
from app.services.procedural_memory import load_rules
from app.services.render_quota_monitor import (
    build_render_quota_admin_data,
    latest_render_quota_snapshot,
)
from app.services.seed import ingest_docs, ingest_sprint_lessons
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
    """Operator snapshot for Studio admin; extends over time (WS-45: pause flag)."""
    paused = is_brain_paused()
    return success_response(
        {
            "brain_paused": paused,
            "brain_paused_reason": brain_pause_reason() if paused else None,
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
