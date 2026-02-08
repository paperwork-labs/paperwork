import json
import sys
import types
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.dependencies import get_admin_user
from backend.tasks.job_catalog import CATALOG, seed_redbeat_if_empty
from backend.tasks.celery_app import celery_app
from backend.tasks.schedule_metadata import ScheduleMetadata


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _admin_override():
    class _Admin:
        email = "admin@test.local"
        username = "admin"

    app.dependency_overrides[get_admin_user] = lambda: _Admin()
    yield
    app.dependency_overrides.pop(get_admin_user, None)


@pytest.fixture(autouse=True)
def scheduler_env(monkeypatch):
    """In-memory stub for RedBeat + metadata + Redis paused store."""

    store: dict[str, dict[str, object]] = {
        "entries": {},
        "metadata": {},
        "paused": {},
    }

    class DummyRDB:
        def scan_iter(self, match=None):
            if match == "redbeat:*:task":
                for key in list(store["entries"].keys()):
                    yield key.encode()
            return []

    class DummyScheduler:
        def __init__(self, app):
            self.rdb = DummyRDB()

    class DummyEntry:
        registry = store["entries"]

        def __init__(self, name, task, schedule, args, kwargs, options, app):
            self.name = name
            self.task = task
            self.schedule = schedule
            self.args = args
            self.kwargs = kwargs
            self.options = options
            self.key = f"redbeat:{name}:task"

        def save(self):
            DummyEntry.registry[self.key] = self

        def delete(self):
            DummyEntry.registry.pop(self.key, None)

        @classmethod
        def from_key(cls, key, app):
            resolved = key.decode() if isinstance(key, bytes) else key
            entry = cls.registry.get(resolved)
            if not entry:
                raise KeyError(resolved)
            return entry

    sched_module = types.ModuleType("redbeat.schedulers")
    sched_module.RedBeatScheduler = DummyScheduler
    sched_module.RedBeatSchedulerEntry = DummyEntry
    redbeat_pkg = types.ModuleType("redbeat")
    redbeat_pkg.schedulers = sched_module
    monkeypatch.setitem(sys.modules, "redbeat", redbeat_pkg)
    monkeypatch.setitem(sys.modules, "redbeat.schedulers", sched_module)

    from backend.tasks import job_catalog
    from backend.api.routes import admin_scheduler as routes

    def _save_meta(name, meta, **_):
        store["metadata"][name] = meta

    def _load_meta(name, **_):
        meta = store["metadata"].get(name)
        return meta

    def _delete_meta(name, **_):
        store["metadata"].pop(name, None)

    monkeypatch.setattr(job_catalog, "save_schedule_metadata", _save_meta)
    monkeypatch.setattr(routes, "save_schedule_metadata", _save_meta)
    monkeypatch.setattr(routes, "load_schedule_metadata", _load_meta)
    monkeypatch.setattr(routes, "delete_schedule_metadata", _delete_meta)

    class MemoryRedis:
        def set(self, key, value):
            store["paused"][key] = value

        def get(self, key):
            return store["paused"].get(key)

        def delete(self, key):
            store["paused"].pop(key, None)

        def scan_iter(self, match=None):
            if match == "redbeat:paused:*":
                for key in list(store["paused"].keys()):
                    yield key
            return []

    monkeypatch.setattr(routes, "_get_redis", lambda: MemoryRedis())
    yield store


def test_catalog_seed_persists_metadata(scheduler_env):
    assert scheduler_env["entries"] == {}
    result = seed_redbeat_if_empty(celery_app)
    assert result["seeded"] == len(CATALOG)
    assert len(scheduler_env["entries"]) == len(CATALOG)
    assert "market_indices_constituents_refresh" in scheduler_env["metadata"]
    meta: ScheduleMetadata = scheduler_env["metadata"]["market_indices_constituents_refresh"]
    assert meta.safety.timeout_s == CATALOG[0].timeout_s


def test_create_schedule_with_metadata_roundtrip(scheduler_env):
    payload = {
        "name": "test-job",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "cron": "0 * * * *",
        "timezone": "UTC",
        "metadata": {
            "queue": "market_data_high",
            "safety": {"timeout_s": 120, "singleflight": True, "max_concurrency": 1},
            "hooks": {"discord_webhook": "playground", "alert_on": ["failure", "success"]},
            "notes": "integration test",
        },
    }
    resp = client.post("/api/v1/admin/schedules", json=payload)
    assert resp.status_code == 200, resp.text
    listing = client.get("/api/v1/admin/schedules").json()
    names = {row["name"] for row in listing["schedules"]}
    assert "test-job" in names
    assert isinstance(scheduler_env["metadata"]["test-job"], ScheduleMetadata)


def test_create_schedule_with_windows_and_dependencies(scheduler_env):
    payload = {
        "name": "complex-job",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "cron": "15 3 * * 1-5",
        "timezone": "America/New_York",
        "metadata": {
            "queue": "market_data_high",
            "dependencies": ["market_indices_constituents_refresh"],
            "maintenance_windows": [
                {"start": "2025-01-01T09:00:00Z", "end": "2025-01-01T09:30:00Z", "timezone": "UTC"}
            ],
            "preflight_checks": ["redis", "postgres"],
            "hooks": {"discord_webhook": "system_status", "alert_on": ["failure", "slow"]},
        },
    }
    resp = client.post("/api/v1/admin/schedules", json=payload)
    assert resp.status_code == 200, resp.text
    meta: ScheduleMetadata = scheduler_env["metadata"]["complex-job"]
    assert meta.queue == "market_data_high"
    assert meta.dependencies == ["market_indices_constituents_refresh"]
    assert meta.preflight_checks == ["redis", "postgres"]
    assert meta.maintenance_windows[0].timezone == "UTC"
    assert "slow" in meta.hooks.alert_on


def test_preview_cron_handles_timezone_offset():
    resp = client.get(
        "/api/v1/admin/schedules/preview",
        params={"cron": "0 12 * * *", "timezone": "America/New_York", "count": 2},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["tz"] == "America/New_York"
    for ts in payload["next_runs_utc"]:
        # Should be valid ISO timestamps in UTC
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None


def test_pause_and_resume_flow_preserves_metadata(scheduler_env):
    payload = {
        "name": "pause-job",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "cron": "0 * * * *",
        "timezone": "UTC",
        "metadata": {"queue": "md-default"},
    }
    create_resp = client.post("/api/v1/admin/schedules", json=payload)
    assert create_resp.status_code == 200, create_resp.text
    pause_resp = client.post("/api/v1/admin/schedules/pause", params={"name": "pause-job"})
    assert pause_resp.status_code == 200, pause_resp.text
    assert f"redbeat:paused:pause-job" in scheduler_env["paused"]
    paused_payload = json.loads(scheduler_env["paused"][f"redbeat:paused:pause-job"])
    assert paused_payload["metadata"]["queue"] == "md-default"
    resume_resp = client.post("/api/v1/admin/schedules/resume", params={"name": "pause-job"})
    assert resume_resp.status_code == 200, resume_resp.text
    assert f"redbeat:paused:pause-job" not in scheduler_env["paused"]


def test_export_import_roundtrip_preserves_hooks(scheduler_env):
    payload = {
        "name": "exportable",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "cron": "0 * * * *",
        "timezone": "UTC",
        "metadata": {
            "queue": "coverage",
            "hooks": {"discord_webhook": "system_status", "discord_channels": ["signals"], "alert_on": ["failure", "slow"]},
        },
    }
    create_resp = client.post("/api/v1/admin/schedules", json=payload)
    assert create_resp.status_code == 200, create_resp.text
    exported = client.get("/api/v1/admin/schedules/export").json()
    assert exported["schedules"]
    # Simulate clean slate then import
    scheduler_env["entries"].clear()
    scheduler_env["metadata"].clear()
    import_resp = client.post("/api/v1/admin/schedules/import", json=exported)
    assert import_resp.status_code == 200, import_resp.text
    listing = client.get("/api/v1/admin/schedules").json()["schedules"]
    imported = next((row for row in listing if row["name"] == "exportable"), None)
    assert imported is not None
    hooks = imported["metadata"]["hooks"]
    assert hooks["discord_webhook"] == "system_status"
    assert "signals" in hooks["discord_channels"]
    assert "slow" in hooks["alert_on"]


def test_audit_fields_update_on_modify(scheduler_env):
    payload = {
        "name": "audit-job",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "cron": "0 3 * * *",
        "timezone": "UTC",
        "metadata": {
            "queue": "default",
            "hooks": {"discord_webhook": "system_status"},
        },
    }
    create_resp = client.post("/api/v1/admin/schedules", json=payload)
    assert create_resp.status_code == 200, create_resp.text
    meta: ScheduleMetadata = scheduler_env["metadata"]["audit-job"]
    assert meta.audit["created_by"] == "admin@test.local"
    update_resp = client.put(
        "/api/v1/admin/schedules/audit-job",
        json={
            "cron": "0 4 * * *",
            "timezone": "UTC",
            "metadata": {"queue": "critical"},
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    updated_meta: ScheduleMetadata = scheduler_env["metadata"]["audit-job"]
    assert updated_meta.queue == "critical"
    assert updated_meta.audit["updated_by"] == "admin@test.local"


def test_hooks_support_mentions_and_threshold(scheduler_env):
    payload = {
        "name": "alerting-job",
        "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
        "cron": "10 * * * *",
        "timezone": "UTC",
        "metadata": {
            "hooks": {
                "discord_mentions": ["@ops-team", "<@12345>"],
                "slow_threshold_s": 45,
            },
        },
    }
    resp = client.post("/api/v1/admin/schedules", json=payload)
    assert resp.status_code == 200, resp.text
    meta: ScheduleMetadata = scheduler_env["metadata"]["alerting-job"]
    assert meta.hooks.discord_mentions == ["@ops-team", "<@12345>"]
    assert meta.hooks.slow_threshold_s == 45


def test_update_schedule_requires_explicit_cron(scheduler_env):
    create_resp = client.post(
        "/api/v1/admin/schedules",
        json={
            "name": "update-me",
            "task": "backend.tasks.market_data_tasks.monitor_coverage_health",
            "cron": "0 5 * * *",
            "timezone": "UTC",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    update_resp = client.put(
        "/api/v1/admin/schedules/update-me",
        json={"timezone": "UTC"},
    )
    assert update_resp.status_code == 400

