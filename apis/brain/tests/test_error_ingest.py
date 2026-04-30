from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app as fastapi_app


@pytest.fixture(autouse=True)
def _isolated_error_store(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAIN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BRAIN_ERROR_INGEST_JSONL", str(tmp_path / "error_ingest.jsonl"))
    monkeypatch.setenv("BRAIN_ERROR_AGGREGATES_JSON", str(tmp_path / "error_aggregates.json"))
    monkeypatch.setattr(settings, "BRAIN_API_INTERNAL_TOKEN", "test-error-token")


def _payload(message: str = "TypeError: failed to load") -> dict[str, object]:
    return {
        "product": "studio",
        "env": "preview",
        "message": message,
        "stack": "TypeError: failed to load\n    at loadPage (/app/page.tsx:10:5)\n    at main",
        "url": "https://studio.paperworklabs.com/admin",
        "user_agent": "pytest",
        "severity": "error",
        "context": {"route": "/admin"},
    }


@pytest.mark.asyncio
async def test_ingest_and_recent_roundtrip() -> None:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        posted = await client.post(
            "/v1/errors/ingest",
            headers={"Authorization": "Bearer test-error-token"},
            json=_payload(),
        )
        assert posted.status_code == 200
        fingerprint = posted.json()["fingerprint"]

        recent = await client.get(
            "/v1/errors/recent?product=studio",
            headers={"Authorization": "Bearer test-error-token"},
        )

    assert recent.status_code == 200
    body = recent.json()
    assert body["count"] == 1
    assert body["errors"][0]["fingerprint"] == fingerprint
    assert body["errors"][0]["message"] == "TypeError: failed to load"


@pytest.mark.asyncio
async def test_fingerprint_deduplicates_into_aggregates() -> None:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post(
            "/v1/errors/ingest",
            headers={"Authorization": "Bearer test-error-token"},
            json=_payload(),
        )
        second = await client.post(
            "/v1/errors/ingest",
            headers={"Authorization": "Bearer test-error-token"},
            json=_payload(),
        )
        aggregates = await client.get(
            "/v1/errors/aggregates",
            headers={"Authorization": "Bearer test-error-token"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["fingerprint"] == second.json()["fingerprint"]
    assert aggregates.status_code == 200
    rows = aggregates.json()["aggregates"]
    assert rows[0]["fingerprint"] == first.json()["fingerprint"]
    assert rows[0]["count"] == 2
    assert rows[0]["products_affected"] == ["studio"]


@pytest.mark.asyncio
async def test_missing_token_returns_401() -> None:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/errors/ingest", json=_payload())

    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]


@pytest.mark.asyncio
async def test_unconfigured_token_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_API_INTERNAL_TOKEN", "")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/errors/recent",
            headers={"Authorization": "Bearer anything"},
        )

    assert response.status_code == 401
    assert "BRAIN_API_INTERNAL_TOKEN" in response.json()["detail"]
