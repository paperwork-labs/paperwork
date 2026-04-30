"""Tests for web push service — WS-69 PR I.

Covers: subscribe, unsubscribe, 410-gone pruning, VapidConfigError on missing env vars.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import app.services.web_push as svc
from app.services.web_push import VapidConfigError


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    data_dir = tmp_path / "apis" / "brain" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# ---------------------------------------------------------------------------
# subscribe / unsubscribe
# ---------------------------------------------------------------------------


def test_subscribe_creates_entry(tmp_path: Path) -> None:
    svc.subscribe(
        user_id="founder",
        endpoint="https://push.example.com/sub/abc",
        p256dh="AAAA",
        auth="BBBB",
    )
    subs = svc._load_subscriptions()
    assert len(subs) == 1
    assert subs[0]["endpoint"] == "https://push.example.com/sub/abc"
    assert subs[0]["user_id"] == "founder"
    assert subs[0]["keys"]["p256dh"] == "AAAA"
    assert subs[0]["keys"]["auth"] == "BBBB"


def test_subscribe_upserts_existing_endpoint() -> None:
    svc.subscribe("founder", "https://push.example.com/sub/abc", "P1", "A1")
    svc.subscribe("founder", "https://push.example.com/sub/abc", "P2", "A2")
    subs = svc._load_subscriptions()
    assert len(subs) == 1
    assert subs[0]["keys"]["p256dh"] == "P2"


def test_unsubscribe_removes_entry() -> None:
    endpoint = "https://push.example.com/sub/remove"
    svc.subscribe("founder", endpoint, "P", "A")
    assert len(svc.list_subscriptions("founder")) == 1
    svc.unsubscribe(endpoint)
    assert svc.list_subscriptions("founder") == []


def test_unsubscribe_idempotent() -> None:
    svc.unsubscribe("https://push.example.com/never-existed")  # should not raise


def test_list_subscriptions_filters_by_user() -> None:
    svc.subscribe("founder", "https://push.example.com/1", "P1", "A1")
    svc.subscribe("other", "https://push.example.com/2", "P2", "A2")
    assert len(svc.list_subscriptions("founder")) == 1
    assert len(svc.list_subscriptions("other")) == 1
    assert len(svc.list_subscriptions("nobody")) == 0


# ---------------------------------------------------------------------------
# VAPID config
# ---------------------------------------------------------------------------


def test_get_vapid_public_key_raises_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VAPID_SUBJECT", raising=False)
    with pytest.raises(VapidConfigError, match="VAPID_PUBLIC_KEY"):
        svc.get_vapid_public_key()


def test_get_vapid_public_key_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-pub-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "test-priv-key")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")
    assert svc.get_vapid_public_key() == "test-pub-key"


# ---------------------------------------------------------------------------
# send_push — 410 pruning
# ---------------------------------------------------------------------------


def test_send_push_prunes_on_410(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")

    endpoint = "https://push.example.com/sub/gone"
    svc.subscribe("founder", endpoint, "P", "A")
    assert len(svc.list_subscriptions("founder")) == 1

    mock_response = MagicMock()
    mock_response.status_code = 410

    mock_pusher = MagicMock()
    mock_pusher.send.return_value = mock_response

    subscription = svc.list_subscriptions("founder")[0]
    with (
        patch("pywebpush.WebPusher", return_value=mock_pusher),
        contextlib.suppress(Exception),
    ):
        svc.send_push(subscription, {"title": "Test"})

    assert len(svc.list_subscriptions("founder")) == 0


def test_send_push_prunes_on_410_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")

    endpoint = "https://push.example.com/sub/gone2"
    svc.subscribe("founder", endpoint, "P", "A")
    assert len(svc.list_subscriptions("founder")) == 1

    subscription = svc.list_subscriptions("founder")[0]

    with patch("pywebpush.WebPusher") as mock_cls:
        from pywebpush import WebPushException

        mock_response = MagicMock()
        mock_response.status_code = 410
        exc = WebPushException("Gone", response=mock_response)
        mock_pusher = MagicMock()
        mock_pusher.send.side_effect = exc
        mock_cls.return_value = mock_pusher

        with pytest.raises(WebPushException):
            svc.send_push(subscription, {"title": "Test"})

    assert len(svc.list_subscriptions("founder")) == 0


# ---------------------------------------------------------------------------
# fan_out_push — no-op when no subscriptions
# ---------------------------------------------------------------------------


def test_fan_out_no_subscriptions_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")
    # Should complete without error
    svc.fan_out_push("founder", {"title": "Test"})


def test_fan_out_dead_letters_on_push_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@example.com")

    svc.subscribe("founder", "https://push.example.com/sub/fail", "P", "A")

    with patch("app.services.web_push.send_push", side_effect=RuntimeError("network error")):
        # fan_out should swallow the error — no exception propagated
        svc.fan_out_push("founder", {"title": "Test"})
