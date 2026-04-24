"""Verify the IB Gateway watchdog skips when no enabled IBKR account exists.

Background: with no IBKR account configured, the watchdog was attempting
``_ensure_connected`` against ``127.0.0.1:7497`` every 5 minutes and
generating ``SoftTimeLimitExceeded`` tracebacks in production logs. The
fix: short-circuit when no enabled BrokerAccount of broker=IBKR exists.
"""
from __future__ import annotations

from unittest.mock import patch

from app.tasks.ops import ibkr_watchdog


def test_skips_when_account_lookup_returns_none():
    with patch.object(
        ibkr_watchdog, "_has_enabled_ibkr_account", return_value=False
    ):
        result = ibkr_watchdog._perform_ping()
    assert result == {"status": "skipped", "reason": "no_enabled_ibkr_account"}


def test_proceeds_when_account_present_but_handles_disconnect():
    """When the gate passes but the gateway is unreachable, the watchdog
    must still return a structured status rather than raise — otherwise
    Celery surfaces a stack trace every 5 minutes."""

    class _FakeIbkr:
        async def _ensure_connected(self):
            return False

        async def disconnect(self):
            return None

    with patch.object(
        ibkr_watchdog, "_has_enabled_ibkr_account", return_value=True
    ), patch(
        "app.services.clients.ibkr_client.ibkr_client", _FakeIbkr()
    ), patch(
        "app.services.notifications.order_notifications.send_risk_alert",
        return_value=None,
    ):
        result = ibkr_watchdog._perform_ping()

    assert result["status"] in {"disconnected", "error"}


def test_account_lookup_swallows_db_failure_and_returns_false():
    """If the DB itself is unreachable, the lookup must return False so the
    watchdog skips rather than blowing up. We never want a watchdog that
    raises every minute when the DB is recovering."""
    with patch(
        "app.database.SessionLocal", side_effect=RuntimeError("db down")
    ):
        assert ibkr_watchdog._has_enabled_ibkr_account() is False
