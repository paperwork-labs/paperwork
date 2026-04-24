"""Risk controls: circuit breaker status (authenticated) and admin reset."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.dependencies import get_admin_user, get_current_user
from app.models.user import User
from app.services.risk.circuit_breaker import circuit_breaker

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/circuit-breaker")
async def get_circuit_breaker_status(
    _user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Current circuit breaker state for dashboard banners."""
    return {"data": circuit_breaker.get_status()}


@router.post("/circuit-breaker/reset-kill-switch")
async def reset_circuit_breaker_kill_switch(
    admin_user: User = Depends(get_admin_user),
) -> Dict[str, Any]:
    """Clear admin kill switch (admin only)."""
    circuit_breaker.reset_kill_switch(user=admin_user.username or "admin")
    return {"data": circuit_breaker.get_status()}
