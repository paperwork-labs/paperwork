"""WS-82 Phase D — Studio-facing admin enrichment endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/memory-stats",
        "/api/v1/admin/persona-dispatch-summary",
        "/api/v1/admin/operating-score/history",
        "/api/v1/admin/cost-breakdown",
        "/api/v1/admin/brain-fill-meter",
    ],
)
@pytest.mark.asyncio
async def test_ws82_admin_endpoints_require_secret(client: AsyncClient, path: str) -> None:
    res = await client.get(path)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_memory_stats_success_shape(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    res = await client.get(
        "/api/v1/admin/memory-stats",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data["total_episodes"], int)
    assert isinstance(data["episodes_by_source"], list)
    assert "trailing_30_days" in data
    assert "average_per_day" in data["trailing_30_days"]
    assert isinstance(data["storage_estimate_bytes"], int)


@pytest.mark.asyncio
async def test_persona_dispatch_summary_shape(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    log = tmp_path / "agent_dispatch_log.json"
    log.write_text(
        json.dumps(
            {
                "dispatches": [
                    {
                        "dispatched_at": "2026-04-29T12:00:00Z",
                        "persona_slug": "ea",
                        "outcome": {"merged_at": "2026-04-29T14:00:00Z", "reverted": False},
                    },
                    {
                        "dispatched_at": "2026-04-28T12:00:00Z",
                        "persona_slug": "ea",
                        "outcome": {"reverted": True, "merged_at": "2026-04-28T13:00:00Z"},
                    },
                    {"dispatched_at": "2026-04-27T12:00:00Z", "persona_slug": "qa"},
                ],
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_AGENT_DISPATCH_LOG_JSON", str(log))

    res = await client.get(
        "/api/v1/admin/persona-dispatch-summary",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    payload = res.json()["data"]
    assert payload["dispatch_total"] == 3
    personas = {p["persona_slug"]: p for p in payload["personas"]}
    assert personas["ea"]["dispatch_count"] == 2
    assert personas["ea"]["success_count"] == 1
    assert personas["ea"]["failure_count"] == 1
    assert personas["qa"]["pending_outcome_count"] == 1
    assert len(payload["recent_activity"]) <= 15


@pytest.mark.asyncio
async def test_operating_score_history_series_length(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    res = await client.get(
        "/api/v1/admin/operating-score/history?days=7",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["days"] == 7
    assert len(data["series"]) == 7
    assert all("date" in p and "total" in p for p in data["series"])


@pytest.mark.asyncio
async def test_cost_breakdown_success_shape(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    res = await client.get(
        "/api/v1/admin/cost-breakdown?days=14",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["window_days"] == 14
    assert data["estimated"] is True
    assert "by_persona" in data and "by_model" in data and "by_day" in data
    assert "tokens_in" in data["totals"]


@pytest.mark.asyncio
async def test_brain_fill_meter_success_shape(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    res = await client.get(
        "/api/v1/admin/brain-fill-meter",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert "overall_utilization_pct" in data
    assert set(data["tiers"].keys()) == {"episodic", "procedural", "semantic"}
