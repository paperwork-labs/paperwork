import asyncio
import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.schemas.base import success_response
from app.services.pr_review import review_pr, sweep_open_prs
from app.services.seed import ingest_docs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


@router.post("/seed")
async def trigger_seed_ingestion(
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_require_admin),
):
    repo_root = os.environ.get(
        "REPO_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    count = await ingest_docs(db, repo_root)
    return success_response({"episodes_created": count})


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
