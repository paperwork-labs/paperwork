"""Compose the hourly blitz progress summary and post it as a Brain Conversation (WS-69 PR J).

medallion: ops
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

_QUEUE_REL = Path("apis/brain/data/merge_queue.json")
_PROCEDURAL_MEMORY_REL = Path("apis/brain/data/procedural_memory.yaml")
_WORKSTREAMS_REL = Path("apps/studio/src/data/workstreams.json")
_PR_NUMBER_RE = re.compile(r"(?:#|pull request #)(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class MergedPr:
    number: int | None
    merged_at: datetime
    subject: str
    state: str
    url: str | None


@dataclass(frozen=True)
class BlitzStatusSnapshot:
    queue_depth: int
    current: dict[str, Any] | None
    last_complete: dict[str, Any] | None
    hourly_summary: str


def repo_root() -> Path:
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / _WORKSTREAMS_REL).exists() or (parent / _QUEUE_REL).exists():
            return parent
    return Path("/app")


def parse_rfc3339(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def queue_status(
    root: Path | None = None,
) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None]:
    base = root or repo_root()
    data = _read_json_object(base / _QUEUE_REL)
    queue = data.get("queue", [])
    history = data.get("history", [])
    if not isinstance(queue, list):
        queue = []
    if not isinstance(history, list):
        history = []
    current = data.get("current") if isinstance(data.get("current"), dict) else None
    last_complete = history[-1] if history and isinstance(history[-1], dict) else None
    return len(queue), current, last_complete


def _run_command(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _pr_state(number: int, root: Path) -> tuple[str, str | None]:
    raw = _run_command(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--json",
            "state,url",
            "--jq",
            "[.state,.url] | @tsv",
        ],
        root,
    ).strip()
    if not raw:
        return "unknown", None
    parts = raw.split("\t", 1)
    state = parts[0] if parts and parts[0] else "unknown"
    url = parts[1] if len(parts) > 1 and parts[1] else None
    return state, url


def merged_prs_last_hour(root: Path, since: datetime) -> list[MergedPr]:
    since_arg = since.astimezone(UTC).isoformat()
    output = _run_command(["git", "log", f"--since={since_arg}", "--format=%cI%x09%s"], root)
    prs: list[MergedPr] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        timestamp, _, subject = line.partition("\t")
        merged_at = parse_rfc3339(timestamp)
        if merged_at is None:
            continue
        match = _PR_NUMBER_RE.search(subject)
        number = int(match.group(1)) if match else None
        state = "unknown"
        url = None
        if number is not None:
            state, url = _pr_state(number, root)
        prs.append(
            MergedPr(number=number, merged_at=merged_at, subject=subject, state=state, url=url)
        )
    return prs


def workstream_changes_last_hour(root: Path, since: datetime) -> list[dict[str, Any]]:
    data = _read_json_object(root / _WORKSTREAMS_REL)
    workstreams = data.get("workstreams", [])
    if not isinstance(workstreams, list):
        return []
    changes: list[dict[str, Any]] = []
    for item in workstreams:
        if not isinstance(item, dict):
            continue
        changed_at = (
            parse_rfc3339(item.get("last_activity"))
            or parse_rfc3339(item.get("updated_at"))
            or parse_rfc3339(item.get("last_dispatched_at"))
        )
        if changed_at is None or changed_at < since:
            continue
        changes.append(item)
    return changes


def procedural_rules_last_hour(
    root: Path,
    since: datetime,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    path = root / _PROCEDURAL_MEMORY_REL
    if not path.exists():
        return []
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return []
    rules = loaded.get("rules", [])
    if not isinstance(rules, list):
        return []
    learned: list[dict[str, Any]] = []
    for item in rules:
        if not isinstance(item, dict):
            continue
        learned_at = parse_rfc3339(item.get("learned_at"))
        if learned_at is None or learned_at < since:
            continue
        learned.append(item)
    learned.sort(key=lambda r: str(r.get("learned_at", "")), reverse=True)
    return learned[:limit]


def compose_hourly_progress_summary(
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> str:
    base = root or repo_root()
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    since = current_time - timedelta(minutes=60)
    queue_depth, current, last_complete = queue_status(base)
    prs = merged_prs_last_hour(base, since)
    workstreams = workstream_changes_last_hour(base, since)
    rules = procedural_rules_last_hour(base, since)

    lines = [
        "# Blitz Hourly Progress",
        "",
        f"Window: {since.strftime('%Y-%m-%dT%H:%M:%SZ')} to "
        f"{current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## PRs Merged Last 60 Minutes",
    ]
    if prs:
        for pr in prs:
            pr_label = f"PR #{pr.number}" if pr.number is not None else "Unnumbered merge"
            target = f" ({pr.url})" if pr.url else ""
            lines.append(f"- {pr_label}: {pr.subject} - state={pr.state}{target}")
    else:
        lines.append("- No PR merges found in git log for this window.")

    lines.extend(["", "## Workstream Status Changes"])
    if workstreams:
        for ws in workstreams:
            lines.append(
                f"- {ws.get('id', 'unknown')}: status={ws.get('status', 'unknown')}, "
                f"percent_done={ws.get('percent_done', 'unknown')}, "
                f"last_activity={ws.get('last_activity') or ws.get('updated_at') or 'unknown'}"
            )
    else:
        lines.append("- No workstream status changes found in this window.")

    lines.extend(["", "## Rebase Queue", f"- Queue depth: {queue_depth}"])
    if current:
        lines.append(f"- Current: PR #{current.get('pr')} on {current.get('branch')}")
    else:
        lines.append("- Current: none")
    if last_complete:
        pr_number = last_complete.get("pr")
        complete_status = last_complete.get("status")
        lines.append(f"- Last complete: PR #{pr_number} ({complete_status})")

    lines.extend(["", "## Procedural Memory Learned"])
    if rules:
        for rule in rules:
            lines.append(f"- {rule.get('id', 'unknown')}: {rule.get('do', 'no action recorded')}")
    else:
        lines.append("- No new procedural-memory rules learned in this window.")
    return "\n".join(lines)


def blitz_status_snapshot(root: Path | None = None) -> BlitzStatusSnapshot:
    base = root or repo_root()
    queue_depth, current, last_complete = queue_status(base)
    return BlitzStatusSnapshot(
        queue_depth=queue_depth,
        current=current,
        last_complete=last_complete,
        hourly_summary=compose_hourly_progress_summary(root=base),
    )


async def post_blitz_progress(root: Path | None = None) -> dict[str, object]:
    """Compose hourly blitz progress and create a Brain Conversation."""
    from datetime import UTC, datetime

    from app.schemas.conversation import ConversationCreate
    from app.services.conversations import create_conversation

    summary = compose_hourly_progress_summary(root=root)
    date_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    conv = create_conversation(
        ConversationCreate(
            title=f"Blitz Progress — {date_str} UTC",
            body_md=summary,
            tags=["sprint-planning"],
            urgency="info",
            persona="ea",
            needs_founder_action=False,
        )
    )
    return {"ok": True, "conversation_id": conv.id}
