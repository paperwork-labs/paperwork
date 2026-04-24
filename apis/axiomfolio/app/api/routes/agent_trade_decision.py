"""
Trade Decision Explainer API routes.

GET    /api/v1/agent/trade-decisions/{order_id}              -- explain or
                                                                cached
POST   /api/v1/agent/trade-decisions/{order_id}/regenerate   -- bump
                                                                version

Both routes are tier-gated to ``brain.trade_decision_explainer`` (Pro+
in :mod:`app.services.billing.feature_catalog`). Tenant scoping is
enforced inside the explainer (``Order.user_id == current_user.id`` is
checked before the lineage build) -- there is **no admin override**:
even an OWNER role cannot read another user's explanation through this
route. Operators can use the audit-trail dashboard for that.

Why split GET vs POST + ``regenerate``:

* ``GET`` is cheap, idempotent, and safe to call from the trades drawer
  on every open. It returns the latest persisted explanation if one
  exists; otherwise it generates one on-demand (so the user doesn't
  have to wait for the daily Celery task to backfill).
* ``POST .../regenerate`` writes a new version row. We never overwrite
  history -- this lets the user see how the explanation changed if we
  improve the prompt, and gives us a queryable trail for audit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_feature
from app.database import get_db
from app.models.user import User
from app.services.agent.trade_decision_explainer import (
    OrderNotFoundError,
    TradeDecisionExplainer,
    TradeDecisionExplainerError,
    explainer_result_to_dict,
)

logger = logging.getLogger(__name__)


router = APIRouter()


_FEATURE_KEY = "brain.trade_decision_explainer"


class TradeDecisionResponse(BaseModel):
    """Wire-shape returned to the trades drawer.

    We keep this thin and lossless -- the structured payload lives in
    ``payload`` so prompt-schema evolution doesn't force an API
    breaking change.
    """

    row_id: int
    order_id: int
    user_id: int
    version: int
    trigger_type: str
    schema_version: str
    model_used: str
    is_fallback: bool
    cost_usd: str = Field(description="Decimal as string to avoid IEEE-754 drift.")
    prompt_token_count: int
    completion_token_count: int
    payload: Dict[str, Any]
    narrative: str
    generated_at: str | None
    reused: bool


def _to_response(payload: Dict[str, Any]) -> TradeDecisionResponse:
    return TradeDecisionResponse.model_validate(payload)


@router.get(
    "/trade-decisions/{order_id}",
    response_model=TradeDecisionResponse,
    summary="Explain (or fetch cached) why an order was placed",
)
async def get_trade_decision_explanation(
    order_id: int,
    current_user: User = Depends(require_feature(_FEATURE_KEY)),
    db: Session = Depends(get_db),
) -> TradeDecisionResponse:
    """Return the latest explanation for ``order_id`` belonging to the
    current user. Generates one on-demand on a cache miss."""
    explainer = TradeDecisionExplainer()
    try:
        result = explainer.explain(
            db, order_id=order_id, user_id=current_user.id
        )
        db.commit()
    except OrderNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TradeDecisionExplainerError as e:
        db.rollback()
        logger.warning(
            "trade-decision GET failed for order=%s user=%s: %s",
            order_id,
            current_user.id,
            e,
        )
        raise HTTPException(
            status_code=500, detail="Trade decision explainer failed"
        ) from e
    return _to_response(explainer_result_to_dict(result))


@router.post(
    "/trade-decisions/{order_id}/regenerate",
    response_model=TradeDecisionResponse,
    status_code=201,
    summary="Force a new versioned explanation row for an order",
)
async def regenerate_trade_decision_explanation(
    order_id: int,
    current_user: User = Depends(require_feature(_FEATURE_KEY)),
    db: Session = Depends(get_db),
) -> TradeDecisionResponse:
    """Write a new ``TradeDecisionExplanation`` with version =
    ``previous + 1``. The previous rows are preserved.

    Owner-only? No -- the user owns their own explanations and may
    regenerate at any time. Cost cap is enforced by the LLM provider's
    per-call ``max_tokens`` limit and by the (future) gateway budget.
    """
    explainer = TradeDecisionExplainer()
    try:
        result = explainer.regenerate(
            db, order_id=order_id, user_id=current_user.id
        )
        db.commit()
    except OrderNotFoundError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TradeDecisionExplainerError as e:
        db.rollback()
        logger.warning(
            "trade-decision regenerate failed for order=%s user=%s: %s",
            order_id,
            current_user.id,
            e,
        )
        raise HTTPException(
            status_code=500, detail="Trade decision explainer failed"
        ) from e
    return _to_response(explainer_result_to_dict(result))
