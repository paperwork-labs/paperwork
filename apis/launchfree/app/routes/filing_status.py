"""Filing engine status API — read for authenticated users, write for internal workers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_session
from app.models.formation import Formation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/filings", tags=["filing-status"])

STATUS_HISTORY_KEY = "_status_history"
FILING_ERROR_MESSAGE_KEY = "_filing_error_message"

FILING_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "pending_payment",
        "payment_complete",
        "submitting",
        "submitted",
        "processing",
        "confirmed",
        "failed",
        "requires_manual",
    }
)

# Legacy formation statuses stored in DB — treated like draft for transition rules
_STATUS_ALIASES: dict[str, str] = {
    "documents_ready": "draft",
}

_ALLOWED: dict[str, frozenset[str]] = {
    "draft": frozenset(
        {
            "pending_payment",
            "submitting",
            "failed",
            "requires_manual",
        }
    ),
    "pending_payment": frozenset({"payment_complete", "failed", "draft"}),
    "payment_complete": frozenset({"submitting", "failed", "requires_manual"}),
    "submitting": frozenset({"submitted", "failed", "requires_manual"}),
    "submitted": frozenset(
        {"processing", "confirmed", "failed", "requires_manual"}
    ),
    "processing": frozenset({"confirmed", "failed", "requires_manual"}),
    "confirmed": frozenset(),
    "failed": frozenset({"draft", "pending_payment"}),
    "requires_manual": frozenset({"draft", "confirmed", "failed"}),
}

_TERMINAL = frozenset({"confirmed"})


def _normalize_for_rules(db_status: str) -> str:
    return _STATUS_ALIASES.get(db_status, db_status)


def can_transition(from_status: str, to_status: str) -> bool:
    """Mirror packages/filing-engine StatusTracker.canTransition (keep in sync)."""
    if from_status == to_status:
        return False
    from_effective = _normalize_for_rules(from_status)
    if from_effective in _TERMINAL:
        return False
    allowed = _ALLOWED.get(from_effective)
    if allowed is None:
        return False
    return to_status in allowed


class StatusTransition(BaseModel):
    from_status: str
    to_status: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None


class FilingStatusResponse(BaseModel):
    formation_id: str
    current_status: str
    history: list[StatusTransition]
    confirmation_number: str | None = None
    filing_number: str | None = None
    error_message: str | None = None
    screenshots: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FilingStatusUpdateBody(BaseModel):
    status: str = Field(min_length=1, max_length=64)
    metadata: dict[str, Any] | None = None
    error_message: str | None = Field(
        default=None,
        description="Optional error text; stored when transitioning to failed",
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _load_history(error_log: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not error_log:
        return []
    raw = error_log.get(STATUS_HISTORY_KEY)
    if not isinstance(raw, list):
        return []
    return raw


def _error_log_with_history(
    existing: dict[str, Any] | None,
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    base = dict(existing) if existing else {}
    base[STATUS_HISTORY_KEY] = history
    return base


def _filing_error_message(error_log: dict[str, Any] | None) -> str | None:
    if not error_log:
        return None
    msg = error_log.get(FILING_ERROR_MESSAGE_KEY)
    if isinstance(msg, str) and msg.strip():
        return msg
    legacy = error_log.get("message")
    if isinstance(legacy, str) and legacy.strip():
        return legacy
    return None


async def require_filing_internal(request: Request) -> None:
    secret = settings.FILING_STATUS_INTERNAL_SECRET
    if secret:
        token = request.headers.get("X-Filing-Internal-Token")
        if token != secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing internal filing token",
            )
        return
    if settings.ENVIRONMENT == "production":
        logger.error("FILING_STATUS_INTERNAL_SECRET unset in production")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Filing status updates are not configured",
        )


def _history_to_models(rows: list[dict[str, Any]]) -> list[StatusTransition]:
    out: list[StatusTransition] = []
    for row in rows:
        try:
            ts = row["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            out.append(
                StatusTransition(
                    from_status=str(row["from_status"]),
                    to_status=str(row["to_status"]),
                    timestamp=ts,
                    metadata=row.get("metadata"),
                )
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Skipping malformed status history row: %s", e)
    return out


def _parse_formation_id(formation_id: str) -> int:
    try:
        return int(formation_id, 10)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="formation_id must be a numeric id",
        ) from None


def _formation_to_response(f: Formation) -> FilingStatusResponse:
    elog = f.error_log if isinstance(f.error_log, dict) else {}
    history_raw = _load_history(elog)
    return FilingStatusResponse(
        formation_id=str(f.id),
        current_status=f.status,
        history=_history_to_models(history_raw),
        confirmation_number=f.confirmation_number,
        filing_number=f.filing_number,
        error_message=_filing_error_message(elog),
        screenshots=list(f.screenshots) if f.screenshots else [],
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


@router.get("/{formation_id}/status", response_model=FilingStatusResponse)
async def get_filing_status(
    formation_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(require_session),
) -> FilingStatusResponse:
    """Return filing status and transition history for the current user's formation."""
    fid = _parse_formation_id(formation_id)
    result = await db.execute(
        select(Formation).where(
            Formation.id == fid,
            Formation.user_id == user_id,
        )
    )
    formation = result.scalar_one_or_none()
    if not formation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formation not found",
        )
    return _formation_to_response(formation)


@router.post("/{formation_id}/status", response_model=FilingStatusResponse)
async def update_filing_status(
    formation_id: str,
    body: FilingStatusUpdateBody,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_filing_internal),
) -> FilingStatusResponse:
    """Apply a status transition (filing engine / workers). Requires internal token."""
    if body.status not in FILING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown status: {body.status}",
        )

    fid = _parse_formation_id(formation_id)
    result = await db.execute(select(Formation).where(Formation.id == fid))
    formation = result.scalar_one_or_none()
    if not formation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Formation not found",
        )

    from_status = formation.status
    if not can_transition(from_status, body.status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition {from_status!r} -> {body.status!r}",
        )

    elog = dict(formation.error_log) if isinstance(formation.error_log, dict) else {}
    history = _load_history(elog)
    now = _utc_now()
    entry: dict[str, Any] = {
        "from_status": from_status,
        "to_status": body.status,
        "timestamp": now.isoformat(),
    }
    if body.metadata is not None:
        entry["metadata"] = body.metadata
    history.append(entry)

    formation.status = body.status
    formation.error_log = _error_log_with_history(elog, history)

    if body.error_message is not None:
        elog_after = dict(formation.error_log)
        elog_after[FILING_ERROR_MESSAGE_KEY] = body.error_message
        formation.error_log = elog_after
    elif body.status != "failed":
        elog_after = dict(formation.error_log)
        elog_after.pop(FILING_ERROR_MESSAGE_KEY, None)
        formation.error_log = elog_after

    await db.flush()
    await db.refresh(formation)

    logger.info(
        "Filing status transition formation_id=%s %s -> %s",
        fid,
        from_status,
        body.status,
    )
    return _formation_to_response(formation)
