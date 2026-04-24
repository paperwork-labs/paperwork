"""Admin: per-tenant cost rollup view.

OWNER-only. Lists the top-N tenants by total cost for a given UTC day,
backed by ``TenantCostRollup`` rows produced by the daily Celery rollup.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_admin_user
from app.database import get_db
from app.models.user import User
from app.services.multitenant.cost_attribution import CostAttributionService

router = APIRouter(prefix="/api/v1/admin/cost-attribution", tags=["AdminCosts"])


@router.get("/top")
def top_tenants_by_cost(
    day: str | None = Query(None, description="UTC date YYYY-MM-DD; defaults to yesterday"),
    limit: int = Query(25, ge=1, le=200),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return the top ``limit`` tenants by total cost for ``day``."""
    if day is None:
        target = (datetime.now(UTC) - timedelta(days=1)).date()
    else:
        try:
            target = date_cls.fromisoformat(day)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    rows = CostAttributionService(db).top_n_by_cost(target, limit=limit)
    return {"day": target.isoformat(), "limit": limit, "rows": rows}


@router.post("/rollup")
def trigger_rollup(
    day: str | None = Query(None, description="UTC date YYYY-MM-DD"),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    """Recompute the rollup synchronously for an arbitrary day.

    Convenience for backfills / debugging. The daily Celery beat
    handles the normal cadence.
    """
    if day is None:
        target = (datetime.now(UTC) - timedelta(days=1)).date()
    else:
        try:
            target = date_cls.fromisoformat(day)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    written = CostAttributionService(db).rollup_day(target)
    return {"day": target.isoformat(), "rows_written": written}
