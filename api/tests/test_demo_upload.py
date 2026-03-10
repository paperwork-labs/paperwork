"""Tests for the demo-upload endpoint."""

import io

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_demo_upload_returns_mock_data():
    """Demo upload should return mock W2 data when no API keys configured."""
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 2000

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents/demo-upload",
            files={"file": ("test-w2.jpg", io.BytesIO(fake_jpeg), "image/jpeg")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "fields" in body["data"]
    assert body["data"]["tier_used"] == "mock"
    assert body["data"]["fields"]["wages"] > 0
    assert body["data"]["fields"]["ssn_last_four"] == "6789"


@pytest.mark.asyncio
async def test_demo_upload_rejects_invalid_type():
    """Should reject non-image files."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents/demo-upload",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "Invalid file type" in body["error"]


@pytest.mark.asyncio
async def test_demo_upload_rejects_tiny_file():
    """Should reject files smaller than 1KB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents/demo-upload",
            files={"file": ("small.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 10), "image/jpeg")},
        )

    body = response.json()
    assert body["success"] is False
    assert "too small" in body["error"]
