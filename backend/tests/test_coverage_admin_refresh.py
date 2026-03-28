import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_admin_user
from backend.models.user import UserRole


@pytest.fixture(autouse=True)
def allow_admin_user():
    class _DummyUser:
        role = UserRole.OWNER
        is_active = True
        email = "admin@example.com"

    app.dependency_overrides[get_admin_user] = lambda: _DummyUser()
    yield
    app.dependency_overrides.pop(get_admin_user, None)


def test_admin_refresh_coverage_enqueues_task(monkeypatch):
    from backend.api.routes.market import admin as routes

    class _StubTask:
        @staticmethod
        def delay(*_args, **_kwargs):
            return SimpleNamespace(id="task-123")

    monkeypatch.setattr(routes, "health_check", _StubTask)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/market-data/admin/backfill/coverage/refresh")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("task_id") == "task-123"


def test_admin_restore_daily_tracked_enqueues_task(monkeypatch):
    from backend.api.routes.market import admin as routes

    class _StubTask:
        @staticmethod
        def delay(*_args, **_kwargs):
            return SimpleNamespace(id="task-restore-123")

    monkeypatch.setattr(routes, "daily_bootstrap", _StubTask)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/market-data/admin/backfill/coverage")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("task_id") == "task-restore-123"


