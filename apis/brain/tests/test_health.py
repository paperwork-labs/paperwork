from httpx import AsyncClient


async def test_health_check_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "status" in data["data"]
    assert "version" in data["data"]
    assert data["data"]["service"] == "brain"


async def test_api_v1_health_matches_root_health(client: AsyncClient) -> None:
    a = await client.get("/health")
    b = await client.get("/api/v1/health")
    assert b.status_code == 200
    assert b.json() == a.json()


async def test_health_check_includes_version(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert data["data"]["version"] == "0.1.0"


async def test_health_check_has_correlation_id(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "x-correlation-id" in response.headers
