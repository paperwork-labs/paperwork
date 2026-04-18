"""
Lock in the CI hard-fail behavior added after PR #321 uncovered that
broken migrations were silently skipping ~500 tests under green CI.

We can't actually flip CI=true within a test (it would break our own
session), so we test the helper and the guard logic directly.
"""
from __future__ import annotations

import pytest

from backend.tests import conftest as ct


def test_in_ci_helper_recognizes_truthy_values(monkeypatch):
    truthy = ("1", "true", "TRUE", "yes", "True")
    for val in truthy:
        monkeypatch.setenv("CI", val)
        assert ct._in_ci() is True, f"_in_ci() must be True for CI={val!r}"


def test_in_ci_helper_recognizes_falsy_or_missing(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    assert ct._in_ci() is False, "_in_ci() must be False when CI is unset"

    for val in ("", "0", "false", "no", "anything-else"):
        monkeypatch.setenv("CI", val)
        assert ct._in_ci() is False, f"_in_ci() must be False for CI={val!r}"


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
    monkeypatch.delenv("CI", raising=False)

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
