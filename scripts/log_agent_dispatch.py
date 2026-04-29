#!/usr/bin/env python3
"""Append a cheap-agent dispatch entry to Brain's blitz dispatch log."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG_ENV = "BLITZ_AGENT_DISPATCH_LOG_PATH"


def utc_now_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_log_path() -> Path:
    override = os.environ.get(LOG_ENV)
    if override:
        return Path(override)
    return (
        Path(__file__).resolve().parent.parent
        / "apis"
        / "brain"
        / "data"
        / "agent_dispatch_log.json"
    )


def empty_log() -> dict[str, Any]:
    return {"dispatches": [], "updated_at": utc_now_z()}


def read_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_log()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    dispatches = raw.get("dispatches")
    if not isinstance(dispatches, list):
        raise ValueError(f"{path} field 'dispatches' must be a list")
    raw.setdefault("updated_at", None)
    return raw


def write_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


@contextmanager
def locked_log(path: Path) -> Iterator[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        payload = read_log(path)
        yield payload
        payload["updated_at"] = utc_now_z()
        write_log(path, payload)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def build_entry(args: argparse.Namespace) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "dispatch_id": args.dispatch_id or str(uuid.uuid4()),
        "agent_id": args.agent_id,
        "agent_model": args.agent_model,
        "subagent_type": args.subagent_type,
        "workstream_id": args.workstream_id,
        "dispatched_at": utc_now_z(),
        "status": args.status,
    }
    optional_fields = {
        "branch": args.branch,
        "pr": args.pr,
        "task": args.task,
        "success_metric": args.success_metric,
        "note": args.note,
    }
    for key, value in optional_fields.items():
        if value not in (None, ""):
            entry[key] = value
    return entry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch-id", default="")
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--agent-model", required=True)
    parser.add_argument("--subagent-type", required=True)
    parser.add_argument("--workstream-id", required=True)
    parser.add_argument("--branch", default="")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--task", default="")
    parser.add_argument("--success-metric", default="")
    parser.add_argument("--status", default="dispatched")
    parser.add_argument("--note", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path = default_log_path()
    try:
        entry = build_entry(args)
        with locked_log(path) as payload:
            payload["dispatches"].append(entry)
            count = len(payload["dispatches"])
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"logged dispatch {entry['dispatch_id']} for {entry['workstream_id']}; "
        f"dispatch_count={count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
