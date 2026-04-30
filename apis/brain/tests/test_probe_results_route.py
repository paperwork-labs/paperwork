"""Smoke tests for /v1/probes/results and /v1/probes/health endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from app.api import probe_results as probe_results_module
from app.database import get_db
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _override_db():
    async def mock_db():
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=AsyncMock(fetchall=list, scalars=lambda: AsyncMock(all=list))
        )
        db.flush = AsyncMock()
        db.add = lambda _: None
        yield db

    app.dependency_overrides[get_db] = mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


def _sample_results() -> list[dict]:
    return [
        {
            "product": "filefree",
            "base_url": "https://filefree.ai",
            "status": "pass",
            "exit_code": 0,
            "started_at": "2026-04-30T10:00:00Z",
            "finished_at": "2026-04-30T10:00:45Z",
        },
        {
            "product": "axiomfolio",
            "base_url": "https://axiomfolio.com",
            "status": "failure",
            "exit_code": 1,
            "started_at": "2026-04-30T10:01:00Z",
            "finished_at": "2026-04-30T10:01:50Z",
            "failing_tests": [{"title": "sign-in test", "status": "failed", "error": "timeout"}],
        },
        {
            "product": "launchfree",
            "base_url": "https://launchfree.ai",
            "status": "pass",
            "exit_code": 0,
            "started_at": "2026-04-30T10:02:00Z",
            "finished_at": "2026-04-30T10:02:30Z",
        },
    ]


# ---------------------------------------------------------------------------
# GET /v1/probes/results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_results_returns_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without filters, /v1/probes/results returns all rows."""
    monkeypatch.setattr(probe_results_module, "_load_results", lambda: _sample_results())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/results")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["count"] == 3
    assert len(data["data"]["results"]) == 3


@pytest.mark.asyncio
async def test_probe_results_filter_by_product(monkeypatch: pytest.MonkeyPatch) -> None:
    """?product=filefree filters to one result."""
    monkeypatch.setattr(probe_results_module, "_load_results", lambda: _sample_results())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/results?product=filefree")

    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["count"] == 1
    assert data["data"]["results"][0]["product"] == "filefree"
    assert data["data"]["product_filter"] == "filefree"


@pytest.mark.asyncio
async def test_probe_results_since_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """?since= filters out older entries."""
    monkeypatch.setattr(probe_results_module, "_load_results", lambda: _sample_results())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # since after filefree (10:00) but before launchfree (10:02)
        resp = await client.get("/v1/probes/results?since=2026-04-30T10:00:30Z")

    assert resp.status_code == 200
    data = resp.json()
    products = [r["product"] for r in data["data"]["results"]]
    assert "filefree" not in products
    assert "axiomfolio" in products
    assert "launchfree" in products


@pytest.mark.asyncio
async def test_probe_results_invalid_since(monkeypatch: pytest.MonkeyPatch) -> None:
    """?since=garbage returns 400, not a crash."""
    monkeypatch.setattr(probe_results_module, "_load_results", lambda: _sample_results())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/results?since=not-a-date")

    assert resp.status_code == 400
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_probe_results_file_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unreadable probe_results.json returns 503, not an empty list."""

    def _raise():
        raise OSError("disk error")

    monkeypatch.setattr(probe_results_module, "_load_results", _raise)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/results")

    assert resp.status_code == 503
    body = resp.json()
    assert body["success"] is False
    # Must not look like an empty result set
    assert "detail" in body


# ---------------------------------------------------------------------------
# GET /v1/probes/health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probe_health_returns_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """/v1/probes/health returns per-product latest status."""
    monkeypatch.setattr(probe_results_module, "_load_results", lambda: _sample_results())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/health")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "health" in data
    assert "overall" in data
    assert data["health"]["filefree"]["status"] == "pass"
    assert data["health"]["axiomfolio"]["status"] == "failure"


@pytest.mark.asyncio
async def test_probe_health_overall_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """overall=pass only when every product is passing."""
    all_pass = [
        {
            "product": p,
            "status": "pass",
            "exit_code": 0,
            "started_at": "2026-04-30T10:00:00Z",
            "finished_at": "2026-04-30T10:00:45Z",
            "base_url": f"https://{p}.ai",
        }
        for p in ["filefree", "axiomfolio", "launchfree"]
    ]
    monkeypatch.setattr(probe_results_module, "_load_results", lambda: all_pass)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/health")

    assert resp.status_code == 200
    assert resp.json()["data"]["overall"] == "pass"


@pytest.mark.asyncio
async def test_probe_health_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty results → 200 with explanatory note, not silent empty dict."""
    monkeypatch.setattr(probe_results_module, "_load_results", list)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/health")

    assert resp.status_code == 200
    data = resp.json()["data"]
    # Must include a note explaining the empty state
    assert "note" in data
    assert "ux_probe_runner" in data["note"]


@pytest.mark.asyncio
async def test_probe_health_file_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unreadable results file → 503, not empty health dict."""

    def _raise():
        raise OSError("permission denied")

    monkeypatch.setattr(probe_results_module, "_load_results", _raise)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/probes/health")

    assert resp.status_code == 503
    assert resp.json()["success"] is False
