"""Brain-owned logs router (WS-69 PR M).

POST /admin/logs/ingest   — apps push events (admin token required)
GET  /admin/logs          — list with filters (admin token required)
POST /admin/logs/pull     — manually trigger pull from Vercel/Render (admin token required)
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.config import settings
from app.schemas.app_log import AppLogIngestRequest, AppLogsListPage
from app.services import app_logs as app_logs_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/logs", tags=["logs"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _require_admin(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    import hmac

    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Admin access required")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest", status_code=201)
def ingest_log(
    req: AppLogIngestRequest,
    _auth: None = Depends(_require_admin),
) -> dict:
    """Push a log event from an app into Brain-owned storage."""
    log = app_logs_svc.ingest_log(req)
    return {"success": True, "data": {"id": log.id, "at": log.at.isoformat()}}


@router.get("")
def list_logs(
    app: str | None = Query(default=None, description="Filter by app name"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    search: str | None = Query(
        default=None, description="Full-text search over message + metadata"
    ),
    since: str | None = Query(
        default=None,
        description="ISO8601 lower-bound on log timestamp (e.g. 2026-01-01T00:00:00Z)",
    ),
    cursor: str | None = Query(default=None, description="Pagination cursor (ISO8601 timestamp)"),
    limit: int = Query(default=100, ge=1, le=500),
    _auth: None = Depends(_require_admin),
) -> dict:
    """Return cursor-paginated, filtered logs (newest first)."""
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid 'since' timestamp: {exc}"
            ) from exc

    page: AppLogsListPage = app_logs_svc.list_logs(
        app=app,
        severity=severity,
        search=search,
        since=since_dt,
        limit=limit,
        cursor=cursor,
    )
    last_pulled = app_logs_svc.get_last_pulled_at()
    return {
        "success": True,
        "data": {
            "logs": [lg.model_dump(mode="json") for lg in page.logs],
            "total_matched": page.total_matched,
            "next_cursor": page.next_cursor,
            "last_pulled_at": last_pulled,
        },
    }


@router.post("/pull")
def trigger_pull(
    _auth: None = Depends(_require_admin),
) -> dict:
    """Manually trigger log pull from Vercel + Render. Runs synchronously."""
    since = datetime.now(UTC) - timedelta(hours=1)
    team_id = os.environ.get("VERCEL_TEAM_ID", "").strip()
    vercel_projects_raw = os.environ.get("BRAIN_LOGS_VERCEL_PROJECT_IDS", "").strip()
    render_services_raw = os.environ.get("BRAIN_LOGS_RENDER_SERVICE_IDS", "").strip()

    vercel_project_ids = [p.strip() for p in vercel_projects_raw.split(",") if p.strip()]
    render_service_ids = [s.strip() for s in render_services_raw.split(",") if s.strip()]

    vercel_count = 0
    render_count = 0

    if vercel_project_ids:
        try:
            vercel_count = app_logs_svc.pull_vercel_logs(
                team_id=team_id,
                project_ids=vercel_project_ids,
                since=since,
            )
        except Exception as exc:
            logger.exception("trigger_pull: pull_vercel_logs raised: %s", exc)

    if render_service_ids:
        try:
            render_count = app_logs_svc.pull_render_logs(
                service_ids=render_service_ids,
                since=since,
            )
        except Exception as exc:
            logger.exception("trigger_pull: pull_render_logs raised: %s", exc)

    return {
        "success": True,
        "data": {
            "vercel_ingested": vercel_count,
            "render_ingested": render_count,
            "since": since.isoformat(),
        },
    }
