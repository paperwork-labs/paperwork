"""Workstreams board API (Track Z) — Studio-authenticated reorder → GitHub PR."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services import workstream_reorder as reorder_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workstreams", tags=["workstreams"])


def _require_internal_bearer(authorization: str | None = Header(None)) -> None:
    if not settings.BRAIN_INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="BRAIN_INTERNAL_TOKEN not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization")
    token = authorization[7:].strip()
    if not hmac.compare_digest(token, settings.BRAIN_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")


class ReorderWorkstreamsBody(BaseModel):
    ordered_ids: list[str] = Field(..., min_length=1)


class ReorderWorkstreamsAccepted(BaseModel):
    pr_number: int
    pr_url: str


@router.post(
    "/reorder",
    status_code=202,
    response_model=ReorderWorkstreamsAccepted,
    dependencies=[Depends(_require_internal_bearer)],
)
async def reorder_workstreams(body: ReorderWorkstreamsBody) -> ReorderWorkstreamsAccepted:
    try:
        pr = await reorder_svc.open_reorder_workstreams_pr(body.ordered_ids)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("workstreams reorder failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    num = pr.get("number")
    url = pr.get("html_url")
    if not isinstance(num, int) or not isinstance(url, str):
        raise HTTPException(status_code=500, detail="Unexpected GitHub PR response shape")
    return ReorderWorkstreamsAccepted(pr_number=num, pr_url=url)
