"""Deploy-health admin routes (G28, D120).

Two endpoints, both admin-gated:

* ``GET  /api/v1/admin/deploys/health`` — current summary (same payload the
  composite-health ``deploys`` dimension uses, plus ``services_configured``
  metadata and raw event tail).
* ``POST /api/v1/admin/deploys/poll``  — force a poll cycle (sync). Useful
  for runbook steps and the pre-merge GitHub Action when it needs a fresh
  read rather than last-5-min cached state.

Kept intentionally small — this is observability, not billing or auth.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user, get_db
from app.models import User
from app.models.deploy_health_event import DeployHealthEvent
from app.services.deploys.poll_service import (
    poll_and_record,
    summarize_composite,
)
from app.services.deploys.service_resolver import resolve_services

# Kept as a module-level alias so unit tests can monkeypatch this symbol
# without having to know the shared-resolver location.
_resolve_services = resolve_services

router = APIRouter(prefix="/admin/deploys", tags=["admin", "deploys"])

logger = logging.getLogger(__name__)


class DeployEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: str
    service_slug: str
    service_type: str
    deploy_id: str
    status: str
    trigger: Optional[str]
    commit_sha: Optional[str]
    commit_message: Optional[str]
    render_created_at: datetime
    render_finished_at: Optional[datetime]
    duration_seconds: Optional[float]
    is_poll_error: bool
    poll_error_message: Optional[str]
    polled_at: datetime


class DeployHealthResponse(BaseModel):
    status: str
    reason: str
    services: List[Dict[str, Any]]
    services_configured: int
    consecutive_failures_max: int
    failures_24h_total: int
    events: List[DeployEventResponse]
    checked_at: datetime


class PollResponse(BaseModel):
    services_polled: int
    events_inserted: int
    events_skipped: int
    poll_errors: int
    details: List[Dict[str, Any]]


@router.get("/health", response_model=DeployHealthResponse)
def deploy_health(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> DeployHealthResponse:
    """Return a rich deploy-health snapshot for the admin UI.

    Includes the composite summary (same shape embedded in ``/admin/health``)
    plus the last ``limit`` raw events across all monitored services so the
    UI can render a timeline.
    """
    services = _resolve_services()
    summary = summarize_composite(db, services)

    # Filter events to the currently monitored services. If the operator
    # drops a service id from DEPLOY_HEALTH_SERVICE_IDS, the UI timeline
    # should no longer show that service's events alongside the composite
    # — otherwise the card contradicts itself.
    events_query = db.query(DeployHealthEvent)
    service_ids = [s["service_id"] for s in services if s.get("service_id")]
    if service_ids:
        events_query = events_query.filter(
            DeployHealthEvent.service_id.in_(service_ids)
        )
    else:
        # No services configured -> no rows at all (matches the
        # empty-services summary path rather than returning stale noise).
        events_query = events_query.filter(False)

    events_q = (
        events_query
        .order_by(DeployHealthEvent.render_created_at.desc(), DeployHealthEvent.id.desc())
        .limit(max(1, min(int(limit), 200)))
        .all()
    )

    return DeployHealthResponse(
        status=summary["status"],
        reason=summary["reason"],
        services=summary["services"],
        services_configured=summary.get("services_configured", len(services)),
        consecutive_failures_max=summary["consecutive_failures_max"],
        failures_24h_total=summary["failures_24h_total"],
        events=[DeployEventResponse.model_validate(e) for e in events_q],
        checked_at=datetime.now(timezone.utc),
    )


@router.post("/poll", response_model=PollResponse)
def deploy_health_poll(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> PollResponse:
    """Force a synchronous poll cycle.

    Useful for:
    * runbook step 1 after a prod freeze ("are new deploys landing?")
    * CI pre-merge gate that wants fresh data, not the last Beat tick
    * manual recovery after the operator reset a Render billing issue
    """
    services = _resolve_services()
    if not services:
        raise HTTPException(
            status_code=400,
            detail="DEPLOY_HEALTH_SERVICE_IDS is empty — configure at least one service id",
        )
    try:
        result = poll_and_record(db, services)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return PollResponse(**result)
