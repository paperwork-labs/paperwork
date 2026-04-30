"""Unified error capture endpoints for Paperwork products."""

from __future__ import annotations

import asyncio
import hmac
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query

from app.config import settings
from app.schemas.error_ingest import ErrorIngestRequest, ErrorIngestResponse
from app.services import error_ingest as error_svc

router = APIRouter(prefix="/errors", tags=["errors"])


def _require_error_ingest_token(authorization: str | None = Header(None)) -> None:
    expected = settings.BRAIN_API_INTERNAL_TOKEN.strip()
    if not expected:
        raise HTTPException(
            status_code=401,
            detail="BRAIN_API_INTERNAL_TOKEN is required for Brain error ingestion.",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization bearer token for Brain error ingestion.",
        )
    token = authorization[7:].strip()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid Brain error ingestion token.")


@router.post(
    "/ingest",
    response_model=ErrorIngestResponse,
    dependencies=[Depends(_require_error_ingest_token)],
)
async def ingest_error(
    body: ErrorIngestRequest,
    background_tasks: BackgroundTasks,
) -> ErrorIngestResponse:
    record = await asyncio.to_thread(error_svc.append_error, body)
    background_tasks.add_task(error_svc.prune_errors_if_needed)
    return ErrorIngestResponse(success=True, fingerprint=record.fingerprint, id=record.id)


@router.get(
    "/recent",
    dependencies=[Depends(_require_error_ingest_token)],
)
async def recent_errors(
    product: str | None = Query(None, min_length=1),
    since: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    errors = await asyncio.to_thread(
        error_svc.query_recent_errors,
        product=product,
        since=since,
        limit=limit,
    )
    return {"errors": errors, "count": len(errors)}


@router.get(
    "/aggregates",
    dependencies=[Depends(_require_error_ingest_token)],
)
async def error_aggregates(
    since: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    aggregates = await asyncio.to_thread(error_svc.query_aggregates, since=since, limit=limit)
    return {"aggregates": aggregates, "count": len(aggregates)}
