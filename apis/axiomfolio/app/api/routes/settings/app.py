from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.entitlement import SubscriptionTier
from app.models.user import User
from app.services.billing.entitlement_service import EntitlementService
from app.services.security.credential_vault import credential_vault

router = APIRouter()
logger = logging.getLogger(__name__)


class AIKeyPutRequest(BaseModel):
    provider: str = Field(pattern="^(openai|anthropic)$")
    api_key: str = Field(min_length=1, max_length=2048)


class AIKeyStatusResponse(BaseModel):
    provider: str | None
    has_key: bool


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
