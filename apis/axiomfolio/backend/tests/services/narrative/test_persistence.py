"""Persistence tests for portfolio narratives."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from backend.models.narrative import PortfolioNarrative
from backend.models.user import User
from backend.services.narrative.persistence import persist_narrative
from backend.services.narrative.provider import NarrativeResult


def test_persist_narrative_idempotent_within_fresh_window(db_session):
    suffix = uuid.uuid4().hex[:10]
    u = User(
        email=f"narr_persist_{suffix}@example.com",
        username=f"narr_persist_{suffix}",
        password_hash="x",
    )
    db_session.add(u)
    db_session.commit()

    narrative_date = date(2026, 4, 10)
    summary = {"target_date": narrative_date.isoformat(), "regime": "R2 (Bull Extended)"}
    r1 = NarrativeResult(
        text="first version",
        provider="stub",
        model="stub",
        tokens_used=0,
        cost_usd=None,
        is_fallback=False,
        prompt_hash="a" * 64,
    )
    row1 = persist_narrative(db_session, u.id, summary, r1, narrative_date)
    db_session.commit()
    assert row1.id is not None
    assert row1.text == "first version"

    r2 = NarrativeResult(
        text="second version",
        provider="stub",
        model="stub",
        tokens_used=0,
        cost_usd=None,
        is_fallback=False,
        prompt_hash="b" * 64,
    )
    row2 = persist_narrative(db_session, u.id, summary, r2, narrative_date)
    db_session.commit()
    assert row2.id == row1.id
    assert row2.text == "first version"


def test_persist_narrative_updates_after_fresh_window(db_session):
    suffix = uuid.uuid4().hex[:10]
    u = User(
        email=f"narr_persist2_{suffix}@example.com",
        username=f"narr_persist2_{suffix}",
        password_hash="x",
    )
    db_session.add(u)
    db_session.commit()

    narrative_date = date(2026, 4, 11)
    summary = {"target_date": narrative_date.isoformat()}
    r1 = NarrativeResult(
        text="v1",
        provider="stub",
        model="stub",
        tokens_used=0,
        cost_usd=None,
        is_fallback=False,
        prompt_hash="c" * 64,
    )
    row1 = persist_narrative(db_session, u.id, summary, r1, narrative_date)
    db_session.commit()

    old_created = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.query(PortfolioNarrative).filter(PortfolioNarrative.id == row1.id).update(
        {"created_at": old_created},
        synchronize_session=False,
    )
    db_session.commit()

    r2 = NarrativeResult(
        text="v2",
        provider="fallback_template",
        model=None,
        tokens_used=None,
        cost_usd=None,
        is_fallback=True,
        prompt_hash="d" * 64,
    )
    row2 = persist_narrative(db_session, u.id, summary, r2, narrative_date)
    db_session.commit()
    assert row2.id == row1.id
    assert row2.text == "v2"
    assert row2.is_fallback is True
    assert row2.cost_usd is None
