"""Tests for cost ledger service, budget alerts, audit runner, and HTTP API.

medallion: ops
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app


def _ledger_doc() -> dict:
    return {
        "entries": [
            {
                "date": "2026-04-15",
                "vendor": "render",
                "category": "hosting",
                "amount_usd": 25.0,
                "details": "api",
            },
            {
                "date": "2026-04-20",
                "vendor": "render",
                "category": "hosting",
                "amount_usd": 20.0,
                "details": "worker",
            },
            {
                "date": "2026-04-10",
                "vendor": "anthropic",
                "category": "llm",
                "amount_usd": 10.0,
                "details": "claude",
            },
        ],
        "monthly_budgets": {
            "anthropic": None,
            "openai": None,
            "google": None,
            "render": 50,
            "vercel": 20,
            "hetzner": 7,
        },
    }


def test_get_monthly_summary_aggregates_by_vendor(tmp_path: Path) -> None:
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps(_ledger_doc()), encoding="utf-8")
    with patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path):
        from app.services import cost_monitor

        s = cost_monitor.get_monthly_summary("2026-04")
    assert s.total_usd == pytest.approx(55.0)
    by_v = {v.vendor: v.amount_usd for v in s.vendors}
    assert by_v["render"] == pytest.approx(45.0)
    assert by_v["anthropic"] == pytest.approx(10.0)


def test_check_budget_alerts_approaching(tmp_path: Path) -> None:
    doc = _ledger_doc()
    doc["entries"] = [
        {
            "date": "2026-04-01",
            "vendor": "render",
            "category": "hosting",
            "amount_usd": 42.0,
            "details": "",
        }
    ]
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path):
        from app.services import cost_monitor

        alerts = cost_monitor.check_budget_alerts(month="2026-04")
    assert len(alerts) == 1
    assert alerts[0].budget_key == "render"
    assert alerts[0].status == "approaching"
    assert alerts[0].utilization == pytest.approx(42.0 / 50.0)


def test_check_budget_alerts_exceeded(tmp_path: Path) -> None:
    doc = _ledger_doc()
    doc["entries"] = [
        {
            "date": "2026-04-01",
            "vendor": "render",
            "category": "hosting",
            "amount_usd": 55.0,
            "details": "",
        }
    ]
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path):
        from app.services import cost_monitor

        alerts = cost_monitor.check_budget_alerts(month="2026-04")
    assert len(alerts) == 1
    assert alerts[0].status == "exceeded"


def test_empty_ledger(tmp_path: Path) -> None:
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps({"entries": [], "monthly_budgets": {}}), encoding="utf-8")
    with patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path):
        from app.services import cost_monitor

        s = cost_monitor.get_monthly_summary("2026-04")
        burn = cost_monitor.get_daily_burn_rate()
        alerts = cost_monitor.check_budget_alerts(month="2026-04")
    assert s.vendors == []
    assert s.total_usd == 0.0
    assert burn.total_usd == 0.0
    assert alerts == []


def test_get_daily_burn_rate_respects_window(tmp_path: Path) -> None:
    end = datetime.now(tz=UTC).date()
    recent = (end - timedelta(days=1)).isoformat()
    stale = (end - timedelta(days=120)).isoformat()
    doc = {
        "entries": [
            {
                "date": recent,
                "vendor": "vercel",
                "category": "hosting",
                "amount_usd": 12.0,
                "details": "",
            },
            {
                "date": stale,
                "vendor": "vercel",
                "category": "hosting",
                "amount_usd": 999.0,
                "details": "",
            },
        ],
        "monthly_budgets": {},
    }
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path):
        from app.services import cost_monitor

        burn = cost_monitor.get_daily_burn_rate(window_days=30)
    assert burn.total_usd == pytest.approx(12.0)
    assert burn.daily_average_usd == pytest.approx(12.0 / 30.0)


def test_cost_monitor_audit_warns_on_budget(tmp_path: Path) -> None:
    doc = _ledger_doc()
    doc["entries"] = [
        {
            "date": "2026-04-10",
            "vendor": "vercel",
            "category": "hosting",
            "amount_usd": 17.0,
            "details": "",
        }
    ]
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    fixed = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    with (
        patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path),
        patch("app.audits.cost_monitor.datetime") as mock_dt,
    ):
        mock_dt.UTC = UTC
        mock_dt.now = lambda **__: fixed
        from app.audits import cost_monitor as cost_audit

        run = cost_audit.run()
    assert run.audit_id == "cost_monitor"
    warns = [f for f in run.findings if f.severity == "warn"]
    assert len(warns) >= 1


@pytest.mark.asyncio
async def test_cost_api_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/costs/summary?month=2026-04")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_cost_api_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    path = tmp_path / "cost_ledger.json"
    path.write_text(json.dumps(_ledger_doc()), encoding="utf-8")
    with patch("app.services.cost_monitor._brain_data_dir", return_value=tmp_path):
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get(
                "/api/v1/costs/summary?month=2026-04",
                headers={"X-Brain-Secret": "test-secret"},
            )
    assert res.status_code == 200
    body = res.json()
    assert body["total_usd"] == pytest.approx(55.0)
    assert len(body["vendors"]) == 2
