"""Regression: portfolio_sync dimension must not mix naive/aware datetimes."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services.silver.market.admin_health_service import AdminHealthService


def _make_account_mock(*, last_successful_sync, account_number: str) -> MagicMock:
    """Build an account mock exposing every attribute ``_build_portfolio_sync_dimension`` reads.

    The service reads ``last_successful_sync``, ``account_number``, and
    ``sync_error_message`` (scanned for ``ACCOUNT_TYPE_WARNING ``). Explicitly
    set ``sync_error_message=None`` so the warning scan short-circuits and
    doesn't depend on MagicMock auto-attribute quirks.
    """
    a = MagicMock()
    a.last_successful_sync = last_successful_sync
    a.account_number = account_number
    a.sync_error_message = None
    a.is_enabled = True
    return a


def test_portfolio_sync_naive_last_successful_sync_does_not_error():
    """Naive ``last_successful_sync`` vs aware cutoff must not raise or return error dim."""
    naive_recent = datetime.utcnow() - timedelta(hours=1)
    assert naive_recent.tzinfo is None

    account = _make_account_mock(
        last_successful_sync=naive_recent,
        account_number="U999001",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [account]

    svc = AdminHealthService()
    result = svc._build_portfolio_sync_dimension(db)

    assert result.get("status") != "error", result
    assert result.get("stale_accounts") == 0
    assert result.get("status") == "green"


def test_portfolio_sync_aware_last_successful_sync_still_compares():
    aware_recent = datetime.now(timezone.utc) - timedelta(hours=1)
    account = _make_account_mock(
        last_successful_sync=aware_recent,
        account_number="U999002",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [account]

    svc = AdminHealthService()
    result = svc._build_portfolio_sync_dimension(db)

    assert result.get("status") == "green"
    assert result.get("stale_accounts") == 0
