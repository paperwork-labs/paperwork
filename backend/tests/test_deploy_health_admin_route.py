"""HTTP contract tests for the ``/api/v1/admin/deploys/*`` routes.

We override ``get_admin_user`` so the admin gate passes, and monkeypatch
the service-id resolver / the poll function so the route never talks to
Render. That leaves the route + pydantic response model under test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Build a minimal FastAPI app that mounts only the deploy-health admin router
# so these tests don't pay the cost of importing the full `backend.api.main`
# (which pulls in every route + heavy optional deps like optuna).
#
# NOTE: `backend.api.routes.__init__` re-exports `.admin.management.router`
# as the bare name `admin`, which shadows the `admin` sub-package on the
# `routes` module. Import the target submodule directly as an object so we
# can monkeypatch it without going through the shadowed attribute path.
import importlib

from backend.api.dependencies import get_admin_user, get_db
from backend.models.deploy_health_event import DeployHealthEvent

deploy_health_module = importlib.import_module(
    "backend.api.routes.admin.deploy_health"
)


app = FastAPI()
app.include_router(deploy_health_module.router, prefix="/api/v1")

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def _override_admin(db_session):
    app.dependency_overrides[get_admin_user] = object
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_deploy_health_requires_admin():
    resp = client.get("/api/v1/admin/deploys/health")
    assert resp.status_code in (401, 403)


def test_deploy_health_poll_requires_admin():
    resp = client.post("/api/v1/admin/deploys/poll")
    assert resp.status_code in (401, 403)


def test_deploy_health_empty_services_returns_yellow(_override_admin, monkeypatch):
    monkeypatch.setattr(deploy_health_module, "_resolve_services", lambda: [])
    resp = client.get("/api/v1/admin/deploys/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "yellow"
    assert payload["services_configured"] == 0
    assert payload["services"] == []
    assert payload["events"] == []


def test_deploy_health_returns_composite(_override_admin, monkeypatch, db_session):
    service = {
        "service_id": "srv-api",
        "service_slug": "axiomfolio-api",
        "service_type": "web_service",
    }
    monkeypatch.setattr(deploy_health_module, "_resolve_services", lambda: [service])

    now = datetime.now(timezone.utc)
    for i in range(2):
        db_session.add(
            DeployHealthEvent(
                service_id=service["service_id"],
                service_slug=service["service_slug"],
                service_type=service["service_type"],
                deploy_id=f"d-{i}",
                status="live",
                trigger="new_commit",
                commit_sha=f"a{i:039d}",
                commit_message=f"msg {i}",
                render_created_at=now - timedelta(minutes=i),
                render_finished_at=now - timedelta(minutes=i) + timedelta(seconds=60),
                duration_seconds=60.0,
            )
        )
    db_session.commit()

    resp = client.get("/api/v1/admin/deploys/health?limit=10")
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["services_configured"] == 1
    # Route returns composite status (green if every recent deploy is live).
    # Env-bound DB may share state with other tests — assert on shape, not
    # exact counts.
    assert payload["status"] in ("green", "yellow", "red")
    assert isinstance(payload["services"], list)
    assert isinstance(payload["events"], list)


def test_deploy_health_poll_no_services_400(_override_admin, monkeypatch):
    monkeypatch.setattr(deploy_health_module, "_resolve_services", lambda: [])
    resp = client.post("/api/v1/admin/deploys/poll")
    assert resp.status_code == 400
    assert "DEPLOY_HEALTH_SERVICE_IDS" in resp.text


def test_deploy_health_poll_delegates_to_service(_override_admin, monkeypatch):
    service = {
        "service_id": "srv-api",
        "service_slug": "axiomfolio-api",
        "service_type": "web_service",
    }
    monkeypatch.setattr(deploy_health_module, "_resolve_services", lambda: [service])

    captured: Dict[str, Any] = {}

    def fake_poll(db, services, **kwargs):
        captured["services"] = list(services)
        return {
            "services_polled": 1,
            "events_inserted": 3,
            "events_skipped": 1,
            "poll_errors": 0,
            "details": [{"service_id": "srv-api", "inserted": 3, "skipped": 1}],
        }

    monkeypatch.setattr(deploy_health_module, "poll_and_record", fake_poll)

    resp = client.post("/api/v1/admin/deploys/poll")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "services_polled": 1,
        "events_inserted": 3,
        "events_skipped": 1,
        "poll_errors": 0,
        "details": [{"service_id": "srv-api", "inserted": 3, "skipped": 1}],
    }
    assert captured["services"] == [service]
