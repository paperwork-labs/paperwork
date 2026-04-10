"""Tests for the advisory-lock startup guard in main.py.

Verifies that when multiple workers start simultaneously, only the worker
that acquires pg_try_advisory_lock(42) runs seed_schedules and admin
creation. The other worker skips those side-effects.

The lock logic lives in _sync_deferred_startup() which runs in a
background thread after startup_event() completes.
"""

import pytest
from unittest.mock import MagicMock, patch


pytestmark = pytest.mark.no_db


class _FakeResult:
    """Mimics SQLAlchemy result object from conn.execute()."""

    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


def _build_mock_conn(lock_acquired: bool):
    """Return a mock connection whose pg_try_advisory_lock returns *lock_acquired*."""
    conn = MagicMock()

    def _execute(sql_text):
        sql_str = str(sql_text)
        if "pg_try_advisory_lock" in sql_str:
            return _FakeResult(lock_acquired)
        if "pg_advisory_unlock" in sql_str:
            return _FakeResult(True)
        return _FakeResult(None)

    conn.execute = _execute
    return conn


@patch("backend.api.main.settings")
@patch("backend.api.main.SessionLocal")
@patch("backend.api.main.engine")
def test_lock_acquired_runs_seed(mock_engine, mock_session_local, mock_settings):
    """When advisory lock is acquired, seed_schedules and admin creation run."""
    mock_settings.ADMIN_SEED_ENABLED = False
    mock_settings.SEED_ACCOUNTS_ON_STARTUP = False
    mock_settings.AUTO_WARM_ON_STARTUP = False

    conn = _build_mock_conn(lock_acquired=True)
    mock_engine.connect.return_value = conn

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_seed = MagicMock(return_value="seeded 5 schedules")

    with patch("backend.scripts.seed_schedules.seed", mock_seed):
        from backend.api.main import _sync_deferred_startup

        _sync_deferred_startup()

        mock_seed.assert_called_once_with(mock_db)


@patch("backend.api.main.settings")
@patch("backend.api.main.SessionLocal")
@patch("backend.api.main.engine")
def test_lock_not_acquired_skips_seed(mock_engine, mock_session_local, mock_settings):
    """When advisory lock is NOT acquired, seed is skipped entirely."""
    mock_settings.ADMIN_SEED_ENABLED = False
    mock_settings.SEED_ACCOUNTS_ON_STARTUP = False
    mock_settings.AUTO_WARM_ON_STARTUP = False

    conn = _build_mock_conn(lock_acquired=False)
    mock_engine.connect.return_value = conn

    mock_seed = MagicMock()

    with patch("backend.scripts.seed_schedules.seed", mock_seed):
        from backend.api.main import _sync_deferred_startup

        _sync_deferred_startup()

        mock_seed.assert_not_called()


@patch("backend.api.main.settings")
@patch("backend.api.main.SessionLocal")
@patch("backend.api.main.engine")
def test_lock_released_in_finally(mock_engine, mock_session_local, mock_settings):
    """Advisory lock is released and connection closed even if seed raises."""
    mock_settings.ADMIN_SEED_ENABLED = False
    mock_settings.SEED_ACCOUNTS_ON_STARTUP = False
    mock_settings.AUTO_WARM_ON_STARTUP = False

    unlock_called = []
    close_called = []

    conn = MagicMock()

    def _execute(sql_text):
        sql_str = str(sql_text)
        if "pg_try_advisory_lock" in sql_str:
            return _FakeResult(True)
        if "pg_advisory_unlock" in sql_str:
            unlock_called.append(True)
            return _FakeResult(True)
        return _FakeResult(None)

    conn.execute = _execute
    conn.close = lambda: close_called.append(True)
    mock_engine.connect.return_value = conn

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    with patch("backend.scripts.seed_schedules.seed", side_effect=RuntimeError("seed kaboom")):
        from backend.api.main import _sync_deferred_startup

        _sync_deferred_startup()

    assert len(unlock_called) == 1, "Advisory lock must be released in finally block"
    assert len(close_called) == 1, "Connection must be closed in finally block"


@patch("backend.api.main.settings")
@patch("backend.api.main.SessionLocal")
@patch("backend.api.main.engine")
def test_lock_not_acquired_still_closes_connection(mock_engine, mock_session_local, mock_settings):
    """Even when lock is not acquired, connection is closed."""
    mock_settings.ADMIN_SEED_ENABLED = False
    mock_settings.SEED_ACCOUNTS_ON_STARTUP = False
    mock_settings.AUTO_WARM_ON_STARTUP = False

    close_called = []
    conn = MagicMock()

    def _execute(sql_text):
        sql_str = str(sql_text)
        if "pg_try_advisory_lock" in sql_str:
            return _FakeResult(False)
        return _FakeResult(None)

    conn.execute = _execute
    conn.close = lambda: close_called.append(True)
    mock_engine.connect.return_value = conn

    from backend.api.main import _sync_deferred_startup

    _sync_deferred_startup()

    assert len(close_called) == 1, "Connection must be closed even when lock not acquired"
