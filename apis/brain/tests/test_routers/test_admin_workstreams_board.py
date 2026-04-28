"""``GET /api/v1/admin/workstreams-board`` — Studio live workstreams JSON."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_admin_workstreams_board_requires_secret(client: AsyncClient) -> None:
    res = await client.get("/api/v1/admin/workstreams-board")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_workstreams_board_returns_file_shape(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_SECRET", "test-secret")
    res = await client.get(
        "/api/v1/admin/workstreams-board",
        headers={"X-Brain-Secret": "test-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("version") == 1
    assert "updated" in body
    assert isinstance(body.get("workstreams"), list)
    assert len(body["workstreams"]) >= 1
    assert body.get("generated_at")
    assert body.get("source") == "brain-writeback"
    assert body.get("ttl_seconds") == 60
    assert "writeback_last_run_at" in body
