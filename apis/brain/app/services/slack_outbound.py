"""Slack outbound (Brain → channels).

Minimal surface for posting a message to a channel. Used by:
- Track B: PR review summaries to #engineering after Brain reviews a PR.
- Track C (later): persona-specific proactive posts.

Keeping this tiny on purpose — the full persona-tone/bot-identity layer lands in
Track C. Right now we just need an async "post this text to this channel" that
degrades gracefully when the token is missing.

medallion: ops
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

_SLACK_BASE = "https://slack.com/api"


async def post_message(
    *,
    channel: str | None = None,
    channel_id: str | None = None,
    text: str,
    blocks: list[dict[str, Any]] | None = None,
    thread_ts: str | None = None,
    unfurl_links: bool = False,
    username: str | None = None,
    icon_emoji: str | None = None,
) -> dict[str, Any]:
    """Post to Slack. Returns ``{ok, ts?, error?}``.

    Accepts either ``channel`` or ``channel_id`` (alias) so callers from
    different tracks can use the name that reads naturally at the call
    site. ``username`` / ``icon_emoji`` are optional per-post overrides
    (Track H — per-persona Slack identity).

    Never raises — failures are logged and surfaced via the return dict so
    webhook/scheduler callers can carry on.
    """
    channel_value = channel or channel_id
    token = (settings.SLACK_BOT_TOKEN or "").strip()
    if not token:
        logger.info(
            "slack_outbound: SLACK_BOT_TOKEN unset, skipping post to %s",
            channel_value,
        )
        return {"ok": False, "error": "SLACK_BOT_TOKEN not configured"}

    if not channel_value or not str(channel_value).strip():
        return {"ok": False, "error": "channel is empty"}

    payload: dict[str, Any] = {
        "channel": channel_value,
        "text": text[:40000],
        "unfurl_links": unfurl_links,
        "unfurl_media": unfurl_links,
    }
    if blocks:
        payload["blocks"] = blocks[:50]
    if thread_ts:
        payload["thread_ts"] = thread_ts
    if username:
        payload["username"] = username
    if icon_emoji:
        payload["icon_emoji"] = icon_emoji

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{_SLACK_BASE}/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=payload,
            )
            data = (
                r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            )
    except httpx.HTTPError as e:
        logger.warning("slack_outbound: post failed (%s): %s", channel, e)
        return {"ok": False, "error": f"http error: {e}"}

    if not data.get("ok"):
        logger.warning("slack_outbound: slack rejected post to %s: %s", channel, data)
        return {"ok": False, "error": str(data.get("error") or "unknown")}

    return {"ok": True, "ts": data.get("ts"), "channel": data.get("channel")}
