"""Brain admin router for application log ingestion and querying (WS-69 PR M).

Endpoints
---------
POST /api/v1/admin/logs/ingest  — bearer (X-Brain-Secret) auth, ingest log entries
GET  /api/v1/admin/logs         — query stored logs with filters + cursor pagination

Authentication uses the same X-Brain-Secret header pattern as all other admin routes.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.schemas.app_logs import AppLogEntry
from app.services import app_logs as app_logs_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


class IngestRequest(BaseModel):
    logs: list[AppLogEntry]


class IngestResponse(BaseModel):
    success: bool
    added: int
    total_submitted: int


@router.post("/ingest", response_model=IngestResponse)
async def ingest_logs(
    body: IngestRequest,
    _auth: None = Depends(_require_admin),
) -> IngestResponse:
    """Ingest a batch of application log entries.

    Deduplicates by ``id`` field. Evicts oldest entries when store exceeds
    10,000 entries. Returns count of net-new entries added.
    """
    added = await asyncio.to_thread(app_logs_svc.ingest_logs, body.logs)
    logger.info(
        "admin_logs.ingest: submitted=%d added=%d",
        len(body.logs),
        added,
        extra={"component": "admin_logs", "op": "ingest", "added": added},
    )
    return IngestResponse(success=True, added=added, total_submitted=len(body.logs))


@router.get("")
async def query_logs(
    app: str | None = Query(None, description="Filter by application name"),
    service: str | None = Query(None, description="Filter by service/project name"),
    severity: str | None = Query(None, description="Minimum severity level"),
    since: datetime | None = Query(None, description="Return entries at or after this timestamp"),
    until: datetime | None = Query(None, description="Return entries at or before this timestamp"),
    q: str | None = Query(None, description="Full-text search across message and attrs"),
    cursor: str | None = Query(None, description="Opaque pagination cursor from previous response"),
    limit: int = Query(50, ge=1, le=500, description="Page size (1-500, default 50)"),
    _auth: None = Depends(_require_admin),
) -> dict[str, Any]:
    """Query stored application logs with optional filters.

    Returns paginated results. Pass ``next_cursor`` into the ``cursor`` param
    to fetch the next page.
    """
    result = await asyncio.to_thread(
        app_logs_svc.query_logs,
        app=app,
        service=service,
        severity_min=severity,
        since=since,
        until=until,
        search=q,
        cursor=cursor,
        limit=limit,
    )
    return result
