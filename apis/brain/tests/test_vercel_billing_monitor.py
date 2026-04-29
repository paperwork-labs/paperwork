"""Tests for Vercel on-demand budget alerting (vercel_billing_monitor)."""

from __future__ import annotations

from app.services.vercel_billing_monitor import evaluate_alerts


def test_no_alerts_when_under_50_pct() -> None:
    fired: dict[str, list[float]] = {}
    alerts = evaluate_alerts(spent_usd=10.0, budget_usd=40.0, fired=fired, period_key="2026-04")
    assert alerts == []
    assert fired == {}


def test_50_pct_threshold_fires_once() -> None:
    fired: dict[str, list[float]] = {}
    alerts = evaluate_alerts(spent_usd=20.0, budget_usd=40.0, fired=fired, period_key="2026-04")
    assert len(alerts) == 1
    assert alerts[0]["threshold"] == 0.5
    assert alerts[0]["severity"] == "info"
    # Calling again same period: no re-fire
    alerts = evaluate_alerts(spent_usd=22.0, budget_usd=40.0, fired=fired, period_key="2026-04")
    assert alerts == []


def test_jump_to_91_pct_fires_50_75_90_in_one_poll() -> None:
    fired: dict[str, list[float]] = {}
    alerts = evaluate_alerts(spent_usd=36.58, budget_usd=40.0, fired=fired, period_key="2026-04")
    thresholds = sorted(a["threshold"] for a in alerts)
    assert thresholds == [0.5, 0.75, 0.9]
    severities = {a["threshold"]: a["severity"] for a in alerts}
    assert severities == {0.5: "info", 0.75: "warning", 0.9: "critical"}


def test_overage_at_100_pct_fires_critical() -> None:
    fired: dict[str, list[float]] = {"2026-04": [0.5, 0.75, 0.9]}
    alerts = evaluate_alerts(spent_usd=42.0, budget_usd=40.0, fired=fired, period_key="2026-04")
    assert len(alerts) == 1
    assert alerts[0]["threshold"] == 1.0
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["pct"] == 105.0


def test_new_period_resets_dedup() -> None:
    fired: dict[str, list[float]] = {"2026-04": [0.5, 0.75, 0.9, 1.0]}
    alerts = evaluate_alerts(spent_usd=20.0, budget_usd=40.0, fired=fired, period_key="2026-05")
    assert len(alerts) == 1
    assert alerts[0]["threshold"] == 0.5


def test_zero_budget_does_not_divide() -> None:
    fired: dict[str, list[float]] = {}
    alerts = evaluate_alerts(spent_usd=10.0, budget_usd=0.0, fired=fired, period_key="2026-04")
    assert alerts == []
