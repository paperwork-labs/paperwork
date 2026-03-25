"""Tests for DB-backed schedule CRUD API + Render sync service."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_admin_user
from backend.models.market_data import CronSchedule
from backend.tasks.job_catalog import CATALOG

pytestmark = pytest.mark.no_db

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Seed script
# ---------------------------------------------------------------------------


def test_seed_script_inserts_catalog_entries(db_session):
    if db_session is None:
        pytest.skip("No test DB")
    from backend.scripts.seed_schedules import seed

    result = seed(db_session)
    assert result["seeded"] == len(CATALOG)
    assert result["updated"] == 0
    assert result["skipped_customized"] == 0

    # Running again should be idempotent
    result2 = seed(db_session)
    assert result2["seeded"] == 0
    assert result2["updated"] == 0
    assert result2["unchanged"] == len(CATALOG)


def test_seed_creates_correct_fields(db_session):
    if db_session is None:
        pytest.skip("No test DB")
    from backend.scripts.seed_schedules import seed

    seed(db_session)
    row = db_session.query(CronSchedule).filter(CronSchedule.id == "admin_coverage_backfill").first()
    assert row is not None
    assert row.cron == "0 3 * * *"
    assert row.task == "backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked"
    assert row.group == "market_data"
    assert row.enabled is True
    assert row.created_by == "catalog_seed"


# ---------------------------------------------------------------------------
# CronSchedule model
# ---------------------------------------------------------------------------


def test_cron_schedule_model_crud(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    schedule = CronSchedule(
        id="test_job",
        display_name="Test Job",
        group="test",
        task="backend.tasks.test.run",
        cron="0 * * * *",
        timezone="UTC",
        enabled=True,
        created_by="test",
    )
    db_session.add(schedule)
    db_session.commit()

    row = db_session.query(CronSchedule).filter(CronSchedule.id == "test_job").first()
    assert row is not None
    assert row.display_name == "Test Job"
    assert row.enabled is True

    row.enabled = False
    db_session.commit()
    row = db_session.query(CronSchedule).filter(CronSchedule.id == "test_job").first()
    assert row.enabled is False

    db_session.delete(row)
    db_session.commit()
    assert db_session.query(CronSchedule).filter(CronSchedule.id == "test_job").first() is None


# ---------------------------------------------------------------------------
# Render sync service
# ---------------------------------------------------------------------------


def test_render_sync_disabled_when_no_api_key():
    from backend.services.core.render_sync_service import RenderCronSyncService

    with patch("backend.services.core.render_sync_service.settings") as mock_settings:
        mock_settings.RENDER_API_KEY = None
        mock_settings.RENDER_OWNER_ID = None
        svc = RenderCronSyncService()
        assert not svc.enabled


def test_render_sync_enabled_when_configured():
    from backend.services.core.render_sync_service import RenderCronSyncService

    with patch("backend.services.core.render_sync_service.settings") as mock_settings:
        mock_settings.RENDER_API_KEY = "rnd_test_key"
        mock_settings.RENDER_OWNER_ID = "usr-test"
        svc = RenderCronSyncService()
        assert svc.enabled


def test_render_sync_all_skipped_without_key(db_session):
    if db_session is None:
        pytest.skip("No test DB")
    from backend.services.core.render_sync_service import RenderCronSyncService

    with patch("backend.services.core.render_sync_service.settings") as mock_settings:
        mock_settings.RENDER_API_KEY = None
        mock_settings.RENDER_OWNER_ID = None
        svc = RenderCronSyncService()
        result = svc.sync_all(db_session)
        assert result["status"] == "skipped"


def test_render_sync_creates_new_cron(db_session):
    if db_session is None:
        pytest.skip("No test DB")
    from backend.services.core.render_sync_service import RenderCronSyncService

    schedule = CronSchedule(
        id="sync_test",
        display_name="Sync Test",
        group="test",
        task="backend.tasks.test.run",
        cron="0 3 * * *",
        enabled=True,
    )
    db_session.add(schedule)
    db_session.commit()

    with patch("backend.services.core.render_sync_service.settings") as mock_settings:
        mock_settings.RENDER_API_KEY = "rnd_key"
        mock_settings.RENDER_OWNER_ID = "usr-123"
        svc = RenderCronSyncService()

        mock_resp_list = MagicMock()
        mock_resp_list.status_code = 200
        mock_resp_list.json.return_value = []

        mock_resp_create = MagicMock()
        mock_resp_create.status_code = 201
        mock_resp_create.json.return_value = {"service": {"id": "srv-new-123"}}

        with patch.object(svc, "_request", side_effect=[mock_resp_list, mock_resp_create]):
            result = svc.sync_all(db_session)
            assert result["created"] == 1

    db_session.refresh(schedule)
    assert schedule.render_service_id == "srv-new-123"
    assert schedule.render_synced_at is not None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


def test_list_schedules_returns_db_mode(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        resp = client.get("/api/v1/admin/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "db"
        assert "render_sync_enabled" in data
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_create_schedule_validates_cron(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        resp = client.post("/api/v1/admin/schedules", json={
            "id": "bad_cron",
            "display_name": "Bad",
            "task": "test.task",
            "cron": "not valid cron",
        })
        assert resp.status_code == 400
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_create_and_delete_schedule(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        with patch("backend.api.routes.admin.scheduler.render_sync_service") as mock_sync:
            mock_sync.enabled = False
            mock_sync.sync_one.return_value = {"status": "skipped"}

            resp = client.post("/api/v1/admin/schedules", json={
                "id": "api_test_job",
                "display_name": "API Test",
                "task": "backend.tasks.test.run",
                "cron": "0 3 * * *",
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

            resp = client.delete("/api/v1/admin/schedules/api_test_job")
            assert resp.status_code == 200
            assert resp.json()["deleted"] == "api_test_job"
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_pause_and_resume_schedule(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db

    schedule = CronSchedule(
        id="pause_test",
        display_name="Pause Test",
        group="test",
        task="backend.tasks.test.run",
        cron="0 3 * * *",
        enabled=True,
    )
    db_session.add(schedule)
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        with patch("backend.api.routes.admin.scheduler.render_sync_service") as mock_sync:
            mock_sync.enabled = False
            mock_sync.sync_one.return_value = {"status": "skipped"}

            resp = client.post("/api/v1/admin/schedules/pause_test/pause")
            assert resp.status_code == 200
            db_session.refresh(schedule)
            assert schedule.enabled is False

            resp = client.post("/api/v1/admin/schedules/pause_test/resume")
            assert resp.status_code == 200
            db_session.refresh(schedule)
            assert schedule.enabled is True
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_sync_endpoint(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        with patch("backend.api.routes.admin.scheduler.render_sync_service") as mock_sync:
            mock_sync.sync_all.return_value = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

            resp = client.post("/api/v1/admin/schedules/sync")
            assert resp.status_code == 200
            assert resp.json()["sync"]["errors"] == 0
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_catalog_endpoint():
    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    try:
        resp = client.get("/api/v1/admin/tasks/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert "catalog" in data
        groups = data["catalog"]
        assert "market_data" in groups
        assert len(groups["market_data"]) >= 1
        assert "portfolio" in groups
        assert len(groups["portfolio"]) >= 1
        assert "maintenance" in groups
        assert len(groups["maintenance"]) >= 1
    finally:
        app.dependency_overrides.pop(get_admin_user, None)


def test_audit_trail_on_create_and_delete(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db
    from backend.models.market_data import CronScheduleAudit

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock(email="audit@test.local", username="audit")
    app.dependency_overrides[get_db] = override_db
    try:
        with patch("backend.api.routes.admin.scheduler.render_sync_service") as mock_sync:
            mock_sync.enabled = False
            mock_sync.sync_one.return_value = {"status": "skipped"}

            client.post("/api/v1/admin/schedules", json={
                "id": "audit_trail_test",
                "display_name": "Audit Trail Test",
                "task": "backend.tasks.test.run",
                "cron": "0 3 * * *",
            })
            client.delete("/api/v1/admin/schedules/audit_trail_test")

        audit_rows = (
            db_session.query(CronScheduleAudit)
            .filter(CronScheduleAudit.schedule_id == "audit_trail_test")
            .order_by(CronScheduleAudit.timestamp)
            .all()
        )
        assert len(audit_rows) >= 2
        actions = [r.action for r in audit_rows]
        assert "created" in actions
        assert "deleted" in actions
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_history_endpoint(db_session):
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db
    from backend.models.market_data import CronScheduleAudit

    db_session.add(CronScheduleAudit(
        schedule_id="history_test",
        action="created",
        actor="test@local",
        changes={"task": "test.run"},
    ))
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        resp = client.get("/api/v1/admin/schedules/history")
        assert resp.status_code == 200
        rows = resp.json()["history"]
        assert len(rows) >= 1
        assert any(r["schedule_id"] == "history_test" for r in rows)

        resp_filtered = client.get("/api/v1/admin/schedules/history", params={"schedule_id": "history_test"})
        assert resp_filtered.status_code == 200
        assert all(r["schedule_id"] == "history_test" for r in resp_filtered.json()["history"])
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_auto_seed_on_empty_table(db_session):
    """When cron_schedule table is empty, GET /admin/schedules auto-seeds from catalog."""
    if db_session is None:
        pytest.skip("No test DB")

    from backend.database import get_db
    import backend.api.routes.admin.scheduler as mod

    mod._seeded = False

    def override_db():
        yield db_session

    app.dependency_overrides[get_admin_user] = lambda: MagicMock()
    app.dependency_overrides[get_db] = override_db
    try:
        assert db_session.query(CronSchedule).count() == 0
        resp = client.get("/api/v1/admin/schedules")
        assert resp.status_code == 200
        schedules = resp.json()["schedules"]
        assert len(schedules) >= len(CATALOG)
    finally:
        mod._seeded = False
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)
