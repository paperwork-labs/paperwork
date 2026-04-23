"""Tests for per-user Pro+ candidate generation (Beat task)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from backend.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
    SyncStatus,
)
from backend.models.entitlement import Entitlement, EntitlementStatus, SubscriptionTier
from backend.models.market_data import JobRun
from backend.models.position import Position, PositionStatus, PositionType, Sleeve
from backend.models.user import User
from backend.services.picks.candidate_generator import GeneratorRunReport
from backend.tasks.candidates import generate_candidates_daily


def _u(db_session, email: str) -> User:
    u = User(
        username=email.split("@")[0],
        email=email,
        full_name="T",
        password_hash="x",
    )
    db_session.add(u)
    db_session.flush()
    return u


def _ent(db_session, user_id: int, tier: SubscriptionTier) -> None:
    e = Entitlement(
        user_id=user_id,
        tier=tier,
        status=EntitlementStatus.ACTIVE,
    )
    db_session.add(e)
    db_session.flush()


@pytest.mark.usefixtures("db_session")
def test_generate_candidates_daily_tier_gating_and_counters(
    db_session, monkeypatch
) -> None:
    if db_session is None:
        return

    pro = _u(db_session, "proplus@test.com")
    free = _u(db_session, "free@test.com")
    _ent(db_session, pro.id, SubscriptionTier.PRO_PLUS)
    _ent(db_session, free.id, SubscriptionTier.FREE)
    db_session.commit()

    _only = {pro.id, free.id}
    _orig_q = db_session.query

    def _scoped_query(*args, **kwargs):
        q = _orig_q(*args, **kwargs)
        if args and args[0] is User:
            return q.filter(User.id.in_(_only))
        return q

    monkeypatch.setattr(db_session, "query", _scoped_query)
    monkeypatch.setattr(db_session, "close", lambda: None)
    monkeypatch.setattr(
        "backend.tasks.candidates.SessionLocal", lambda: db_session
    )

    fake_report = [
        GeneratorRunReport(
            generator="g1",
            version="1.0",
            produced=5,
            created=2,
            skipped_duplicate=0,
            invalid=0,
        )
    ]

    with patch(
        "backend.tasks.candidates.run_all_generators", return_value=fake_report
    ) as m_run:
        out = generate_candidates_daily.run()

    m_run.assert_called_once()
    _, kwargs = m_run.call_args
    assert kwargs.get("quality_score_user_id") == pro.id

    assert out["users_skipped_no_tier"] == 1
    assert out["users_processed"] == 1
    assert out["errors"] == 0
    assert out["symbols_scanned"] == 5
    assert out["candidates_written"] == 2
    assert out["users_processed"] + out["users_skipped_no_tier"] + out["errors"] == out[
        "total_users"
    ]

    latest = (
        db_session.query(JobRun)
        .filter(JobRun.task_name == "generate_candidates_daily")
        .order_by(JobRun.id.desc())
        .first()
    )
    assert latest is not None
    assert latest.status == "ok"
    assert latest.counters is not None
    assert latest.counters.get("candidates_written") == 2
