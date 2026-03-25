import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.tests.auth_test_utils import approve_user_for_login_tests
from backend.config import settings
from backend.models.market_data import MarketSnapshot
from backend.models.index_constituent import IndexConstituent
from datetime import datetime, timedelta


def _register_and_login_admin(client: TestClient, db_session) -> str:
    # Register + login
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

    # Promote to admin directly in DB
    from backend.models.user import User, UserRole

    user = db_session.query(User).filter(User.username == u).first()
    assert user is not None
    user.role = UserRole.ADMIN
    db_session.commit()
    return token


@pytest.mark.asyncio
async def test_admin_snapshot_digest_sends_via_bot(monkeypatch, db_session):
    client = TestClient(app, raise_server_exceptions=False)
    # Ensure API routes use the same session/transaction as this test.
    from backend.database import get_db

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    token = _register_and_login_admin(client, db_session)

    # Seed tracked universe fallback (active constituents)
    db_session.add(IndexConstituent(index_name="SP500", symbol="AAA", is_active=True))
    db_session.add(IndexConstituent(index_name="SP500", symbol="BBB", is_active=True))
    db_session.commit()

    now = datetime.utcnow()
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

    # Configure bot client at runtime
    from backend.services.notifications.discord_bot import discord_bot_client

    discord_bot_client.token = "test-token"
    settings.DISCORD_BOT_DEFAULT_CHANNEL_ID = "123"

    sent = {}

    async def fake_send_message(*, channel_id: str, content: str, max_attempts: int = 3) -> bool:
        sent["channel_id"] = channel_id
        sent["content"] = content
        return True

    monkeypatch.setattr(discord_bot_client, "send_message", fake_send_message)

    r = client.post(
        "/api/v1/market-data/admin/snapshots/discord-digest",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["sent"] is True
    assert sent["channel_id"] == "123"
    assert "MarketSnapshot digest" in sent["content"]
    assert "Top RS" in sent["content"]

    app.dependency_overrides.pop(get_db, None)


def test_admin_snapshot_digest_requires_token(db_session):
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/api/v1/market-data/admin/snapshots/discord-digest")
    assert r.status_code in (401, 403)


