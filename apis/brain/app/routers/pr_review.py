"""GitHub PR review webhook — entry point for Brain's executive reviewer.

Triggered by ``.github/workflows/brain-pr-review.yaml`` on non-dependabot PRs.
The workflow POSTs a tiny envelope (pr_number, action) with an HMAC-SHA256
signature; Brain takes it from there: fetches metadata, diff, historical
context, calls Claude, and posts the review on GitHub.

Kept intentionally thin — all review logic lives in ``services/pr_review``.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory, get_db
from app.services.pr_review import review_pr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/github", tags=["webhooks", "github"])


async def _verify_gh_signature(request: Request) -> None:
    """HMAC-SHA256 verification (same pattern as AxiomFolio webhook).

    Header: ``X-Brain-Signature: sha256=<hex>``.
    Secret: ``settings.BRAIN_GITHUB_WEBHOOK_SECRET``.
    In development the check is relaxed so you can curl the endpoint locally.
    """
    expected_secret = getattr(settings, "BRAIN_GITHUB_WEBHOOK_SECRET", "") or ""
    if not expected_secret:
        if settings.ENVIRONMENT == "development":
            logger.warning(
                "BRAIN_GITHUB_WEBHOOK_SECRET not set — accepting review webhook unauthenticated (dev only)"
            )
            return
        raise HTTPException(status_code=503, detail="PR review webhook secret not configured")

    sig = request.headers.get("X-Brain-Signature", "")
    if not sig.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing X-Brain-Signature header")

    body = await request.body()
    expected = hmac.new(expected_secret.encode(), body, hashlib.sha256).hexdigest()
    received = sig[7:]
    if not hmac.compare_digest(expected, received):
        logger.warning("Brain PR review webhook signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid signature")


class PRReviewRequest(BaseModel):
    pr_number: int = Field(..., gt=0)
    action: str = Field("opened")
    organization_id: str = Field("paperwork-labs")
    force: bool = Field(
        False,
        description="Run the review even if the PR looks trivial/empty.",
    )


@router.post("/pr-review")
async def pr_review_webhook(
    body: PRReviewRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(_verify_gh_signature),
) -> dict[str, object]:
    """Kick off an async PR review. Returns 202 immediately.

    GitHub Actions workflows timeout after ~6h; we don't want the runner to
    pay for Claude's latency. Queue the work on the app's background tasks
    and ack the webhook in <100 ms.
    """
    if body.action not in ("opened", "synchronize", "ready_for_review", "reopened", "manual"):
        return {"accepted": False, "reason": f"ignoring action={body.action}"}

    background_tasks.add_task(_review_in_background, body.pr_number, body.organization_id)
    return {"accepted": True, "pr_number": body.pr_number, "action": body.action}


async def _review_in_background(pr_number: int, org_id: str) -> None:
    """Run the review with a fresh DB session (BackgroundTasks outlives `db`)."""
    async with async_session_factory() as session:
        try:
            result = await review_pr(session, pr_number=pr_number, org_id=org_id)
            logger.info(
                "PR review complete: #%s verdict=%s model=%s posted=%s",
                pr_number,
                result.get("verdict"),
                result.get("model"),
                result.get("posted"),
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("PR review failed for #%s: %s", pr_number, e)
