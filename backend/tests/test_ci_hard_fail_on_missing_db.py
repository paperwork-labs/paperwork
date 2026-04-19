"""
Lock in the CI hard-fail behavior added after PR #321 uncovered that
broken migrations were silently skipping ~500 tests under green CI.

We can't actually flip CI=true within a test (it would break our own
session), so we test the helper and the guard logic directly.
"""
from __future__ import annotations

import pytest

from backend.tests import conftest as ct


_CI_ENV_VARS = ("CI", "GITHUB_ACTIONS", "GITHUB_RUN_ID")


def _clear_all_ci_env(monkeypatch):
    for name in _CI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_in_ci_helper_recognizes_truthy_values(monkeypatch):
    truthy = ("1", "true", "TRUE", "yes", "True", "on")
    for val in truthy:
        _clear_all_ci_env(monkeypatch)
        monkeypatch.setenv("CI", val)
        assert ct._in_ci() is True, f"_in_ci() must be True for CI={val!r}"


def test_in_ci_helper_recognizes_falsy_or_missing(monkeypatch):
    _clear_all_ci_env(monkeypatch)
    assert (
        ct._in_ci() is False
    ), "_in_ci() must be False when no CI env vars are set"

    for val in ("", "0", "false", "no", "anything-else"):
        _clear_all_ci_env(monkeypatch)
        monkeypatch.setenv("CI", val)
        assert ct._in_ci() is False, f"_in_ci() must be False for CI={val!r}"


def test_in_ci_helper_reads_github_actions_env(monkeypatch):
    """GITHUB_ACTIONS=true is a fallback signal for GitHub-hosted runners
    when CI didn't propagate (the exact failure mode behind PR #321)."""
    _clear_all_ci_env(monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert ct._in_ci() is True


def test_in_ci_helper_reads_github_run_id_env(monkeypatch):
    """GITHUB_RUN_ID is always populated on Actions; any non-empty value
    means we're in CI (it's a numeric run id, never a boolean toggle)."""
    _clear_all_ci_env(monkeypatch)
    monkeypatch.setenv("GITHUB_RUN_ID", "12345678901")
    assert ct._in_ci() is True


def test_in_ci_helper_falsy_ci_does_not_override_github_actions(monkeypatch):
    """``GITHUB_ACTIONS`` being set means we're in CI even when ``CI=false``,
    because detection ORs independent signals; ``CI=false`` only disables the
    ``CI`` toggle, not GitHub runner signals like ``GITHUB_ACTIONS``.
    """
    _clear_all_ci_env(monkeypatch)
    monkeypatch.setenv("CI", "false")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    # GITHUB_ACTIONS=true still wins (we OR signals). Document the trade-off.
    assert ct._in_ci() is True


def test_schema_guard_raises_in_ci_when_tables_missing(monkeypatch):
    """The guard must raise (not skip) in CI when required tables are
    missing. This is the behavior that would have caught the PR #321
    silent-skip cascade."""
    monkeypatch.setenv("CI", "true")

    class _FakeInspector:
        def has_table(self, name):
            return False  # everything missing

    class _FakeBind:
        pass

    class _FakeSession:
        bind = _FakeBind()

    # Patch the inspect() call inside the guard to return our fake.
    monkeypatch.setattr(ct, "inspect", lambda _bind: _FakeInspector())

    with pytest.raises(pytest.UsageError) as exc_info:
        ct._enforce_schema_or_fail(_FakeSession())

    msg = str(exc_info.value)
    assert "CI" in msg
    assert "users" in msg or "broker_accounts" in msg
    assert "silently skip" in msg.lower()


def test_schema_guard_skips_outside_ci_when_tables_missing(monkeypatch):
    """Outside CI we keep the soft-skip behavior so local dev still works."""
    _clear_all_ci_env(monkeypatch)

    class _FakeInspector:
        def has_table(self, name):
            return False

    class _FakeBind:
        pass

    class _FakeSession:
        bind = _FakeBind()

    monkeypatch.setattr(ct, "inspect", lambda _bind: _FakeInspector())

    with pytest.raises(pytest.skip.Exception):
        ct._enforce_schema_or_fail(_FakeSession())
