"""Admin-only trigger for the OptionTaxLot backfill."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.dependencies import get_admin_user
from app.api.main import app
from app.models.user import User, UserRole

client = TestClient(app, raise_server_exceptions=False)


def test_admin_jobs_backfill_requires_auth() -> None:
    resp = client.post("/api/v1/admin/jobs/backfill-option-tax-lots", json={})
    assert resp.status_code in (401, 403)


def test_admin_jobs_backfill_enqueues_celery_task() -> None:
    fake_admin = User(
        id=999,
        username="admin",
        email="admin@example.test",
        password_hash="x",
        role=UserRole.OWNER,
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    app.dependency_overrides[get_admin_user] = lambda: fake_admin
    mock_task = MagicMock()
    mock_task.id = "celery-task-id-xyz"
    try:
        with patch(
            "app.api.routes.admin.jobs.celery_app.send_task",
            return_value=mock_task,
        ) as send:
            resp = client.post(
                "/api/v1/admin/jobs/backfill-option-tax-lots",
                json={"user_id": 1},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status"] == "enqueued"
            assert body["task_id"] == "celery-task-id-xyz"
            assert body["user_id"] == 1
            send.assert_called_once()
            call = send.call_args
            assert call.args[0] == "app.tasks.portfolio.reconciliation.backfill_option_tax_lots"
            assert call.kwargs["kwargs"] == {"user_id": 1}
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


def test_admin_jobs_backfill_all_users_when_user_id_omitted() -> None:
    fake_admin = User(
        id=999,
        username="admin",
        email="admin@example.test",
        password_hash="x",
        role=UserRole.OWNER,
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    app.dependency_overrides[get_admin_user] = lambda: fake_admin
    mock_task = MagicMock()
    mock_task.id = "celery-task-id-all"
    try:
        with patch(
            "app.api.routes.admin.jobs.celery_app.send_task",
            return_value=mock_task,
        ) as send:
            resp = client.post(
                "/api/v1/admin/jobs/backfill-option-tax-lots",
                json={},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["user_id"] is None
            # Task kwargs should be empty (no user filter)
            assert send.call_args.kwargs["kwargs"] == {}
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
