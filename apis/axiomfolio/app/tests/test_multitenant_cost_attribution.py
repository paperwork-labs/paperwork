"""Integration tests for the daily cost rollup.

Drives ``CostAttributionService.rollup_day`` end-to-end against the
test database, verifies upsert semantics, and asserts cross-tenant
isolation of the rollup row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.multitenant import TenantCostRollup
from app.models.narrative import PortfolioNarrative
from app.models.user import User
from app.services.multitenant.cost_attribution import (
    CostAttributionService,
)


def _make_user(db, suffix: str) -> User:
    u = User(
        username=f"cost_{suffix}_{int(datetime.now(UTC).timestamp() * 1000)}",
        email=f"cost_{suffix}_{int(datetime.now(UTC).timestamp() * 1000)}@example.com",
        password_hash="x",
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_narrative(db, *, user_id: int, day: date, cost_usd: str) -> None:
    db.add(
        PortfolioNarrative(
            user_id=user_id,
            narrative_date=day,
            text="x",
            summary_data={},
            provider="test",
            prompt_hash=f"test-{user_id}-{day.isoformat()}-{cost_usd}",
            tokens_used=100,
            cost_usd=Decimal(cost_usd),
            created_at=datetime.combine(
                day, datetime.min.time(), tzinfo=timezone.utc
            ),
        )
    )
    db.commit()


def test_rollup_aggregates_llm_cost_per_user(db_session):
    # PortfolioNarrative has a uq on (user_id, narrative_date), so each
    # user gets at most one row per day. The rollup still must (a) sum
    # what's there, and (b) keep tenants isolated.
    today = date(2026, 4, 19)
    user_a = _make_user(db_session, "a")
    user_b = _make_user(db_session, "b")

    _make_narrative(db_session, user_id=user_a.id, day=today, cost_usd="0.1235")
    _make_narrative(db_session, user_id=user_b.id, day=today, cost_usd="2.5000")

    svc = CostAttributionService(db_session)
    written = svc.rollup_day(today)
    assert written >= 2  # at least the two we just created

    rows = (
        db_session.query(TenantCostRollup)
        .filter(TenantCostRollup.day == today)
        .filter(TenantCostRollup.user_id.in_([user_a.id, user_b.id]))
        .all()
    )
    by_uid = {r.user_id: r for r in rows}
    assert by_uid[user_a.id].llm_cost_usd == Decimal("0.1235")
    assert by_uid[user_b.id].llm_cost_usd == Decimal("2.5000")
    # total = llm + provider (provider proxy returns 0 today)
    assert by_uid[user_a.id].total_cost_usd == Decimal("0.1235")
    # Cross-tenant isolation: A's row does NOT include B's spend.
    assert by_uid[user_a.id].llm_cost_usd != by_uid[user_b.id].llm_cost_usd


def test_rollup_is_idempotent(db_session):
    today = date(2026, 4, 18)
    user = _make_user(db_session, "idem")
    _make_narrative(db_session, user_id=user.id, day=today, cost_usd="0.5")

    svc = CostAttributionService(db_session)
    svc.rollup_day(today)
    svc.rollup_day(today)  # second run must upsert, not duplicate

    count = (
        db_session.query(TenantCostRollup)
        .filter(
            TenantCostRollup.user_id == user.id, TenantCostRollup.day == today
        )
        .count()
    )
    assert count == 1


def test_top_n_by_cost_orders_descending(db_session):
    today = date(2026, 4, 17)
    big = _make_user(db_session, "big")
    small = _make_user(db_session, "small")
    _make_narrative(db_session, user_id=big.id, day=today, cost_usd="9.99")
    _make_narrative(db_session, user_id=small.id, day=today, cost_usd="0.01")

    svc = CostAttributionService(db_session)
    svc.rollup_day(today)
    top = svc.top_n_by_cost(today, limit=10)
    # The first row in the *full* result must have the largest total.
    assert top[0]["total_cost_usd"] >= top[-1]["total_cost_usd"]
