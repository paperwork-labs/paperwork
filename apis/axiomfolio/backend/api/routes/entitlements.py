"""
Entitlements API
================

Three endpoints:

* ``GET  /api/v1/entitlements/me``       — the current user's tier + features
* ``GET  /api/v1/entitlements/catalog``  — the public feature catalog
* ``POST /api/v1/entitlements/check``    — programmatic access check
                                            (used by the frontend AgentBrain
                                            chat to decide whether to render
                                            the upgrade prompt)

The catalog endpoint is intentionally **public** (``optional_user``) so the
marketing site and a logged-out pricing page can render the same source of
truth as the in-app gate.

Manual operator overrides (``POST /admin``) live in
``backend/api/routes/admin/entitlements.py`` and are gated by
``get_admin_user``.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_optional_user
from backend.database import get_db
from backend.models.user import User
from backend.services.billing.entitlement_service import EntitlementService
from backend.services.billing.feature_catalog import (
    Feature,
    all_features,
    get_feature,
    is_allowed,
)


router = APIRouter(prefix="/entitlements", tags=["Entitlements"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class FeatureSchema(BaseModel):
    key: str
    title: str
    description: str
    category: str
    min_tier: str

    @classmethod
    def from_feature(cls, f: Feature) -> "FeatureSchema":
        return cls(
            key=f.key,
            title=f.title,
            description=f.description,
            category=f.category,
            min_tier=f.min_tier.value,
        )


class FeatureAccessSchema(BaseModel):
    """Per-feature decision for the current user."""

    key: str
    allowed: bool
    min_tier: str


class MeResponse(BaseModel):
    """Everything the frontend needs to render the gate.

    ``features`` is a flat array (rather than a dict) so the response is
    easy to memoize, diff, and snapshot-test on the client.
    """

    tier: str
    status: str
    is_active: bool
    cancel_at_period_end: bool
    current_period_end: Optional[str]
    trial_ends_at: Optional[str]
    features: List[FeatureAccessSchema]


class CatalogResponse(BaseModel):
    features: List[FeatureSchema]


class CheckRequest(BaseModel):
    feature: str


class CheckResponse(BaseModel):
    allowed: bool
    feature: str
    current_tier: str
    required_tier: str
    reason: str


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.get("/catalog", response_model=CatalogResponse)
async def get_catalog(
    _user: Optional[User] = Depends(get_optional_user),
) -> CatalogResponse:
    """Public feature catalog — used by both in-app and marketing-site
    pricing tables. Auth is optional so a logged-out visitor can also load
    the page; the actual feature list is identical either way."""
    return CatalogResponse(
        features=[FeatureSchema.from_feature(f) for f in all_features()]
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    """Current user's tier and per-feature access flags.

    Computed in one round-trip so the frontend doesn't fan out N requests
    when it boots.
    """
    ent = EntitlementService.get_or_create(db, user)
    effective = ent.effective_tier()
    feature_rows = [
        FeatureAccessSchema(
            key=f.key,
            allowed=is_allowed(effective, f.key),
            min_tier=f.min_tier.value,
        )
        for f in all_features()
    ]
    return MeResponse(
        tier=effective.value,
        status=ent.status.value,
        is_active=ent.is_active(),
        cancel_at_period_end=bool(ent.cancel_at_period_end),
        current_period_end=(
            ent.current_period_end.isoformat() if ent.current_period_end else None
        ),
        trial_ends_at=(
            ent.trial_ends_at.isoformat() if ent.trial_ends_at else None
        ),
        features=feature_rows,
    )


@router.post("/check", response_model=CheckResponse)
async def check_feature(
    body: CheckRequest = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckResponse:
    """Programmatic check — handy for the AgentBrain chat panel which
    decides whether to render content or an upgrade prompt based on
    runtime context."""
    try:
        get_feature(body.feature)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    decision = EntitlementService.check(db, user, body.feature)
    return CheckResponse(
        allowed=decision.allowed,
        feature=decision.feature.key,
        current_tier=decision.current_tier.value,
        required_tier=decision.required_tier.value,
        reason=decision.reason,
    )
