"""Internal HTTP surface for cheap-agent sprint planning (founder / Studio)."""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.schemas.base import success_response
from app.services.agent_sprint_store import load_sprints_since, today_metrics
from app.schedulers.agent_sprint_scheduler import run_agent_sprint_tick

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/agent-sprints", tags=["internal"])


def _require_founder_secret(x_brain_secret: str | None = Header(None, alias="X-Brain-Secret")) -> None:
    expected = settings.BRAIN_API_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="BRAIN_API_SECRET not configured")
    if not x_brain_secret or not hmac.compare_digest(x_brain_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Brain-Secret")


@router.get("/today")
async def agent_sprints_today(_auth: None = Depends(_require_founder_secret)):
    """Last 24h of generated sprints plus day metrics (Studio command center)."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    sprints = load_sprints_since(since)
    metrics = today_metrics()
    payload = {
        "sprints": [s.model_dump() for s in sprints],
        "metrics": metrics.model_dump(),
        "generated_through": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return success_response(payload)


@router.post("/regenerate")
async def agent_sprints_regenerate(_auth: None = Depends(_require_founder_secret)):
    """Run the same pipeline as the scheduler tick immediately (manual refresh)."""
    try:
        report = await run_agent_sprint_tick(reason="manual_regenerate")
    except Exception:
        logger.exception("agent_sprints_regenerate failed")
        raise HTTPException(status_code=500, detail="regenerate_failed") from None
    return success_response(report)
