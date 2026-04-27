"""Unit tests for slack_outbound — the shared Slack poster used by
pr_review (Track B), proactive_cadence (Track C), and agent.process
(Track H two-node pattern).

These tests focus on the *contract* other code in Brain depends on:
- ``channel`` and ``channel_id`` must both be accepted as aliases.
- Missing token is a soft failure, not a raise.
- Optional ``username`` and ``icon_emoji`` are forwarded to Slack's
  ``chat.postMessage`` payload so n8n can set per-persona identity
  without touching Brain's persona registry.

medallion: ops
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

import pytest

from app.services import slack_outbound


@pytest.mark.asyncio
async def test_post_message_no_token_returns_error(monkeypatch):
    """Soft-fail when SLACK_BOT_TOKEN is unset (local dev / misconfig)."""
    monkeypatch.setattr(slack_outbound.settings, "SLACK_BOT_TOKEN", "")
    result = await slack_outbound.post_message(channel="C123", text="hi")
    assert result["ok"] is False
    assert "SLACK_BOT_TOKEN" in result["error"]


@pytest.mark.asyncio
async def test_post_message_empty_channel_returns_error(monkeypatch):
    monkeypatch.setattr(slack_outbound.settings, "SLACK_BOT_TOKEN", "xoxb-test")
    result = await slack_outbound.post_message(channel="", text="hi")
    assert result["ok"] is False
    assert "channel is empty" in result["error"]


@pytest.mark.asyncio
async def test_post_message_channel_id_alias_works(monkeypatch):
    """Track H passes ``channel_id`` — must map to Slack's ``channel`` field."""
    monkeypatch.setattr(slack_outbound.settings, "SLACK_BOT_TOKEN", "xoxb-test")

    captured: dict = {}

    class _MockResponse:
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        def json(self) -> dict:
            return {"ok": True, "ts": "1700000000.000001", "channel": "C999"}

    class _MockClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url: str, headers=None, json=None):  # noqa: ARG002
            captured["url"] = url
            captured["json"] = json
            return _MockResponse()

    with patch.object(slack_outbound, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = _MockClient
        mock_httpx.HTTPError = Exception
        result = await slack_outbound.post_message(
            channel_id="C999",
            text="persona speaking",
            username="CPA Advisor",
            icon_emoji=":nerd_face:",
        )

    assert result["ok"] is True
    assert captured["json"]["channel"] == "C999"
    assert captured["json"]["username"] == "CPA Advisor"
    assert captured["json"]["icon_emoji"] == ":nerd_face:"


@pytest.mark.asyncio
async def test_post_message_text_truncated_at_40k(monkeypatch):
    """Slack hard limit: we chop before calling, never mid-post."""
    monkeypatch.setattr(slack_outbound.settings, "SLACK_BOT_TOKEN", "xoxb-test")
    captured: dict = {}

    class _MockResponse:
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        def json(self) -> dict:
            return {"ok": True, "ts": "1.0"}

    class _MockClient:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, headers=None, json=None):  # noqa: ARG002
            captured["json"] = json
            return _MockResponse()

    big_text = "x" * 50000
    with patch.object(slack_outbound, "httpx") as mock_httpx:
        mock_httpx.AsyncClient = _MockClient
        mock_httpx.HTTPError = Exception
        await slack_outbound.post_message(channel="C1", text=big_text)

    assert len(captured["json"]["text"]) == 40000
