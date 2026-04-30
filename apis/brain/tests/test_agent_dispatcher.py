"""Tests for agent dispatch helpers (preflight stamping)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.agent_dispatcher import stamp_preflight


def test_stamp_preflight_recent_call_marks_true() -> None:
    record = {"id": "d1"}
    calls = [{"timestamp": datetime.now(UTC) - timedelta(minutes=2)}]
    assert stamp_preflight(record, calls)["preflight_consulted"] is True


def test_stamp_preflight_old_call_marks_false() -> None:
    record = {"id": "d1"}
    calls = [{"timestamp": datetime.now(UTC) - timedelta(minutes=10)}]
    assert stamp_preflight(record, calls)["preflight_consulted"] is False


def test_stamp_preflight_no_calls_marks_false() -> None:
    record = {"id": "d1"}
    assert stamp_preflight(record, [])["preflight_consulted"] is False
