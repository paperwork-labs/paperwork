from httpx import AsyncClient


async def test_health_check_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "status" in data["data"]
    assert "version" in data["data"]
    assert "db_connected" in data["data"]


async def test_health_check_includes_version(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert data["data"]["version"] == "0.1.0"


async def test_health_check_has_correlation_id(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "x-correlation-id" in response.headers
