"""Slack mrkdwn formatting ported from retired n8n Code nodes (growth / social).

medallion: ops
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any


def sanitize_slack_mrkdwn(text: str) -> str:
    s = str(text or "")
    s = re.sub(r"```\w*\n?", "```", s)
    s = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", s, flags=re.MULTILINE)
    s = re.sub(r"^[-*_]{3,}\s*$", "", s, flags=re.MULTILINE)
    s = re.sub(r"\*\*(.+?)\*\*", r"*\1*", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


def format_structured_json_for_slack(
    raw_llm: str,
    *,
    header_prefix: str,
    footer: str = "_Thread router: reply with a persona name for a focused take._",
) -> str:
    """Turn JSON object text into bullet Slack mrkdwn (matches n8n ``Format for Slack``)."""
    raw = (raw_llm or "").strip()
    date = datetime.now(UTC).date().isoformat()
    header = f"*{header_prefix} — {date}*"
    if not raw:
        return sanitize_slack_mrkdwn(
            f":warning: No output generated. Check workflow logs.\n\n{footer}"
        )
    try:
        obj: dict[str, Any] = json.loads(raw)
        parts: list[str] = []
        for k, v in obj.items():
            label = k.replace("_", " ").title()
            if isinstance(v, list):
                lines = "\n".join(
                    f"  - {json.dumps(item) if isinstance(item, dict) else item}" for item in v
                )
                parts.append(f"• *{label}:*\n{lines}")
            elif isinstance(v, dict):
                parts.append(f"• *{label}:* {json.dumps(v)}")
            else:
                parts.append(f"• *{label}:* {v}")
        body = "\n".join(parts)
    except json.JSONDecodeError:
        body = raw
    return sanitize_slack_mrkdwn(f"{header}\n\n{body}\n\n{footer}")
