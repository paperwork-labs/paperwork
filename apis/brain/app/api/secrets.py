"""Internal secrets intelligence routes (Studio webhooks, admin read surfaces)."""

from __future__ import annotations

import hmac
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.config import settings
from app.database import get_db
from app.models.secrets_intelligence import BrainSecretsRegistry
from app.services import secrets_intelligence as si
from app.services.agent_task_bridge import AgentTaskSpec, try_queue_agent_task

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/secrets", tags=["secrets"])


def _require_internal_bearer(authorization: str | None = Header(None)) -> None:
    if not settings.BRAIN_INTERNAL_TOKEN:
        raise HTTPException(status_code=503, detail="BRAIN_INTERNAL_TOKEN not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization")
    token = authorization[7:].strip()
    if not hmac.compare_digest(token, settings.BRAIN_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")


class SecretEventPayload(BaseModel):
    secret_name: str = Field(..., min_length=1)
    event_type: str
    source: str = "studio_intake"
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    # Optional: set when Studio knows registry cadence (intake complete)
    rotation_applied: bool = False


@router.post("/events")
async def record_secret_event(
    payload: SecretEventPayload,
    _auth: None = Depends(_require_internal_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive events from Studio vault (intake, rotations, etc.)."""
    intel = si.SecretsIntelligence(db)
    summary = payload.summary or f"{payload.event_type} for {payload.secret_name}"
    row = await intel.record_episode(
        secret_name=payload.secret_name,
        event_type=payload.event_type,
        source=payload.source,
        summary=summary,
        details=payload.details,
    )
    reg = await intel.get_registry(payload.secret_name)
    task_id: UUID | None = None

    if payload.event_type == "intake" and reg and reg.rotation_cadence_days:
        now = datetime.now(UTC)
        await intel.update_rotation_sync(
            payload.secret_name,
            last_rotated=now,
            last_verified=now,
        )

    if payload.event_type in ("drift_detected", "rotation_due"):
        spec = AgentTaskSpec(
            title=f"Secrets follow-up: {payload.secret_name}",
            summary=summary,
            category="secrets",
            metadata={"secret_name": payload.secret_name, "event_type": payload.event_type},
        )
        queued = await try_queue_agent_task(spec)
        if isinstance(queued, UUID):
            task_id = queued

    body: dict[str, Any] = {"ok": True, "episode_id": str(row.id)}
    if task_id is not None:
        body["task_id"] = str(task_id)
    return body


@router.get("/registry")
async def list_registry_endpoint(
    criticality: str | None = None,
    _auth: None = Depends(_require_internal_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    intel = si.SecretsIntelligence(db)
    rows = await intel.list_registry(criticality=criticality)
    return {
        "ok": True,
        "data": [
            {
                "name": r.name,
                "purpose": r.purpose,
                "service": r.service,
                "format_hint": r.format_hint,
                "expected_prefix": r.expected_prefix,
                "criticality": r.criticality,
                "depends_in_apps": r.depends_in_apps,
                "depends_in_services": r.depends_in_services,
                "rotation_cadence_days": r.rotation_cadence_days,
                "last_rotated_at": r.last_rotated_at.isoformat() if r.last_rotated_at else None,
                "last_verified_synced_at": (
                    r.last_verified_synced_at.isoformat() if r.last_verified_synced_at else None
                ),
                "drift_detected_at": r.drift_detected_at.isoformat()
                if r.drift_detected_at
                else None,
                "drift_summary": r.drift_summary,
                "lessons_learned": r.lessons_learned,
            }
            for r in rows
        ],
    }


@router.get("/episodes/{secret_name}")
async def episodes_for_secret(
    secret_name: str,
    limit: int = Query(50, ge=1, le=200),
    _auth: None = Depends(_require_internal_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    intel = si.SecretsIntelligence(db)
    eps = await intel.episodes_for(secret_name, limit=limit)
    return {
        "ok": True,
        "data": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "event_at": e.event_at.isoformat(),
                "source": e.source,
                "summary": e.summary,
                "details": e.details,
            }
            for e in eps
        ],
    }


@router.get("/health")
async def secrets_health(
    _auth: None = Depends(_require_internal_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rcount = await db.scalar(select(func.count(BrainSecretsRegistry.id)))
    drift_n = await db.scalar(
        select(func.count(BrainSecretsRegistry.id)).where(
            BrainSecretsRegistry.drift_detected_at.isnot(None)
        )
    )
    crit = {
        c: (
            await db.scalar(
                select(func.count(BrainSecretsRegistry.id)).where(
                    BrainSecretsRegistry.criticality == c
                )
            )
        )
        or 0
        for c in ("critical", "high", "normal", "low")
    }
    intel = si.SecretsIntelligence(db)
    due = await intel.rotations_due(threshold_days=7)
    return {
        "ok": True,
        "registry_count": int(rcount or 0),
        "with_drift_flag": int(drift_n or 0),
        "rotations_due_next_7d": len(due),
        "criticality_breakdown": crit,
    }
