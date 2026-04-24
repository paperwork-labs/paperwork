"""Tests for held-symbol vs tracked-universe startup observability (G11)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.models.broker_account import (
    AccountStatus,
    AccountType,
    BrokerAccount,
    BrokerType,
    SyncStatus,
)
from app.models.position import Position, PositionStatus, PositionType, Sleeve
from app.models.user import User
from app.services.silver.market.admin_health_service import AdminHealthService
from app.services.ops.universe_coverage import run_universe_coverage_check


def _user(db_session, email: str) -> User:
    u = User(
        username=email.split("@")[0],
        email=email,
        full_name="U",
        password_hash="x",
    )
    db_session.add(u)
    db_session.flush()
    return u


def _acct(db_session, user_id: int) -> BrokerAccount:
    a = BrokerAccount(
        user_id=user_id,
        account_number=f"A-{user_id}",
        account_name="T",
        broker=BrokerType.IBKR,
        account_type=AccountType.TAXABLE,
        status=AccountStatus.ACTIVE,
        sync_status=SyncStatus.SUCCESS,
    )
    db_session.add(a)
    db_session.flush()
    return a


def _pos(
    db_session, *, uid: int, aid: int, symbol: str
) -> None:
    db_session.add(
        Position(
            user_id=uid,
            account_id=aid,
            symbol=symbol,
            quantity=Decimal("10"),
            position_type=PositionType.LONG,
            status=PositionStatus.OPEN,
            sleeve=Sleeve.ACTIVE.value,
        )
    )
    db_session.flush()


@pytest.mark.usefixtures("db_session")
def test_gap_warns_and_counts(db_session) -> None:
    if db_session is None:
        return
    u = _user(db_session, "a@example.com")
    a = _acct(db_session, u.id)
    _pos(db_session, uid=u.id, aid=a.id, symbol="GOOGL")
    _pos(db_session, uid=u.id, aid=a.id, symbol="RIVN")
    db_session.commit()

    with patch(
        "app.services.silver.market.universe.tracked_symbols_with_source",
        return_value=(["GOOGL"], True),
    ):
        r = run_universe_coverage_check(db_session)

    assert r["gaps_total"] == 1
    assert r["state"] == "degraded"
    assert r["errors"] == 0


@pytest.mark.usefixtures("db_session")
def test_no_positions_healthy(db_session) -> None:
    if db_session is None:
        return
    u = _user(db_session, "b@example.com")
    _acct(db_session, u.id)
    db_session.commit()

    with patch(
        "app.services.silver.market.universe.tracked_symbols_with_source",
        return_value=(["SPY"], True),
    ):
        r = run_universe_coverage_check(db_session)

    assert r["gaps_total"] == 0
    assert r["state"] == "healthy"
    assert r["positions_total"] == 0


@pytest.mark.usefixtures("db_session")
def test_tracked_universe_load_error_surfaces_without_raising(db_session) -> None:
    if db_session is None:
        return
    with patch(
        "app.services.silver.market.universe.tracked_symbols_with_source",
        side_effect=RuntimeError("boom"),
    ):
        r = run_universe_coverage_check(db_session)

    assert r["state"] == "error"
    assert r["errors"] == 1
    assert r["gaps_total"] == 0
    assert "boom" in (r.get("error_detail") or "")


def test_admin_health_universe_degraded_uses_no_silent_ok() -> None:
    with patch(
        "app.services.ops.universe_coverage.read_universe_coverage_for_admin_health",
        return_value={
            "state": "degraded",
            "gaps_total": 2,
            "users_checked": 1,
            "positions_total": 2,
            "errors": 0,
            "checked_at": "2026-01-01T00:00:00+00:00",
        },
    ):
        svc = AdminHealthService()
        dim = svc._build_universe_coverage_dimension()
    assert dim["state"] == "degraded"
    assert dim["status"] in ("yellow",)  # not green — gaps must not look healthy
    assert dim.get("gaps_total") == 2
    assert "Universe gap" in (dim.get("reason") or "")
