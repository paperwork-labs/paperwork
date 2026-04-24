"""User-scoped broker connection health (aggregates accounts + OAuth rows)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.connections.health_aggregate import build_connections_health

router = APIRouter()


class BrokerHealthRow(BaseModel):
    broker: str
    status: str = Field(
        ...,
        description="disconnected | connected | stale | error",
    )
    last_sync_at: datetime | None = None
    error_message: str | None = None


class ConnectionsHealthResponse(BaseModel):
    connected: int
    total: int
    last_sync_at: datetime | None = None
    by_broker: list[BrokerHealthRow]


@router.get("/health", response_model=ConnectionsHealthResponse)
def get_connections_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionsHealthResponse:
    """Summarize broker link + sync health for the authenticated user."""

    raw = build_connections_health(db, int(current_user.id))
    return ConnectionsHealthResponse.model_validate(raw)
