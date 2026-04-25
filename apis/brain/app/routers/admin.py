import asyncio
import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.models.episode import Episode
from app.personas import list_specs as list_persona_specs
from app.schemas.base import success_response
from app.services.pr_merge_sweep import merge_ready_prs
from app.services.pr_review import review_pr, sweep_open_prs
from app.services.seed import ingest_docs, ingest_sprint_lessons

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


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


@router.get("/personas")
async def list_personas(
    _auth: None = Depends(_require_admin),
):
    """Return the PersonaSpec registry so Studio can render /admin/agents."""
    specs = list_persona_specs()
    return success_response({
        "count": len(specs),
        "personas": [spec.model_dump() for spec in specs],
    })


class PRSweepRequest(BaseModel):
    organization_id: str = Field("paperwork-labs")
    limit: int = Field(30, ge=1, le=100)
    force: bool = Field(
        False,
        description="Re-review PRs even if an episode already exists at the current head SHA.",
    )


@router.post("/pr-sweep")
async def trigger_pr_sweep(
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

    asyncio.create_task(_run())
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
        description="Filter episodes whose `source` starts with this prefix (e.g. `brain:pr-review`).",
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
