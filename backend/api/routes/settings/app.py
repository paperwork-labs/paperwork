from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_admin_user
from backend.database import get_db
from backend.models.entitlement import SubscriptionTier
from backend.models.user import User
from backend.services.billing.entitlement_service import EntitlementService
from backend.services.core.app_settings_service import get_or_create_app_settings
from backend.services.security.credential_vault import credential_vault

router = APIRouter()
logger = logging.getLogger(__name__)


class AppSettingsUpdate(BaseModel):
    market_only_mode: bool | None = None
    portfolio_enabled: bool | None = None
    strategy_enabled: bool | None = None


class AIKeyPutRequest(BaseModel):
    provider: str = Field(pattern="^(openai|anthropic)$")
    api_key: str = Field(min_length=1, max_length=2048)


class AIKeyStatusResponse(BaseModel):
    provider: Optional[str]
    has_key: bool


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


@router.get("/settings/ai-keys", response_model=AIKeyStatusResponse)
async def get_ai_key_status(
    current_user: User = Depends(get_current_user),
) -> AIKeyStatusResponse:
    encrypted = current_user.llm_provider_key_encrypted
    if not encrypted:
        return AIKeyStatusResponse(provider=None, has_key=False)
    try:
        payload = credential_vault.decrypt_dict(encrypted)
        provider = str(payload.get("provider") or "").strip().lower() or None
        return AIKeyStatusResponse(provider=provider, has_key=True)
    except Exception as e:
        logger.warning(
            "Failed to decrypt user llm key for user_id=%s: %s",
            current_user.id,
            e,
        )
        return AIKeyStatusResponse(provider=None, has_key=True)


@router.put("/settings/ai-keys", response_model=AIKeyStatusResponse)
async def put_ai_key(
    payload: AIKeyPutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIKeyStatusResponse:
    effective_tier = EntitlementService.effective_tier(db, current_user)
    if SubscriptionTier.rank(effective_tier) < SubscriptionTier.rank(SubscriptionTier.PRO):
        raise HTTPException(status_code=402, detail="BYOK requires Pro or higher")
    encrypted = credential_vault.encrypt_dict(
        {"provider": payload.provider, "api_key": payload.api_key}
    )
    current_user.llm_provider_key_encrypted = encrypted
    db.add(current_user)
    db.commit()
    logger.info(
        "BYOK key stored for user_id=%s provider=%s",
        current_user.id,
        payload.provider,
    )
    return AIKeyStatusResponse(provider=payload.provider, has_key=True)


@router.delete("/settings/ai-keys", response_model=AIKeyStatusResponse)
async def delete_ai_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIKeyStatusResponse:
    # No tier check: a user who downgrades from PRO should still be able
    # to scrub their key. Returning the cleared status is intentional so
    # the frontend can render the empty state without a follow-up fetch.
    current_user.llm_provider_key_encrypted = None
    db.add(current_user)
    db.commit()
    logger.info("BYOK key removed for user_id=%s", current_user.id)
    return AIKeyStatusResponse(provider=None, has_key=False)
