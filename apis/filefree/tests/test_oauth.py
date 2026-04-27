"""Tests for Google and Apple OAuth social login flow."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.oauth_service import OAuthUser

MOCK_GOOGLE_USER = OAuthUser(
    email="guser@gmail.com",
    name="Google User",
    provider_id="google-sub-12345",
)

MOCK_APPLE_USER = OAuthUser(
    email="auser@icloud.com",
    name="Apple User",
    provider_id="apple-sub-67890",
)


@pytest.fixture
def mock_google_verify():
    with patch(
        "app.routers.auth.verify_google_token",
        new_callable=AsyncMock,
        return_value=MOCK_GOOGLE_USER,
    ) as m:
        yield m


@pytest.fixture
def mock_apple_verify():
    with patch(
        "app.routers.auth.verify_apple_token",
        new_callable=AsyncMock,
        return_value=MOCK_APPLE_USER,
    ) as m:
        yield m


@pytest.mark.usefixtures("mock_google_verify")
class TestGoogleAuth:
    @pytest.mark.asyncio
    async def test_google_creates_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/google", json={"id_token": "fake-google-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["user"]["email"] == "guser@gmail.com"
        assert data["data"]["user"]["full_name"] == "Google User"
        assert data["data"]["user"]["auth_provider"] == "google"
        assert data["data"]["user"]["email_verified"] is True
        assert "csrf_token" in data["data"]
        assert "session" in resp.cookies

    @pytest.mark.asyncio
    async def test_google_idempotent(self, client: AsyncClient):
        resp1 = await client.post("/api/v1/auth/google", json={"id_token": "fake-google-token"})
        user_id_1 = resp1.json()["data"]["user"]["id"]

        resp2 = await client.post("/api/v1/auth/google", json={"id_token": "fake-google-token"})
        user_id_2 = resp2.json()["data"]["user"]["id"]

        assert user_id_1 == user_id_2

    @pytest.mark.asyncio
    async def test_google_missing_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/google", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_google_invalid_token(self, client: AsyncClient):
        from app.utils.exceptions import UnauthorizedError

        with patch(
            "app.routers.auth.verify_google_token",
            new_callable=AsyncMock,
            side_effect=UnauthorizedError("Invalid Google token"),
        ):
            resp = await client.post("/api/v1/auth/google", json={"id_token": "bad-token"})
            assert resp.status_code == 401
            assert resp.json()["success"] is False


@pytest.mark.usefixtures("mock_apple_verify")
class TestAppleAuth:
    @pytest.mark.asyncio
    async def test_apple_creates_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/apple", json={"id_token": "fake-apple-token"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["user"]["email"] == "auser@icloud.com"
        assert data["data"]["user"]["auth_provider"] == "apple"
        assert "csrf_token" in data["data"]
        assert "session" in resp.cookies

    @pytest.mark.asyncio
    async def test_apple_with_user_info(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/apple",
            json={
                "id_token": "fake-apple-token",
                "user": {"name": {"firstName": "Test", "lastName": "User"}},
            },
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_apple_idempotent(self, client: AsyncClient):
        resp1 = await client.post("/api/v1/auth/apple", json={"id_token": "fake-apple-token"})
        user_id_1 = resp1.json()["data"]["user"]["id"]

        resp2 = await client.post("/api/v1/auth/apple", json={"id_token": "fake-apple-token"})
        user_id_2 = resp2.json()["data"]["user"]["id"]

        assert user_id_1 == user_id_2


class TestAccountLinking:
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_google_verify")
    async def test_email_user_can_login_with_google(self, client: AsyncClient):
        """User registers with email, then logs in via Google with same email."""
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "guser@gmail.com",
                "password": "SecurePass1",
                "full_name": "Email User",
            },
        )
        assert reg_resp.status_code == 201
        email_user_id = reg_resp.json()["data"]["user"]["id"]

        google_resp = await client.post(
            "/api/v1/auth/google", json={"id_token": "fake-google-token"}
        )
        assert google_resp.status_code == 200
        google_user_id = google_resp.json()["data"]["user"]["id"]

        assert email_user_id == google_user_id

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("mock_google_verify", "mock_apple_verify")
    async def test_google_user_can_login_with_apple_same_email(self, client: AsyncClient):
        """User signs up with Google, then tries Apple with the same email."""
        mock_apple_same_email = AsyncMock(
            return_value=OAuthUser(
                email="guser@gmail.com",
                name="Same Person",
                provider_id="apple-sub-99999",
            )
        )

        google_resp = await client.post(
            "/api/v1/auth/google", json={"id_token": "fake-google-token"}
        )
        google_user_id = google_resp.json()["data"]["user"]["id"]

        with patch(
            "app.routers.auth.verify_apple_token",
            mock_apple_same_email,
        ):
            apple_resp = await client.post(
                "/api/v1/auth/apple", json={"id_token": "fake-apple-token"}
            )
            assert apple_resp.status_code == 200
            apple_user_id = apple_resp.json()["data"]["user"]["id"]

        assert google_user_id == apple_user_id
