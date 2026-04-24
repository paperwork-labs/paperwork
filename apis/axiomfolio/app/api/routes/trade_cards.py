"""Trade cards for the current user.

A trade card is composed on read from a scored :class:`Candidate` plus the
latest :class:`MarketSnapshot`, :class:`MarketRegime`, and the user's broker
account balances. Cards are not persisted — see
``app/services/gold/trade_card_composer.py`` for the composition rules.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.picks import Candidate
from app.models.user import User
from app.services.gold.trade_card_composer import (
    TradeCardComposer,
    _sum_user_account_value,
    trade_card_to_payload,
)
from app.services.silver.regime.regime_engine import get_current_regime

logger = logging.getLogger(__name__)

router = APIRouter()


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/today")
def list_trade_cards_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Return today's trade cards for ``current_user`` ordered by pick score desc.

    Cards are composed per-candidate; a failure in one card's composition logs
    and is surfaced as an error entry so a single bad input cannot take the
    whole page down.
    """
    start = _today_utc_start()
    base_filter = (Candidate.generated_at >= start,)

    total = (
        db.query(func.count(Candidate.id)).filter(*base_filter).scalar() or 0
    )

    rows: List[Candidate] = (
        db.query(Candidate)
        .filter(*base_filter)
        .order_by(
            Candidate.pick_quality_score.desc().nullslast(),
            Candidate.score.desc().nullslast(),
            Candidate.id.desc(),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    composer = TradeCardComposer()
    regime = get_current_regime(db)
    account_value = _sum_user_account_value(db, current_user.id)

    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    for idx, cand in enumerate(rows):
        try:
            card = composer.compose(
                db,
                candidate=cand,
                user=current_user,
                rank=offset + idx + 1,
                regime=regime,
                account_value_override=account_value,
            )
            items.append(trade_card_to_payload(card))
        except Exception as e:
            logger.warning(
                "trade_cards: composition failed for candidate_id=%s symbol=%s user_id=%s: %s",
                cand.id,
                cand.symbol,
                current_user.id,
                e,
            )
            errors.append(
                {
                    "candidate_id": cand.id,
                    "symbol": cand.symbol,
                    "error": str(e)[:200],
                }
            )

    return {
        "items": items,
        "errors": errors,
        "total": total,
        "limit": limit,
        "offset": offset,
        "user_id": current_user.id,
    }
