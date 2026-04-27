"""Integration tests for GDPR export + delete services.

Hits the real test database via the ``db_session`` fixture so we
exercise the full SQLAlchemy reflection path (the production code
walks ``Base.metadata.sorted_tables``).

We monkeypatch the Celery task dispatch so ``start_export`` /
``confirm`` don't try to enqueue a real task; we then drive
``run_export`` / ``run_delete`` directly.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime, timezone

import pytest

from app.models.multitenant import (
    GDPRDeleteJob,
    GDPRExportJob,
    GDPRJobStatus,
    IncidentRow,
)
from app.models.user import User
from app.services.gdpr.delete_service import (
    GDPR_DELETE_CASCADE_TABLES,
    GDPRDeleteService,
)
from app.services.gdpr.export_service import GDPRExportService
from app.services.gdpr.delete_service import _user_scoped_tables
from app.tasks.multitenant.gdpr import GDPR_DELETE_CASCADE_TABLES as TASK_GDPR_DELETE_CASCADE_TABLES


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _make_user(db, *, suffix: str) -> User:
    u = User(
        username=f"gdpr_{suffix}_{int(datetime.now(UTC).timestamp() * 1000)}",
        email=f"gdpr_{suffix}_{int(datetime.now(UTC).timestamp() * 1000)}@example.com",
        password_hash="x",
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture(autouse=True)
def _patch_celery_dispatch(monkeypatch):
    """Stub out Celery .delay() so we drive workers inline."""
    import app.tasks.multitenant.gdpr as gdpr_tasks

    class _Inline:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, *args, **kwargs):  # noqa: D401
            return None

    monkeypatch.setattr(gdpr_tasks, "run_export", _Inline(None))
    monkeypatch.setattr(gdpr_tasks, "run_delete", _Inline(None))


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


def test_export_writes_zip_with_manifest_and_per_table_csvs(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "app.config.settings.GDPR_EXPORT_LOCAL_DIR", str(tmp_path)
    )
    user = _make_user(db_session, suffix="export")

    svc = GDPRExportService(db_session)
    job = GDPRExportJob(user_id=user.id, status=GDPRJobStatus.PENDING.value)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    svc.run_export(job.id)
    db_session.refresh(job)
    assert job.status == GDPRJobStatus.COMPLETED.value
    assert job.bytes_written and job.bytes_written > 0
    assert job.download_url and job.download_url.startswith("local://")

    # ZIP must contain MANIFEST.json + at least one users.csv-style file.
    zip_path = tmp_path / job.download_url.removeprefix("local://")
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert "MANIFEST.json" in names
        # At least the users-related per-tenant table should be present.
        assert any(n.endswith(".csv") for n in names)


def test_export_does_not_leak_other_tenants_rows(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "app.config.settings.GDPR_EXPORT_LOCAL_DIR", str(tmp_path)
    )
    a = _make_user(db_session, suffix="iso_a")
    b = _make_user(db_session, suffix="iso_b")

    job = GDPRExportJob(user_id=a.id, status=GDPRJobStatus.PENDING.value)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    GDPRExportService(db_session).run_export(job.id)
    db_session.refresh(job)

    zip_path = tmp_path / job.download_url.removeprefix("local://")
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            content = zf.read(name).decode("utf-8")
            # Tenant B's username/email must NOT appear in tenant A's
            # export. (This is a coarse but high-signal check; the
            # row-level filter is asserted by the test below.)
            assert b.username not in content, f"{b.username} leaked in {name}"
            assert b.email not in content, f"{b.email} leaked in {name}"


def test_export_failure_writes_incident_row(
    db_session, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "app.config.settings.GDPR_EXPORT_LOCAL_DIR", str(tmp_path)
    )
    user = _make_user(db_session, suffix="fail")
    job = GDPRExportJob(user_id=user.id, status=GDPRJobStatus.PENDING.value)
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    svc = GDPRExportService(db_session)
    # Force the writer to explode.
    monkeypatch.setattr(svc, "_write_zip", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("disk full")))

    with pytest.raises(RuntimeError):
        svc.run_export(job.id)
    db_session.refresh(job)
    assert job.status == GDPRJobStatus.FAILED.value
    assert "disk full" in (job.error_message or "")
    incidents = (
        db_session.query(IncidentRow)
        .filter(
            IncidentRow.user_id == user.id,
            IncidentRow.category == "gdpr.export_failed",
        )
        .all()
    )
    assert len(incidents) == 1


# ---------------------------------------------------------------------------
# delete (two-phase)
# ---------------------------------------------------------------------------


def test_delete_two_phase_success(db_session):
    user = _make_user(db_session, suffix="del")
    svc = GDPRDeleteService(db_session)
    job, token = svc.start_delete(user.id)

    assert job.status == GDPRJobStatus.PENDING.value
    assert job.confirmation_token_hash and len(job.confirmation_token_hash) == 64
    assert token  # plaintext returned exactly once

    confirmed = svc.confirm(user.id, job.id, token)
    assert confirmed.status == GDPRJobStatus.CONFIRMED.value
    assert confirmed.confirmation_token_hash is None  # single-use

    svc.run_delete(job.id)
    db_session.refresh(confirmed)
    assert confirmed.status == GDPRJobStatus.COMPLETED.value

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.is_active is False
    assert refreshed.email.endswith("@axiomfolio.invalid")


def test_delete_confirm_rejects_cross_tenant_job(db_session):
    a = _make_user(db_session, suffix="x_a")
    b = _make_user(db_session, suffix="x_b")
    svc = GDPRDeleteService(db_session)
    job, token = svc.start_delete(a.id)

    with pytest.raises(PermissionError):
        svc.confirm(b.id, job.id, token)


def test_delete_confirm_rejects_wrong_token(db_session):
    user = _make_user(db_session, suffix="badtok")
    svc = GDPRDeleteService(db_session)
    job, _real_token = svc.start_delete(user.id)
    with pytest.raises(PermissionError):
        svc.confirm(user.id, job.id, "not-the-real-token")


def test_delete_run_refuses_when_not_confirmed(db_session):
    user = _make_user(db_session, suffix="unc")
    svc = GDPRDeleteService(db_session)
    job, _ = svc.start_delete(user.id)
    # status is PENDING, never CONFIRMED.
    svc.run_delete(job.id)
    db_session.refresh(job)
    assert job.status == GDPRJobStatus.PENDING.value
    # User row must NOT have been scrubbed.
    user_row = db_session.get(User, user.id)
    assert user_row is not None
    assert user_row.is_active is True


def test_delete_failure_writes_incident_row(db_session, monkeypatch):
    user = _make_user(db_session, suffix="delfail")
    svc = GDPRDeleteService(db_session)
    job, token = svc.start_delete(user.id)
    svc.confirm(user.id, job.id, token)

    monkeypatch.setattr(
        svc, "_cascade_delete", lambda _uid: (_ for _ in ()).throw(RuntimeError("FK boom"))
    )
    with pytest.raises(RuntimeError):
        svc.run_delete(job.id)
    db_session.expire_all()
    refreshed = db_session.get(GDPRDeleteJob, job.id)
    assert refreshed.status == GDPRJobStatus.FAILED.value
    assert "FK boom" in (refreshed.error_message or "")
    incidents = (
        db_session.query(IncidentRow)
        .filter(
            IncidentRow.user_id == user.id,
            IncidentRow.category == "gdpr.delete_failed",
        )
        .all()
    )
    assert len(incidents) == 1


def test_gdpr_user_scoped_tables_include_historical_import_runs():
    table_names = {t.name for t in _user_scoped_tables()}
    assert "historical_import_runs" in table_names


def test_gdpr_delete_registry_shared_between_service_and_task_module():
    assert TASK_GDPR_DELETE_CASCADE_TABLES == GDPR_DELETE_CASCADE_TABLES
