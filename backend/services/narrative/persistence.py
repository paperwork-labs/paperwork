"""Persistence helpers for :class:`backend.models.narrative.PortfolioNarrative`."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.narrative import PortfolioNarrative
from backend.services.narrative.provider import NarrativeResult

logger = logging.getLogger(__name__)

_FRESH_WINDOW = timedelta(hours=1)


def fetch_fresh_narrative(
    db: Session, user_id: int, narrative_date: date
) -> Optional[PortfolioNarrative]:
    """Return existing row if written within the last hour (idempotency / dedupe)."""
    row = (
        db.query(PortfolioNarrative)
        .filter(
            PortfolioNarrative.user_id == user_id,
            PortfolioNarrative.narrative_date == narrative_date,
        )
        .one_or_none()
    )
    if row is None:
        return None
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - created
    if age < _FRESH_WINDOW:
        return row
    return None


def persist_narrative(
    db: Session,
    user_id: int,
    summary: dict,
    result: NarrativeResult,
    narrative_date: date,
) -> PortfolioNarrative:
    """Insert or update narrative for (user_id, narrative_date)."""
    existing = (
        db.query(PortfolioNarrative)
        .filter(
            PortfolioNarrative.user_id == user_id,
            PortfolioNarrative.narrative_date == narrative_date,
        )
        .one_or_none()
    )
    if existing is not None:
        created = existing.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created < _FRESH_WINDOW:
            logger.info(
                "narrative: fresh row exists user=%s date=%s id=%s",
                user_id,
                narrative_date,
                existing.id,
            )
            return existing

    now = datetime.now(timezone.utc)

    def _apply_update(target: PortfolioNarrative) -> None:
        target.text = result.text
        target.summary_data = dict(summary)
        target.provider = result.provider
        target.model = result.model
        target.prompt_hash = result.prompt_hash
        target.is_fallback = result.is_fallback
        target.tokens_used = result.tokens_used
        target.cost_usd = result.cost_usd
        target.created_at = now

    if existing is not None:
        _apply_update(existing)
        db.flush()
        return existing

    row = PortfolioNarrative(
        user_id=user_id,
        narrative_date=narrative_date,
        text=result.text,
        summary_data=dict(summary),
        provider=result.provider,
        model=result.model,
        prompt_hash=result.prompt_hash,
        is_fallback=result.is_fallback,
        tokens_used=result.tokens_used,
        cost_usd=result.cost_usd,
    )
    try:
        db.add(row)
        db.flush()
        return row
    except IntegrityError:
        logger.warning(
            "narrative: insert race user=%s date=%s; refetching after rollback",
            user_id,
            narrative_date,
        )
        db.rollback()
        concurrent = (
            db.query(PortfolioNarrative)
            .filter(
                PortfolioNarrative.user_id == user_id,
                PortfolioNarrative.narrative_date == narrative_date,
            )
            .one_or_none()
        )
        if concurrent is None:
            raise
        created = concurrent.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created < _FRESH_WINDOW:
            return concurrent
        _apply_update(concurrent)
        db.flush()
        return concurrent
