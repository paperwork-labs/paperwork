from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Dict, Any

from backend.api.dependencies import get_current_user, get_admin_user
from backend.database import get_db
from backend.services.core.app_settings_service import get_or_create_app_settings

router = APIRouter()


class AppSettingsUpdate(BaseModel):
    market_only_mode: bool | None = None
    portfolio_enabled: bool | None = None
    strategy_enabled: bool | None = None


@router.get("/app-settings")
async def get_app_settings(
    _user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    settings = get_or_create_app_settings(db)
    return {
        "market_only_mode": bool(settings.market_only_mode),
        "portfolio_enabled": bool(settings.portfolio_enabled),
        "strategy_enabled": bool(settings.strategy_enabled),
    }


@router.get("/admin/app-settings")
async def get_admin_app_settings(
    _admin=Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    settings = get_or_create_app_settings(db)
    return {
        "market_only_mode": bool(settings.market_only_mode),
        "portfolio_enabled": bool(settings.portfolio_enabled),
        "strategy_enabled": bool(settings.strategy_enabled),
    }


@router.patch("/admin/app-settings")
async def update_app_settings(
    payload: AppSettingsUpdate,
    _admin=Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    settings = get_or_create_app_settings(db)
    if payload.market_only_mode is not None:
        settings.market_only_mode = bool(payload.market_only_mode)
    if payload.portfolio_enabled is not None:
        settings.portfolio_enabled = bool(payload.portfolio_enabled)
    if payload.strategy_enabled is not None:
        settings.strategy_enabled = bool(payload.strategy_enabled)
    db.commit()
    db.refresh(settings)
    return {
        "market_only_mode": bool(settings.market_only_mode),
        "portfolio_enabled": bool(settings.portfolio_enabled),
        "strategy_enabled": bool(settings.strategy_enabled),
    }
