"""Tests for :mod:`backend.tasks.portfolio.plaid_sync`.

Focus: the per-connection counter loop:

* Counters are emitted with keys ``total``, ``written``, ``skipped_no_holdings``,
  ``errors`` and the invariant ``written + skipped_no_holdings + errors == total``
  holds across mixed outcomes.
* A per-connection exception does NOT crash the task; it's captured as
  ``errors`` and the connection is marked ``error`` with ``last_error`` set.
* Counter-drift inside ``persist_holdings`` would propagate (AssertionError)
  — simulated via a service that raises AssertionError.
"""

from __future__ import annotations

from typing import Dict
from unittest.mock import patch

import pytest

try:
    from backend.models.broker_account import (
        AccountStatus,
        AccountType,
        BrokerAccount,
        BrokerType,
    )
    from backend.models.plaid_connection import (
        PlaidConnection,
        PlaidConnectionStatus,
    )
    from backend.models.user import User, UserRole
    from backend.tasks.portfolio import plaid_sync as plaid_sync_mod
    AVAILABLE = True
except Exception:  # pragma: no cover
    AVAILABLE = False


pytestmark = pytest.mark.skipif(not AVAILABLE, reason="Dependencies not available")


def _mk_user(db_session, suffix: str) -> User:
    user = User(
        email=f"plaid_task_{suffix}@example.com",
        username=f"plaid_task_{suffix}",
        password_hash="x",
        role=UserRole.ANALYST,
        is_active=True,
        is_approved=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _mk_conn(db_session, user_id: int, *, item_id: str, status: str) -> PlaidConnection:
    conn = PlaidConnection(
        user_id=user_id,
        item_id=item_id,
        access_token_encrypted="ENC::x",
        institution_id="ins",
        institution_name="Bank",
        environment="sandbox",
        status=status,
    )
    db_session.add(conn)
    db_session.flush()
    return conn


def _mk_broker_account(db_session, user_id: int, *, acct_num: str) -> BrokerAccount:
    acct = BrokerAccount(
        user_id=user_id,
        broker=BrokerType.UNKNOWN_BROKER,
        account_number=acct_num,
        account_name="Plaid 401k",
        account_type=AccountType.IRA,
        auto_discovered=True,
        status=AccountStatus.ACTIVE,
        is_primary=False,
        is_enabled=True,
        connection_source="plaid",
    )
    db_session.add(acct)
    db_session.flush()
    return acct


class _FakeService:
    """Pluggable fake that emits per-call outcomes for the sync loop."""

    def __init__(self, outcomes_by_item: Dict[str, str]) -> None:
        self._outcomes = outcomes_by_item

    def sync_account_comprehensive(self, account_number, session, *, user_id=None):
        # Outcome keyed by account_number for convenience.
        outcome = self._outcomes.get(account_number, "success")
        if outcome == "raise":
            raise RuntimeError("boom")
        if outcome == "assertion":
            raise AssertionError("counter drift in persist_holdings")
        return {"status": outcome, "pipeline": {"written": 1}}


def test_sync_one_connection_returns_skipped_when_needs_reauth(db_session):
    user = _mk_user(db_session, "reauth")
    conn = _mk_conn(
        db_session,
        user.id,
        item_id="item-reauth",
        status=PlaidConnectionStatus.NEEDS_REAUTH.value,
    )
    outcome = plaid_sync_mod._sync_one_connection(
        db_session, conn, _FakeService({})
    )
    assert outcome == "skipped_no_holdings"


def test_sync_one_connection_skipped_when_no_enabled_accounts(db_session):
    user = _mk_user(db_session, "noacct")
    conn = _mk_conn(
        db_session,
        user.id,
        item_id="item-no",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    outcome = plaid_sync_mod._sync_one_connection(
        db_session, conn, _FakeService({})
    )
    assert outcome == "skipped_no_holdings"


def test_sync_one_connection_written_on_success(db_session):
    user = _mk_user(db_session, "ok")
    conn = _mk_conn(
        db_session,
        user.id,
        item_id="item-ok",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    _mk_broker_account(db_session, user.id, acct_num="ok-1")
    outcome = plaid_sync_mod._sync_one_connection(
        db_session, conn, _FakeService({"ok-1": "success"})
    )
    assert outcome == "written"


def test_sync_one_connection_errors_bucket_when_service_raises(db_session):
    user = _mk_user(db_session, "raise")
    conn = _mk_conn(
        db_session,
        user.id,
        item_id="item-raise",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    _mk_broker_account(db_session, user.id, acct_num="boom-1")
    outcome = plaid_sync_mod._sync_one_connection(
        db_session, conn, _FakeService({"boom-1": "raise"})
    )
    assert outcome == "errors"


def test_sync_one_connection_propagates_counter_drift(db_session):
    user = _mk_user(db_session, "drift")
    conn = _mk_conn(
        db_session,
        user.id,
        item_id="item-drift",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    _mk_broker_account(db_session, user.id, acct_num="drift-1")
    with pytest.raises(AssertionError):
        plaid_sync_mod._sync_one_connection(
            db_session, conn, _FakeService({"drift-1": "assertion"})
        )


def test_daily_sync_counters_sum_to_total(db_session, monkeypatch):
    """End-to-end: one success + one no-account + one error = 3 total."""
    u1 = _mk_user(db_session, "d1")
    u2 = _mk_user(db_session, "d2")
    u3 = _mk_user(db_session, "d3")
    # 1) success
    _mk_conn(
        db_session,
        u1.id,
        item_id="item-d1",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    _mk_broker_account(db_session, u1.id, acct_num="acct-d1")
    # 2) no broker accounts -> skipped_no_holdings
    _mk_conn(
        db_session,
        u2.id,
        item_id="item-d2",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    # 3) service raises -> errors bucket
    _mk_conn(
        db_session,
        u3.id,
        item_id="item-d3",
        status=PlaidConnectionStatus.ACTIVE.value,
    )
    _mk_broker_account(db_session, u3.id, acct_num="acct-d3")
    db_session.commit()

    fake = _FakeService({"acct-d1": "success", "acct-d3": "raise"})

    class _FakeSessionCtx:
        def __init__(self, session):
            self._session = session

        def __enter__(self):
            return self._session

        def __exit__(self, *a):
            return None

    def _session_local():
        # The task calls SessionLocal() then close() — our db_session
        # lives for the whole test so we yield it and make close a no-op.
        class _S:
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def close(self):
                return None

        return _S(db_session)

    monkeypatch.setattr(plaid_sync_mod, "SessionLocal", _session_local)
    monkeypatch.setattr(plaid_sync_mod, "PlaidSyncService", lambda: fake)

    # Bypass the Celery + @task_run decorator machinery by invoking the
    # underlying Python function via its ``run`` method if it's a Celery
    # Task, or call directly otherwise.
    fn = plaid_sync_mod.daily_sync
    if hasattr(fn, "run"):
        counters = fn.run()
    else:
        counters = fn()

    assert isinstance(counters, dict), counters
    assert counters["total"] == 3
    assert (
        counters["written"]
        + counters["skipped_no_holdings"]
        + counters["errors"]
        == counters["total"]
    )
    # Expected breakdown from fixtures above.
    assert counters["written"] == 1
    assert counters["skipped_no_holdings"] == 1
    assert counters["errors"] == 1
