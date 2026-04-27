"""Integration tests for `/internal/secrets` routes."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app
from app.services.secrets_intelligence import SecretsIntelligence


@pytest.mark.asyncio
async def test_post_internal_secrets_events_records_episode(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "BRAIN_INTERNAL_TOKEN", "test-internal-brain-token")
    intel = SecretsIntelligence(db_session)
    await intel.upsert_registry_entry(
        "API_EP",
        service="test",
        rotation_cadence_days=90,
    )
    await db_session.commit()

    async def _override_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    fastapi_app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=fastapi_app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/internal/secrets/events",
                headers={"Authorization": "Bearer test-internal-brain-token"},
                json={
                    "secret_name": "API_EP",
                    "event_type": "intake",
                    "source": "studio_intake",
                    "summary": "pasted via intake",
                    "details": {"x": 1},
                },
            )
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert data.get("episode_id")
    finally:
        fastapi_app.dependency_overrides.clear()

    again = SecretsIntelligence(db_session)
    eps = await again.episodes_for("API_EP", limit=5)
    assert any(e.event_type == "intake" for e in eps)


@pytest.mark.asyncio
async def test_get_registry_after_seed(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "BRAIN_INTERNAL_TOKEN", "tok2")
    name = f"SEED_{uuid.uuid4().hex[:8]}"
    intel = SecretsIntelligence(db_session)
    await intel.upsert_registry_entry(
        name,
        service="test",
        purpose="probe",
        criticality="low",
    )
    await db_session.commit()

    async def _override_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    fastapi_app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=fastapi_app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/internal/secrets/registry",
                headers={"Authorization": "Bearer tok2"},
            )
        assert res.status_code == 200
        body = res.json()
        assert body.get("ok") is True
        names = {r["name"] for r in body["data"]}
        assert name in names
    finally:
        fastapi_app.dependency_overrides.clear()
