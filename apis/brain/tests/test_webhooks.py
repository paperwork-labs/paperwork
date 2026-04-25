"""Tests for AxiomFolio webhook HMAC-SHA256 verification."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest


class TestAxiomFolioWebhookAuth:
    """Test HMAC-SHA256 signature verification for AxiomFolio webhooks."""

    @pytest.fixture
    def webhook_payload(self) -> dict:
        return {
            "event": "trade.executed",
            "data": {"symbol": "AAPL", "side": "buy", "quantity": 100},
            "timestamp": "2026-03-30T12:00:00Z",
        }

    @pytest.fixture
    def webhook_secret(self) -> str:
        return "test_webhook_secret_123"

    def _serialize_and_sign(self, payload: dict, secret: str) -> tuple[bytes, str]:
        """Serialize payload and compute HMAC-SHA256 signature.

        Returns (body_bytes, signature_header) to ensure the signature is
        computed over the exact bytes that will be sent.
        """
        body_bytes = json.dumps(payload, separators=(",", ":")).encode()
        sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        return body_bytes, f"sha256={sig}"

    @pytest.mark.asyncio
    async def test_valid_signature_accepted(
        self, client, webhook_payload, webhook_secret
    ):
        """Webhook with valid HMAC signature should be accepted."""
        body_bytes, signature = self._serialize_and_sign(webhook_payload, webhook_secret)

        with patch("app.config.settings.AXIOMFOLIO_WEBHOOK_SECRET", webhook_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                response = await client.post(
                    "/api/v1/webhooks/axiomfolio",
                    content=body_bytes,
                    headers={
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json",
                    },
                )

        assert response.status_code == 200
        assert response.json() == {"success": True}

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self, client, webhook_payload, webhook_secret):
        """Webhook without signature header should return 401."""
        with patch("app.config.settings.AXIOMFOLIO_WEBHOOK_SECRET", webhook_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                response = await client.post(
                    "/api/v1/webhooks/axiomfolio",
                    json=webhook_payload,
                )

        assert response.status_code == 401
        assert "Missing or malformed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_malformed_signature_rejected(
        self, client, webhook_payload, webhook_secret
    ):
        """Webhook with malformed signature (no sha256= prefix) should return 401."""
        with patch("app.config.settings.AXIOMFOLIO_WEBHOOK_SECRET", webhook_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                response = await client.post(
                    "/api/v1/webhooks/axiomfolio",
                    json=webhook_payload,
                    headers={"X-Webhook-Signature": "invalid_format"},
                )

        assert response.status_code == 401
        assert "Missing or malformed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(
        self, client, webhook_payload, webhook_secret
    ):
        """Webhook with wrong signature should return 401."""
        wrong_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

        with patch("app.config.settings.AXIOMFOLIO_WEBHOOK_SECRET", webhook_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                response = await client.post(
                    "/api/v1/webhooks/axiomfolio",
                    json=webhook_payload,
                    headers={"X-Webhook-Signature": wrong_signature},
                )

        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_dev_mode_bypass_without_secret(self, client, webhook_payload):
        """In development mode with no secret configured, webhooks are accepted."""
        with patch("app.config.settings.AXIOMFOLIO_WEBHOOK_SECRET", ""):
            with patch("app.config.settings.ENVIRONMENT", "development"):
                response = await client.post(
                    "/api/v1/webhooks/axiomfolio",
                    json=webhook_payload,
                )

        assert response.status_code == 200
        assert response.json() == {"success": True}

    @pytest.mark.asyncio
    async def test_production_requires_secret(self, client, webhook_payload):
        """In production mode with no secret configured, return 503."""
        with patch("app.config.settings.AXIOMFOLIO_WEBHOOK_SECRET", ""):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                response = await client.post(
                    "/api/v1/webhooks/axiomfolio",
                    json=webhook_payload,
                )

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


class TestGitHubWebhookAuth:
    """HMAC-SHA256 (X-Hub-Signature-256) verification on /webhooks/github."""

    @pytest.fixture
    def github_payload(self) -> dict:
        return {
            "action": "opened",
            "number": 999,
            "pull_request": {
                "number": 999,
                "draft": False,
                "title": "chore(deps): bump lodash from 4.17.20 to 4.17.21",
                "user": {"login": "dependabot[bot]"},
                "labels": [],
            },
        }

    @pytest.fixture
    def github_secret(self) -> str:
        return "gh_webhook_secret_xyz"

    def _sign(self, payload: dict, secret: str) -> tuple[bytes, str]:
        body = json.dumps(payload, separators=(",", ":")).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return body, f"sha256={sig}"

    @pytest.mark.asyncio
    async def test_ping_event_short_circuits(self, client, github_secret):
        body, sig = self._sign({}, github_secret)
        with patch("app.config.settings.GITHUB_WEBHOOK_SECRET", github_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                res = await client.post(
                    "/api/v1/webhooks/github",
                    content=body,
                    headers={
                        "X-Hub-Signature-256": sig,
                        "X-GitHub-Event": "ping",
                        "X-GitHub-Delivery": "abc-123",
                        "Content-Type": "application/json",
                    },
                )
        assert res.status_code == 200
        assert res.json() == {"received": True, "ping": True}

    @pytest.mark.asyncio
    async def test_unknown_event_acknowledged_but_ignored(self, client, github_secret):
        body, sig = self._sign({}, github_secret)
        with patch("app.config.settings.GITHUB_WEBHOOK_SECRET", github_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                res = await client.post(
                    "/api/v1/webhooks/github",
                    content=body,
                    headers={
                        "X-Hub-Signature-256": sig,
                        "X-GitHub-Event": "push",
                        "X-GitHub-Delivery": "abc-456",
                        "Content-Type": "application/json",
                    },
                )
        assert res.status_code == 200
        assert res.json()["ignored"] == "push"

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self, client, github_payload, github_secret):
        with patch("app.config.settings.GITHUB_WEBHOOK_SECRET", github_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                res = await client.post(
                    "/api/v1/webhooks/github",
                    json=github_payload,
                    headers={
                        "X-Hub-Signature-256": "sha256=0" * 64,
                        "X-GitHub-Event": "pull_request",
                    },
                )
        # Either invalid or malformed depending on length — both 401.
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self, client, github_payload, github_secret):
        with patch("app.config.settings.GITHUB_WEBHOOK_SECRET", github_secret):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                res = await client.post(
                    "/api/v1/webhooks/github",
                    json=github_payload,
                    headers={"X-GitHub-Event": "pull_request"},
                )
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_production_requires_secret(self, client, github_payload):
        with patch("app.config.settings.GITHUB_WEBHOOK_SECRET", ""):
            with patch("app.config.settings.ENVIRONMENT", "production"):
                res = await client.post(
                    "/api/v1/webhooks/github",
                    json=github_payload,
                    headers={"X-GitHub-Event": "pull_request"},
                )
        assert res.status_code == 503
