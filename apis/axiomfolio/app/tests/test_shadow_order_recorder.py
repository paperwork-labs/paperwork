"""Tests for the shadow (paper) order recorder + mark-to-market task.

Scenarios covered:
  1. happy path — recorder persists an executed-at-simulation-time row
  2. risk-gate-denied order still persists with the verdict
  3. cross-tenant isolation — user A cannot see user B's shadow orders via
     ``OrderManager.submit`` diversion
  4. mark-to-market computes simulated P&L from a frozen ``MarketSnapshot``
  5. disabling ``SHADOW_TRADING_MODE`` routes into the real submit path
     (broker mocked)

A separate regression test asserts the flag-gated ``if`` block inside
``order_manager.py`` exists exactly once.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

try:
    from app.models import User
    from app.models.market_data import MarketSnapshot
    from app.models.order import Order, OrderSide, OrderStatus, OrderType
    from app.models.shadow_order import ShadowOrder, ShadowOrderStatus
    from app.models.user import UserRole
    from app.services.execution.order_manager import OrderManager
    from app.services.execution.shadow_mark_to_market import (
        mark_open_shadow_orders,
    )
    from app.services.execution.shadow_order_recorder import (
        ShadowOrderRecorder,
    )

    AVAILABLE = True
except Exception:  # pragma: no cover - import guard mirrors other tests
    AVAILABLE = False


pytestmark = pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user(db_session, *, email: str, username: str) -> User:
    user = User(
        email=email,
        username=username,
        password_hash="dummy",
        role=UserRole.OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_preview_order(db_session, *, user: User, symbol: str, qty: float = 10.0) -> Order:
    order = Order(
        symbol=symbol.upper(),
        side=OrderSide.BUY.value,
        order_type=OrderType.MARKET.value,
        status=OrderStatus.PREVIEW.value,
        quantity=qty,
        limit_price=None,
        stop_price=None,
        source="manual",
        broker_type="ibkr",
        user_id=user.id,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def _seed_snapshot(
    db_session,
    *,
    symbol: str,
    price: float,
    analysis_timestamp: datetime | None = None,
) -> MarketSnapshot:
    now = datetime.now(UTC)
    row = MarketSnapshot(
        symbol=symbol.upper(),
        analysis_type="technical_snapshot",
        expiry_timestamp=now + timedelta(days=1),
        current_price=price,
        analysis_timestamp=analysis_timestamp or now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def user_a(db_session):
    return _make_user(db_session, email="shadow_a@example.com", username="shadow_a")


@pytest.fixture
def user_b(db_session):
    return _make_user(db_session, email="shadow_b@example.com", username="shadow_b")


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_happy_path_records_executed_shadow_order(db_session, user_a):
    """A preview-status order with a healthy snapshot price records as
    ``executed_at_simulation_time`` with the risk-gate verdict attached."""
    _seed_snapshot(db_session, symbol="ACME", price=100.0)
    order = _make_preview_order(db_session, user=user_a, symbol="ACME", qty=10)

    result = ShadowOrderRecorder(session=db_session).record(order_id=order.id, user_id=user_a.id)

    assert result["shadow"] is True
    assert result["status"] == ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME.value
    row = db_session.query(ShadowOrder).filter(ShadowOrder.id == result["shadow_order_id"]).one()
    assert row.user_id == user_a.id
    assert row.symbol == "ACME"
    assert row.side == "buy"
    assert row.qty == Decimal("10")
    assert row.source_order_id == order.id
    assert row.intended_fill_price == Decimal("100")
    assert row.risk_gate_verdict is not None
    assert row.risk_gate_verdict.get("allowed") is True


# ---------------------------------------------------------------------------
# 2. Risk-gate-denied orders still persist
# ---------------------------------------------------------------------------


def test_risk_gate_denied_order_still_persists_with_verdict(db_session, user_a):
    """Even when the risk gate rejects, we still record a ledger row so a
    downstream observer (admin panel, report) can see the denied intent."""
    # No snapshot for this symbol -> estimate_price raises RiskViolation.
    order = _make_preview_order(db_session, user=user_a, symbol="NOPRICE", qty=5)

    result = ShadowOrderRecorder(session=db_session).record(order_id=order.id, user_id=user_a.id)

    assert result["status"] == ShadowOrderStatus.WOULD_DENY_BY_RISK_GATE.value
    row = db_session.query(ShadowOrder).filter(ShadowOrder.id == result["shadow_order_id"]).one()
    assert row.intended_fill_price is None
    assert row.intended_fill_at is None
    verdict = row.risk_gate_verdict or {}
    assert verdict.get("allowed") is False
    assert "No price available" in verdict.get("reason", "")


# ---------------------------------------------------------------------------
# 3. Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_cross_tenant_isolation(db_session, user_a, user_b):
    """User B cannot divert User A's order through the recorder, and the
    shadow ledger stays user-scoped."""
    _seed_snapshot(db_session, symbol="ACME", price=100.0)
    a_order = _make_preview_order(db_session, user=user_a, symbol="ACME", qty=3)

    # User B attempts to divert User A's order — returns not-found, no row.
    result = ShadowOrderRecorder(session=db_session).record(order_id=a_order.id, user_id=user_b.id)
    assert result == {"error": "Order not found"}

    b_shadows = db_session.query(ShadowOrder).filter(ShadowOrder.user_id == user_b.id).all()
    assert b_shadows == []

    # Proper divert by the owning user still works.
    result_owner = ShadowOrderRecorder(session=db_session).record(
        order_id=a_order.id, user_id=user_a.id
    )
    owner_row = (
        db_session.query(ShadowOrder)
        .filter(ShadowOrder.id == result_owner["shadow_order_id"])
        .one()
    )
    assert owner_row.user_id == user_a.id
    # Cross-tenant read via the user-scoped query still sees nothing for B.
    assert db_session.query(ShadowOrder).filter(ShadowOrder.user_id == user_b.id).count() == 0


# ---------------------------------------------------------------------------
# 4. Mark-to-market computes correctly using frozen snapshot
# ---------------------------------------------------------------------------


def test_mark_to_market_uses_frozen_snapshot_price(db_session, user_a):
    """After a simulated fill at $100, updating the snapshot to $105 and
    running MtM yields a +$50 P&L for a 10-share long."""
    snap = _seed_snapshot(db_session, symbol="ACME", price=100.0)
    order = _make_preview_order(db_session, user=user_a, symbol="ACME", qty=10)
    result = ShadowOrderRecorder(session=db_session).record(order_id=order.id, user_id=user_a.id)
    assert result["status"] == ShadowOrderStatus.EXECUTED_AT_SIMULATION_TIME.value

    # Advance the snapshot price.
    later = datetime.now(UTC) + timedelta(minutes=15)
    _seed_snapshot(db_session, symbol="ACME", price=105.0, analysis_timestamp=later)

    summary = mark_open_shadow_orders(db_session)

    assert summary["total"] == 1
    assert summary["updated"] == 1
    assert summary["skipped_no_price"] == 0
    assert summary["errors"] == 0
    row = db_session.query(ShadowOrder).filter(ShadowOrder.id == result["shadow_order_id"]).one()
    assert row.status == ShadowOrderStatus.MARKED_TO_MARKET.value
    assert row.last_mark_price == Decimal("105")
    assert row.simulated_pnl == Decimal("50")  # (105 - 100) * 10
    assert row.simulated_pnl_as_of is not None

    # Drift guard: counters must sum to total.
    assert (
        summary["updated"]
        + summary["skipped_no_price"]
        + summary["skipped_no_fill"]
        + summary["errors"]
        == summary["total"]
    )


# ---------------------------------------------------------------------------
# 5. Disabling the flag routes to the real OrderManager path
# ---------------------------------------------------------------------------


def test_flag_off_routes_to_real_submit_path(db_session, user_a, monkeypatch):
    """When ``SHADOW_TRADING_MODE`` is False, the recorder is NOT called; the
    normal submit path runs. We stub the path just past the flag-check by
    asserting that the shadow table stays empty and the recorder method is
    never invoked."""
    _seed_snapshot(db_session, symbol="ACME", price=100.0)
    order = _make_preview_order(db_session, user=user_a, symbol="ACME", qty=2)

    # Flip the flag off for this test only.
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "SHADOW_TRADING_MODE", False, raising=False)

    # Patch the recorder so we can assert it is NEVER called in flag-off mode.
    recorder_call = {"count": 0}

    original_record = ShadowOrderRecorder.record

    def _counting_record(self, **kwargs):  # pragma: no cover - guard
        recorder_call["count"] += 1
        return original_record(self, **kwargs)

    monkeypatch.setattr(ShadowOrderRecorder, "record", _counting_record)

    # Stop the real submit path BEFORE any broker call: intercept the
    # Redis lock helper and force the "blocked" branch so we never reach a
    # broker executor. This is sufficient to prove the flag-off path is
    # live: the code after the flag runs.
    from app.services import cache as cache_module

    class _FakeRedis:
        def set(self, *args, **kwargs):
            return False  # lock NOT acquired -> early return

    monkeypatch.setattr(cache_module, "redis_client", _FakeRedis())

    result = asyncio.run(OrderManager().submit(db_session, order_id=order.id, user_id=user_a.id))

    assert recorder_call["count"] == 0
    # Lock-not-acquired branch returns a specific payload.
    assert result == {"error": "Order submission already in progress"}
    # And no shadow row was created.
    assert db_session.query(ShadowOrder).filter(ShadowOrder.user_id == user_a.id).count() == 0


# ---------------------------------------------------------------------------
# Regression: the flag-gated block in order_manager.py exists exactly once.
# ---------------------------------------------------------------------------


def test_order_manager_flag_gate_exists_exactly_once() -> None:
    """The additive flag-gated divert added for D137 must remain singular.

    A second divert (even well-intentioned) would double-record shadow rows
    or open a silent re-entry path. If this test ever fails, review the
    diff against ``app/services/execution/order_manager.py`` before
    merging.
    """
    path = Path(__file__).resolve().parent.parent / "services" / "execution" / "order_manager.py"
    source = path.read_text()

    if_hits = re.findall(r"if\s+_shadow_settings\.SHADOW_TRADING_MODE\s*:", source)
    assert len(if_hits) == 1, (
        "Expected exactly one flag-gated shadow divert in order_manager.py; "
        f"found {len(if_hits)}. Review the diff before merging."
    )

    recorder_hits = re.findall(
        r"from app\.services\.execution\.shadow_order_recorder import ShadowOrderRecorder",
        source,
    )
    assert len(recorder_hits) == 1, (
        "The ShadowOrderRecorder import must live inside the single "
        f"flag-gated branch; found {len(recorder_hits)} imports."
    )


# ---------------------------------------------------------------------------
# Celery: MtM task must be importable and registered (job_catalog 15m beat)
# ---------------------------------------------------------------------------


def test_shadow_mtm_celery_task_is_registered() -> None:
    import importlib

    importlib.import_module("app.services.execution.shadow_mark_to_market")
    from app.tasks.celery_app import celery_app

    assert "app.services.execution.shadow_mark_to_market.run" in celery_app.tasks
