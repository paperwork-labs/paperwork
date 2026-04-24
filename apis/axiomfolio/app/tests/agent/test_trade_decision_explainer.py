"""
Tests for TradeDecisionExplainer.

Goals:

* Lock in the prompt JSON schema + ``SCHEMA_VERSION`` so a casual
  prompt edit cannot drop a required field on the floor.
* Prove the trigger resolver picks the most specific lineage label.
* Prove the explainer caches: a second ``explain`` call after a
  successful first one returns the same row with ``reused=True`` and
  does NOT touch the LLM provider.
* Prove ``regenerate`` writes a strictly higher version row.
* Prove cross-tenant isolation: User B cannot fetch User A's order
  explanation through the service.
* Prove the malformed-LLM path persists a fallback row with
  ``is_fallback=True`` (no silent fallback).

The schema/trigger/payload tests are DB-free. The explain/regenerate/
cross-tenant tests use the ``db_session`` fixture so they exercise the
real model + UNIQUE constraint at the DB layer.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

import pytest

from app.services.agent.anomaly_explainer.provider import (
    AlwaysFailingProvider,
    StubLLMProvider,
)
from app.services.agent.explanation_prompts import (
    OUTPUT_JSON_SCHEMA,
    SCHEMA_VERSION,
    SYSTEM_PROMPT,
    TRIGGER_TYPES,
    build_user_prompt,
    trigger_hint,
)
from app.services.agent.trade_decision_explainer import (
    OrderNotFoundError,
    TradeDecisionExplainer,
    _resolve_trigger_type,
    _validate_payload,
    explainer_result_to_dict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _good_llm_payload(trigger: str = "manual") -> str:
    return json.dumps(
        {
            "trigger": trigger,
            "headline": "Bought AAPL on Stage 2A breakout",
            "rationale_bullets": [
                "Stage 2A confirmed by SMA50 > SMA150 > SMA200.",
                "RSI 58 -- not overbought.",
                "Regime R2 (positive) so equity exposure is permitted.",
            ],
            "risk_context": {
                "position_size_label": "approx 1.5% of equity",
                "stop_placement": "ATR-based, ~7% below entry",
                "regime_alignment": "Aligned with R2 long bias",
            },
            "outcome_so_far": {
                "status": "open",
                "summary": "Position currently +2.3% above entry.",
                "pnl_label": "+2.3%",
            },
            "narrative": (
                "AAPL printed a Stage 2A confirmation and the regime supported "
                "long exposure. Risk was sized to ~1.5% of equity with an "
                "ATR-based stop. Position is currently in profit."
            ),
        }
    )


class _FakeOrder:
    """Minimal Order stand-in for trigger-resolver tests."""

    def __init__(self, source: Optional[str] = None) -> None:
        self.source = source


class _FakePick:
    pass


class _FakeSignal:
    pass


class _FakeStrategy:
    pass


# ---------------------------------------------------------------------------
# Schema lock-in
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_schema_version_locked(self):
        # Bumping SCHEMA_VERSION forces every cached row to be regenerated.
        # A casual prompt tweak should not silently invalidate the cache.
        assert SCHEMA_VERSION == "trade_decision.v1"

    def test_trigger_types_match_db_check_constraint(self):
        # The DB check constraint hard-codes these strings (migration 0051);
        # a divergence here means rows would fail to insert at runtime.
        assert set(TRIGGER_TYPES) == {
            "pick",
            "scan",
            "rebalance",
            "manual",
            "strategy",
            "unknown",
        }

    def test_output_schema_required_fields(self):
        required = set(OUTPUT_JSON_SCHEMA["required"])
        assert required == {
            "trigger",
            "headline",
            "rationale_bullets",
            "risk_context",
            "outcome_so_far",
            "narrative",
        }

    def test_system_prompt_forbids_recommending_new_trades(self):
        # The single most important guardrail: this is a historical
        # explainer, not a signal generator.
        assert "never recommend" in SYSTEM_PROMPT.lower()
        assert "never invent" in SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# Trigger resolution
# ---------------------------------------------------------------------------


class TestTriggerResolver:
    def test_pick_wins_over_signal_and_strategy(self):
        out = _resolve_trigger_type(
            order=_FakeOrder(source="manual"),
            pick=_FakePick(),
            signal=_FakeSignal(),
            strategy=_FakeStrategy(),
        )
        assert out == "pick"

    def test_rebalance_source_overrides_strategy_and_signal(self):
        out = _resolve_trigger_type(
            order=_FakeOrder(source="rebalance"),
            pick=None,
            signal=_FakeSignal(),
            strategy=_FakeStrategy(),
        )
        assert out == "rebalance"

    def test_strategy_when_strategy_present_no_pick_no_rebalance(self):
        out = _resolve_trigger_type(
            order=_FakeOrder(source="strategy"),
            pick=None,
            signal=None,
            strategy=_FakeStrategy(),
        )
        assert out == "strategy"

    def test_scan_when_only_signal_present(self):
        out = _resolve_trigger_type(
            order=_FakeOrder(source="manual"),
            pick=None,
            signal=_FakeSignal(),
            strategy=None,
        )
        assert out == "scan"

    def test_manual_when_source_manual_and_no_lineage(self):
        out = _resolve_trigger_type(
            order=_FakeOrder(source="manual"),
            pick=None,
            signal=None,
            strategy=None,
        )
        assert out == "manual"

    def test_unknown_when_no_lineage_and_unknown_source(self):
        out = _resolve_trigger_type(
            order=_FakeOrder(source=None),
            pick=None,
            signal=None,
            strategy=None,
        )
        assert out == "unknown"


# ---------------------------------------------------------------------------
# Payload validation
# ---------------------------------------------------------------------------


class TestValidatePayload:
    def test_good_payload_parses(self):
        payload = _validate_payload(_good_llm_payload())
        assert payload["trigger"] == "manual"
        assert payload["rationale_bullets"]

    def test_empty_string_rejected(self):
        with pytest.raises(Exception):
            _validate_payload("")

    def test_invalid_json_rejected(self):
        with pytest.raises(Exception):
            _validate_payload("not json")

    def test_missing_required_field_rejected(self):
        bad = json.dumps(
            {
                "trigger": "manual",
                "headline": "x",
                "rationale_bullets": ["x"],
                "risk_context": {
                    "position_size_label": "x",
                    "stop_placement": "x",
                    "regime_alignment": "x",
                },
                # outcome_so_far missing
                "narrative": "x",
            }
        )
        with pytest.raises(Exception):
            _validate_payload(bad)

    def test_invalid_trigger_value_rejected(self):
        good = json.loads(_good_llm_payload())
        good["trigger"] = "totally-made-up"
        with pytest.raises(Exception):
            _validate_payload(json.dumps(good))

    def test_empty_rationale_bullets_rejected(self):
        good = json.loads(_good_llm_payload())
        good["rationale_bullets"] = []
        with pytest.raises(Exception):
            _validate_payload(json.dumps(good))


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    def test_prompt_embeds_all_blocks_as_json(self):
        prompt = build_user_prompt(
            trigger_type="pick",
            order_payload={"order_id": 42, "symbol": "AAPL"},
            lineage_payload={"trigger_type": "pick"},
            market_snapshot_payload={"snapshot": {"rsi": 58.0}},
            outcome_payload={"status": "open"},
        )
        # JSON-encoded blocks make the prompt safe against backticks and
        # newlines in free-text fields like reason_summary.
        assert '"order_id": 42' in prompt
        assert '"symbol": "AAPL"' in prompt
        # Trigger hint for "pick" must mention validator pseudonym.
        assert "validator pseudonym" in trigger_hint("pick").lower()

    def test_unknown_trigger_falls_back_to_unknown_hint(self):
        # Garbage triggers should never appear in the rendered hint;
        # the "unknown" hint is honest about the lineage gap.
        prompt = build_user_prompt(
            trigger_type="garbage",
            order_payload={},
            lineage_payload={},
            market_snapshot_payload={},
            outcome_payload={},
        )
        assert "audit trail did not preserve" in prompt


# ---------------------------------------------------------------------------
# DB-backed end-to-end (uses db_session fixture)
# ---------------------------------------------------------------------------


def _make_user(db_session, *, email: str):
    from app.models import User

    u = User(
        username=email.split("@")[0],
        email=email,
        first_name="Test",
        last_name="User",
        password_hash="x" * 32,
    )
    db_session.add(u)
    db_session.flush()
    return u


def _make_order(db_session, *, user_id: int, symbol: str = "AAPL"):
    from app.models import Order

    now = datetime.now(timezone.utc)
    o = Order(
        symbol=symbol,
        side="buy",
        order_type="market",
        status="filled",
        quantity=10.0,
        filled_quantity=10.0,
        filled_avg_price=150.0,
        decision_price=150.0,
        broker_type="ibkr",
        source="manual",
        user_id=user_id,
        submitted_at=now - timedelta(minutes=5),
        filled_at=now,
    )
    db_session.add(o)
    db_session.flush()
    return o


@pytest.mark.usefixtures("db_session")
class TestExplainerEndToEnd:
    def test_first_explain_writes_row_second_returns_cached(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        provider = StubLLMProvider([_good_llm_payload(trigger="manual")])
        explainer = TradeDecisionExplainer(provider=provider)

        user = _make_user(db_session, email="trader-a@example.com")
        order = _make_order(db_session, user_id=user.id)

        first = explainer.explain(
            db_session, order_id=order.id, user_id=user.id
        )
        assert first.reused is False
        assert first.is_fallback is False
        assert first.version == 1
        # Trigger comes from the resolver, NOT from the LLM (the explainer
        # forces it so the LLM cannot rewrite the audit-derived label).
        assert first.trigger_type == "manual"
        # Provider was hit exactly once.
        assert len(provider.calls) == 1

        second = explainer.explain(
            db_session, order_id=order.id, user_id=user.id
        )
        assert second.reused is True
        assert second.row_id == first.row_id
        # Provider must NOT have been called again.
        assert len(provider.calls) == 1

    def test_regenerate_bumps_version(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        provider = StubLLMProvider(
            [_good_llm_payload(), _good_llm_payload()]
        )
        explainer = TradeDecisionExplainer(provider=provider)

        user = _make_user(db_session, email="trader-b@example.com")
        order = _make_order(db_session, user_id=user.id)

        v1 = explainer.explain(
            db_session, order_id=order.id, user_id=user.id
        )
        v2 = explainer.regenerate(
            db_session, order_id=order.id, user_id=user.id
        )
        assert v2.version == v1.version + 1
        assert v2.row_id != v1.row_id
        assert len(provider.calls) == 2

    def test_cross_tenant_user_b_cannot_see_user_a_order(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        provider = StubLLMProvider([_good_llm_payload()])
        explainer = TradeDecisionExplainer(provider=provider)

        user_a = _make_user(db_session, email="alice@example.com")
        user_b = _make_user(db_session, email="bob@example.com")
        order_a = _make_order(db_session, user_id=user_a.id)

        with pytest.raises(OrderNotFoundError):
            explainer.explain(
                db_session, order_id=order_a.id, user_id=user_b.id
            )
        # Provider must not be touched on a cross-tenant attempt.
        assert provider.calls == []

    def test_failing_provider_persists_fallback_row(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        explainer = TradeDecisionExplainer(
            provider=AlwaysFailingProvider("test")
        )

        user = _make_user(db_session, email="trader-c@example.com")
        order = _make_order(db_session, user_id=user.id)

        result = explainer.explain(
            db_session, order_id=order.id, user_id=user.id
        )
        # No silent fallback: the row exists and is_fallback=True so the
        # UI can render a degraded badge.
        assert result.is_fallback is True
        assert result.version == 1
        assert result.payload["trigger"] == "manual"
        assert result.payload["rationale_bullets"], "fallback must still cite something"


# ---------------------------------------------------------------------------
# Result serializer
# ---------------------------------------------------------------------------


class TestResultSerializer:
    def test_decimal_to_str_in_dict(self, db_session):
        if db_session is None:
            pytest.skip("DB unavailable")
        provider = StubLLMProvider([_good_llm_payload()])
        explainer = TradeDecisionExplainer(provider=provider)
        user = _make_user(db_session, email="trader-d@example.com")
        order = _make_order(db_session, user_id=user.id)
        result = explainer.explain(
            db_session, order_id=order.id, user_id=user.id
        )
        d = explainer_result_to_dict(result)
        # Money fields are strings, not floats, in the wire payload.
        assert isinstance(d["cost_usd"], str)
        # generated_at is ISO 8601, never None for a fresh row.
        assert d["generated_at"] is not None
