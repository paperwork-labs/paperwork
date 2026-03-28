from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db():
    """Mock DB session scoped to each test — avoids global leak."""

    async def mock_db():
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=AsyncMock(fetchall=lambda: [], scalars=lambda: AsyncMock(all=lambda: []))
        )
        db.flush = AsyncMock()
        db.add = lambda x: None
        yield db

    app.dependency_overrides[get_db] = mock_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_process_returns_response():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/brain/process",
            json={
                "organization_id": "paperwork-labs",
                "message": "what should I work on today?",
                "user_id": "test-user",
                "channel": "test",
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "response" in data["data"]
    assert data["data"]["persona"] == "ea"


@pytest.mark.asyncio
async def test_process_requires_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/brain/process",
            json={"organization_id": "paperwork-labs"},
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_process_with_brain_secret():
    from app.config import settings

    original = settings.BRAIN_API_SECRET
    settings.BRAIN_API_SECRET = "test-secret"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res_no_auth = await client.post(
                "/api/v1/brain/process",
                json={"organization_id": "paperwork-labs", "message": "hello"},
            )
            assert res_no_auth.status_code == 401

            res_with_auth = await client.post(
                "/api/v1/brain/process",
                json={"organization_id": "paperwork-labs", "message": "hello"},
                headers={"X-Brain-Secret": "test-secret"},
            )
            assert res_with_auth.status_code == 200
    finally:
        settings.BRAIN_API_SECRET = original
