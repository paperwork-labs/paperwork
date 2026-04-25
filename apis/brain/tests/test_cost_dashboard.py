"""Tests for Track I cost dashboard formatter.

Keeps the Slack-facing output deterministic so CFO sees the same shape
day over day, and catches regressions in percentage / warning logic.

medallion: ops
"""
from __future__ import annotations

from app.schedulers.cost_dashboard import _format_dashboard


def test_format_dashboard_sorts_by_spent_descending():
    rows = [
        ("engineering", 1.50, 10.00),
        ("cpa", 4.00, 5.00),
        ("qa", 0.25, 5.00),
    ]
    out = _format_dashboard(rows, total=5.75)
    cpa_pos = out.index("cpa")
    eng_pos = out.index("engineering")
    qa_pos = out.index("qa")
    assert cpa_pos < eng_pos < qa_pos


def test_format_dashboard_flags_over_80_percent():
    rows = [("cpa", 4.50, 5.00)]  # 90% used
    out = _format_dashboard(rows, total=4.50)
    assert "near ceiling" in out
    assert "cpa" in out


def test_format_dashboard_clears_when_everyone_healthy():
    rows = [("cpa", 0.50, 5.00), ("qa", 0.10, 5.00)]
    out = _format_dashboard(rows, total=0.60)
    assert "comfortably under ceiling" in out
    assert "near ceiling" not in out


def test_format_dashboard_handles_missing_ceiling():
    rows = [("brand", 0.20, None)]
    out = _format_dashboard(rows, total=0.20)
    assert "brand" in out
    assert "—" in out


def test_format_dashboard_includes_total():
    rows = [("cpa", 2.50, 5.00), ("qa", 1.00, 5.00)]
    out = _format_dashboard(rows, total=3.50)
    assert "$3.50" in out
