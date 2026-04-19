"""Tests for Postmark picks inbound webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import backend.config as app_config
from backend.api.main import app
from backend.database import get_db
from backend.models.picks import EmailInbox
from backend.services.picks.postmark_signature import validate_postmark_signature

URL = "/api/v1/webhooks/picks/inbound"


def _sign_body(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def _minimal_payload(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "From": "Allowed User <allowed@example.com>",
        "To": "inbox <picks@inbound.postmarkapp.com>",
        "ToFull": [
            {"Email": "picks@inbound.postmarkapp.com", "Name": "inbox", "MailboxHash": ""}
        ],
        "Subject": "Weekly picks",
        "MessageID": "msg-test-001",
        "Date": "Sat, 18 Apr 2026 12:00:00 +0000",
        "TextBody": "Buy EXAMPLE",
        "HtmlBody": "<p>Buy EXAMPLE</p>",
        "Attachments": [],
    }
    base.update(overrides)
    return base


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def picks_webhook_secret(monkeypatch) -> str:
    secret = "unit-test-postmark-secret"
    monkeypatch.setattr(app_config.settings, "POSTMARK_INBOUND_SECRET", secret)
    monkeypatch.setattr(app_config.settings, "PICKS_INBOUND_REQUIRE_SIGNATURE", True)
    return secret


@pytest.fixture
def picks_allowlist(monkeypatch) -> None:
    monkeypatch.setattr(
        app_config.settings,
        "PICKS_INBOUND_ALLOWLIST",
        ["allowed@example.com"],
    )


@pytest.fixture(autouse=True)
def picks_parse_delay_stub(monkeypatch) -> MagicMock:
    """Avoid contacting the real Celery broker during webhook tests."""
    m = MagicMock()
    monkeypatch.setattr(
        "backend.api.routes.webhooks.picks.parse_inbound_email.delay",
        m,
    )
    return m


def test_validate_postmark_signature_base64_and_hex():
    body = b'{"MessageID":"x"}'
    secret = "k"
    b64 = _sign_body(body, secret)
    assert validate_postmark_signature(body, b64, secret) is True
    hx = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert validate_postmark_signature(body, hx, secret) is True
    assert validate_postmark_signature(body, "nope", secret) is False


def test_signature_required_when_enabled(client, picks_webhook_secret, picks_allowlist):
    payload = _minimal_payload(MessageID="msg-sig-req-1")
    body = json.dumps(payload).encode("utf-8")
    r = client.post(URL, data=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 403

    bad = client.post(
        URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Postmark-Signature": "not-a-valid-signature",
        },
    )
    assert bad.status_code == 403


def test_signature_skipped_in_dev(client, monkeypatch, picks_allowlist):
    monkeypatch.setattr(app_config.settings, "PICKS_INBOUND_REQUIRE_SIGNATURE", False)
    monkeypatch.setattr(app_config.settings, "POSTMARK_INBOUND_SECRET", None)
    payload = _minimal_payload(MessageID="msg-skip-sig-1")
    body = json.dumps(payload).encode("utf-8")
    r = client.post(URL, data=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json().get("status") == "queued"


def test_allowlist_blocks_unknown_sender(
    client, db_session, picks_webhook_secret, monkeypatch
):
    monkeypatch.setattr(
        app_config.settings,
        "PICKS_INBOUND_ALLOWLIST",
        ["someone_else@example.com"],
    )
    payload = _minimal_payload(MessageID="msg-unknown-sender")
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_body(body, picks_webhook_secret)
    r = client.post(
        URL,
        data=body,
        headers={"Content-Type": "application/json", "X-Postmark-Signature": sig},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "ignored"
    n = db_session.query(EmailInbox).filter(EmailInbox.message_id == "msg-unknown-sender").count()
    assert n == 0


def test_allowlist_allows_known_sender(client, db_session, picks_webhook_secret, picks_allowlist):
    payload = _minimal_payload(MessageID="msg-allow-001")
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_body(body, picks_webhook_secret)
    r = client.post(
        URL,
        data=body,
        headers={"Content-Type": "application/json", "X-Postmark-Signature": sig},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "queued"
    row = db_session.query(EmailInbox).filter(EmailInbox.message_id == "msg-allow-001").one()
    assert row.ingestion_status == "RECEIVED"
    assert row.sender == "allowed@example.com"
    assert row.raw_payload is not None
    assert row.raw_payload.get("MessageID") == "msg-allow-001"
    assert "Attachments" not in row.raw_payload


def test_idempotent_on_duplicate_message_id(
    client, db_session, picks_webhook_secret, picks_allowlist, picks_parse_delay_stub
):
    payload = _minimal_payload(MessageID="msg-dup-001")
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_body(body, picks_webhook_secret)
    h = {"Content-Type": "application/json", "X-Postmark-Signature": sig}
    j1 = client.post(URL, data=body, headers=h).json()
    assert j1["status"] == "queued"
    inbox_id = j1["inbox_id"]
    j2 = client.post(URL, data=body, headers=h).json()
    assert j2 == {"status": "duplicate", "inbox_id": inbox_id}
    assert db_session.query(EmailInbox).filter(EmailInbox.message_id == "msg-dup-001").count() == 1
    assert picks_parse_delay_stub.call_count == 1


def test_dispatches_parse_task(
    client, picks_webhook_secret, picks_allowlist, picks_parse_delay_stub
):
    payload = _minimal_payload(MessageID="msg-dispatch-001")
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_body(body, picks_webhook_secret)
    r = client.post(
        URL,
        data=body,
        headers={"Content-Type": "application/json", "X-Postmark-Signature": sig},
    )
    assert r.status_code == 200
    inbox_id = r.json()["inbox_id"]
    picks_parse_delay_stub.assert_called_once_with(inbox_id)
