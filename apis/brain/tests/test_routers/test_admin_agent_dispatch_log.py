"""``GET /api/v1/admin/agent-dispatch-log`` — Studio persona activity stream."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_agent_dispatch_log_requires_secret(client: AsyncClient) -> None:
    res = await client.get("/api/v1/admin/agent-dispatch-log")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_agent_dispatch_log_returns_newest_first(
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
                        "persona_slug": "older",
                    },
                    {
                        "dispatched_at": "2026-04-30T12:00:00Z",
                        "persona_slug": "newer",
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_AGENT_DISPATCH_LOG_JSON", str(log))

    res = await client.get(
        "/api/v1/admin/agent-dispatch-log?limit=10",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    data = body["data"]
    assert data["count"] == 2
    assert data["dispatches"][0]["persona_slug"] == "newer"
    assert data["dispatches"][1]["persona_slug"] == "older"


@pytest.mark.asyncio
async def test_agent_dispatch_log_since_filter(
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
                    {"dispatched_at": "2026-04-01T10:00:00Z"},
                    {"dispatched_at": "2026-04-15T10:00:00Z"},
                ],
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BRAIN_AGENT_DISPATCH_LOG_JSON", str(log))

    res = await client.get(
        "/api/v1/admin/agent-dispatch-log?since=2026-04-10T00:00:00Z",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["count"] == 1
    assert data["dispatches"][0]["dispatched_at"] == "2026-04-15T10:00:00Z"
