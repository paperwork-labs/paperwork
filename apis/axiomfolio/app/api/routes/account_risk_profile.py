"""Per-account risk profile routes.

``GET /api/v1/accounts/{account_id}/risk-profile`` returns the firm
caps, the per-account overrides, and the effective (tighter-of-two)
limits for a broker account owned by the current user.

``PUT /api/v1/accounts/{account_id}/risk-profile`` validates and
persists a new override. Any attempt to loosen a firm cap returns
HTTP 400 with a readable error; the firm layer is always the ceiling.

Enforcement of the effective limits at order time remains in
``app/services/execution/risk_gate.py`` (Danger Zone, not touched by
this PR). This surface is configuration + advisory display only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.gold.risk.account_risk_profile import (
    AccountNotFoundError,
    apply_override,
    get_effective_limits,
)
from app.services.gold.risk.firm_caps import FIRM_CAP_FIELDS, FirmCapsUnavailable


router = APIRouter(prefix="/accounts", tags=["accounts", "risk"])


class RiskProfilePayload(BaseModel):
    """Partial override payload.

    Each field is an optional fraction in ``[0, 1]`` (e.g. ``0.05`` =
    5%). Missing / null fields are treated as "inherit firm cap".
    """

    model_config = ConfigDict(extra="forbid")

    max_position_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)
    max_stage_2c_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)
    max_options_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)
    max_daily_loss_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)
    hard_stop_pct: Optional[Decimal] = Field(default=None, ge=0, le=1)

    def as_override(self) -> dict[str, Optional[Decimal]]:
        return {field: getattr(self, field) for field in FIRM_CAP_FIELDS}


@router.get("/{account_id}/risk-profile")
def get_account_risk_profile(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Return firm caps, per-account overrides, and effective limits."""
    try:
        result = get_effective_limits(db=db, user_id=user.id, account_id=account_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except FirmCapsUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    return {"data": result.as_dict()}


@router.put("/{account_id}/risk-profile")
def put_account_risk_profile(
    account_id: int,
    payload: RiskProfilePayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    """Validate and persist a per-account risk-profile override.

    Returns 400 with a clear error if any requested override is looser
    than the corresponding firm cap.
    """
    try:
        result = apply_override(
            db=db,
            user_id=user.id,
            account_id=account_id,
            new_limits=payload.as_override(),
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except FirmCapsUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    db.commit()
    return {"data": result.as_dict()}
