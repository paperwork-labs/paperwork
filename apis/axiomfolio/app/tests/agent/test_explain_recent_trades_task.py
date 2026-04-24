"""
Tests for the daily ``explain_recent_trades`` Celery backfill.

What we lock in:

* Counter invariant: ``considered == explained + skipped_cached +
  skipped_no_user + failed`` (no silent drift).
* Idempotency: a second run inside the same window does NOT re-explain
  orders that already have a row.
* Out-of-window orders are ignored.
* Orders with ``user_id IS NULL`` are counted as ``skipped_no_user`` so
  the cross-tenant gap is visible in ops counters.
* Unfilled / preview orders are not picked up.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.services.agent.anomaly_explainer.provider import StubLLMProvider
from app.services.agent.trade_decision_explainer import TradeDecisionExplainer
from app.tasks.agent.explain_recent_trades import _run_backfill


def _good_payload() -> str:
    return json.dumps(
        {
            "trigger": "manual",
            "headline": "Backfill payload",
            "rationale_bullets": ["Stage 2A confirmed.", "RSI 58."],
            "risk_context": {
                "position_size_label": "1.5% equity",
                "stop_placement": "ATR-based",
                "regime_alignment": "R2 long bias",
            },
            "outcome_so_far": {"status": "open", "summary": "+1%"},
            "narrative": "Backfill narrative.",
        }
    )


def _make_user(db_session, *, email: str):
    from app.models import User

    u = User(
        username=email.split("@")[0],
        email=email,
        first_name="T",
        last_name="U",
        password_hash="x" * 32,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_order(
    db_session,
    *,
    user_id: Optional[int],
    status: str = "filled",
    filled_at: Optional[datetime] = None,
    symbol: str = "AAPL",
):
    from app.models import Order

    now = datetime.now(timezone.utc)
    o = Order(
        symbol=symbol,
        side="buy",
        order_type="market",
        status=status,
        quantity=10.0,
        filled_quantity=10.0 if status in ("filled", "partially_filled") else 0.0,
        filled_avg_price=150.0,
        decision_price=150.0,
        broker_type="ibkr",
        source="manual",
        user_id=user_id,
        submitted_at=(filled_at or now) - timedelta(minutes=5),
        filled_at=filled_at or now,
    )
    db_session.add(o)
    db_session.flush()
    return o


@pytest.mark.usefixtures("db_session")
class TestRunBackfill:
    def test_explains_recent_filled_orders_and_counters_balance(
        self, db_session
    ):
        if db_session is None:
            pytest.skip("DB unavailable")
        user = _make_user(db_session, email="task-user-a@example.com")
        # 3 orders inside the window, all filled, none explained yet
        for _ in range(3):
            _make_order(db_session, user_id=user.id)
        provider = StubLLMProvider([_good_payload()] * 3)
        explainer = TradeDecisionExplainer(provider=provider)

        result = _run_backfill(
            lookback_hours=24, explainer=explainer, db=db_session
        )
        assert result["considered"] == 3
        assert result["explained"] == 3
        assert result["skipped_cached"] == 0
        assert result["failed"] == 0
        assert (
            result["explained"]
            + result["skipped_cached"]
            + result["skipped_no_user"]
            + result["failed"]
            == result["considered"]
        )

    def test_idempotent_second_run_skips_cached(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        user = _make_user(db_session, email="task-user-b@example.com")
        for _ in range(2):
            _make_order(db_session, user_id=user.id)
        provider = StubLLMProvider([_good_payload()] * 2)
        explainer = TradeDecisionExplainer(provider=provider)

        first = _run_backfill(
            lookback_hours=24, explainer=explainer, db=db_session
        )
        assert first["explained"] == 2

        # Second run with NO scripted responses must not call the LLM.
        # If it does, StubLLMProvider raises -> the test fails.
        provider2 = StubLLMProvider([])
        explainer2 = TradeDecisionExplainer(provider=provider2)
        second = _run_backfill(
            lookback_hours=24, explainer=explainer2, db=db_session
        )
        assert second["explained"] == 0
        assert second["skipped_cached"] == 2
        assert provider2.calls == []

    def test_out_of_window_orders_are_ignored(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        user = _make_user(db_session, email="task-user-c@example.com")
        # 3 days ago is outside a 24h window
        old = datetime.now(timezone.utc) - timedelta(days=3)
        _make_order(db_session, user_id=user.id, filled_at=old)
        provider = StubLLMProvider([])  # would explode on call
        explainer = TradeDecisionExplainer(provider=provider)

        result = _run_backfill(
            lookback_hours=24, explainer=explainer, db=db_session
        )
        assert result["considered"] == 0
        assert provider.calls == []

    def test_orders_without_user_id_are_skipped_visibly(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        _make_order(db_session, user_id=None)
        provider = StubLLMProvider([])
        explainer = TradeDecisionExplainer(provider=provider)

        result = _run_backfill(
            lookback_hours=24, explainer=explainer, db=db_session
        )
        assert result["considered"] == 1
        assert result["skipped_no_user"] == 1
        assert result["explained"] == 0

    def test_preview_orders_are_not_explained(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        user = _make_user(db_session, email="task-user-d@example.com")
        _make_order(db_session, user_id=user.id, status="preview")
        provider = StubLLMProvider([])
        explainer = TradeDecisionExplainer(provider=provider)

        result = _run_backfill(
            lookback_hours=24, explainer=explainer, db=db_session
        )
        assert result["considered"] == 0

    def test_invalid_lookback_raises(self, db_session):
        # Pure-arg validation should not need DB at all.
        provider = StubLLMProvider([])
        explainer = TradeDecisionExplainer(provider=provider)
        with pytest.raises(ValueError):
            _run_backfill(
                lookback_hours=0, explainer=explainer, db=db_session
            )
