from fastapi.testclient import TestClient

from app.api.main import app
from app.api.dependencies import get_admin_user

client = TestClient(app, raise_server_exceptions=False)


def test_admin_tasks_requires_admin():
    resp = client.get("/api/v1/market-data/admin/tasks")
    assert resp.status_code in (401, 403)


def test_admin_tasks_payload_shape():
    app.dependency_overrides[get_admin_user] = object
    try:
        resp = client.get("/api/v1/market-data/admin/tasks")
        assert resp.status_code == 200
        data = resp.json()
        tasks = data.get("tasks", [])
        assert isinstance(tasks, list)
        assert tasks, "expected at least one task action"
        for action in tasks:
            assert isinstance(action, dict)
            assert isinstance(action.get("task_name"), str)
            assert isinstance(action.get("method"), str)
            assert isinstance(action.get("endpoint"), str)
            params_schema = action.get("params_schema")
            if params_schema is not None:
                assert isinstance(params_schema, list)
                for param in params_schema:
                    assert isinstance(param, dict)
                    assert isinstance(param.get("name"), str)
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


def test_admin_record_history_requires_admin():
    resp = client.post("/api/v1/market-data/admin/snapshots/history/record")
    assert resp.status_code in (401, 403)


def test_admin_coverage_backfill_preview_requires_admin():
    resp = client.get("/api/v1/market-data/admin/backfill/coverage/preview")
    assert resp.status_code in (401, 403)


def test_admin_coverage_backfill_preview_payload():
    app.dependency_overrides[get_admin_user] = object
    try:
        resp = client.get("/api/v1/market-data/admin/backfill/coverage/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert "resolved_history_days" in data
        assert int(data["resolved_history_days"]) >= 5
        assert "date_range" in data
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
