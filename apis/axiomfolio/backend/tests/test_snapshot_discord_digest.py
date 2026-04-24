import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.tests.auth_test_utils import approve_user_for_login_tests
from backend.models.market_data import MarketSnapshot
from backend.models.index_constituent import IndexConstituent
from datetime import datetime, timedelta, timezone


def _register_and_login_admin(client: TestClient, db_session) -> str:
    u = "admin_digest"
    pw = "Passw0rd!"
    email = "admin_digest@example.com"
    r = client.post(
        "/api/v1/auth/register",
        json={"username": u, "password": pw, "email": email},
    )
    assert r.status_code in (200, 201)
    approve_user_for_login_tests(u, db=db_session)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r2.status_code == 200
    token = r2.json()["access_token"]

    from backend.models.user import User, UserRole

    user = db_session.query(User).filter(User.username == u).first()
    assert user is not None
    user.role = UserRole.OWNER
    db_session.commit()
    return token


@pytest.mark.asyncio
async def test_admin_snapshot_digest_sends_via_brain(monkeypatch, db_session):
    client = TestClient(app, raise_server_exceptions=False)
    from backend.database import get_db
    from backend.api.routes.market import admin as admin_routes
    from backend.services.brain.webhook_client import brain_webhook, BrainWebhookClient

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        token = _register_and_login_admin(client, db_session)

        db_session.add(IndexConstituent(index_name="SP500", symbol="AAA", is_active=True))
        db_session.add(IndexConstituent(index_name="SP500", symbol="BBB", is_active=True))
        db_session.commit()

        now = datetime.now(timezone.utc)
        db_session.add(
            MarketSnapshot(
                symbol="AAA",
                analysis_type="technical_snapshot",
                expiry_timestamp=now + timedelta(hours=12),
                current_price=10.0,
                rs_mansfield_pct=12.3,
                stage_label="2",
                raw_analysis={"current_price": 10.0},
            )
        )
        db_session.add(
            MarketSnapshot(
                symbol="BBB",
                analysis_type="technical_snapshot",
                expiry_timestamp=now + timedelta(hours=12),
                current_price=20.0,
                rs_mansfield_pct=-3.4,
                stage_label="4",
                raw_analysis={"current_price": 20.0},
            )
        )
        db_session.commit()

        # Route checks brain_webhook.webhook_url; patch the class property so CI env and
        # pydantic-settings quirks cannot leave it falsy (monkeypatch restores after test).
        monkeypatch.setattr(
            BrainWebhookClient,
            "webhook_url",
            property(lambda _self: "https://brain.example"),
        )

        async def _fake_tracked_symbols_async(_db, redis_async=None):
            return ["AAA", "BBB"]

        monkeypatch.setattr(admin_routes, "tracked_symbols_async", _fake_tracked_symbols_async)

        calls = []

        async def fake_notify(event, data, user_id=None):
            calls.append((event, data, user_id))
            return True

        monkeypatch.setattr(brain_webhook, "notify", fake_notify)

        r = client.post(
            "/api/v1/market-data/admin/snapshots/discord-digest",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sent"] is True
        assert body.get("destination") == "brain"
        assert calls[0][0] == "snapshot_digest"
        assert "MarketSnapshot digest" in calls[0][1]["content"]
        assert "Top RS" in calls[0][1]["content"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_admin_snapshot_digest_requires_token(db_session):
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/api/v1/market-data/admin/snapshots/discord-digest")
    assert r.status_code in (401, 403)
