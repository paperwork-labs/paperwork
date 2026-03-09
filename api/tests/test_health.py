from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "status" in data["data"]
    assert "version" in data["data"]
    assert "db_connected" in data["data"]


def test_health_check_includes_version() -> None:
    response = client.get("/health")
    data = response.json()
    assert data["data"]["version"] == "0.1.0"


def test_health_check_has_correlation_id() -> None:
    response = client.get("/health")
    assert "x-correlation-id" in response.headers
