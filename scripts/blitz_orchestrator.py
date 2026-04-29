#!/usr/bin/env python3
"""Single-writer queue for the 48-hour cheap-agent blitz merge flow."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

QUEUE_ENV = "BLITZ_MERGE_QUEUE_PATH"
DEFAULT_HISTORY_LIMIT = 5


def utc_now_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_queue_path() -> Path:
    override = os.environ.get(QUEUE_ENV)
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "apis" / "brain" / "data" / "merge_queue.json"


def _empty_state() -> dict[str, Any]:
    return {"queue": [], "current": None, "history": [], "updated_at": utc_now_z()}


@contextmanager
def locked_state(path: Path) -> Iterator[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        yield state
        state["updated_at"] = utc_now_z()
        write_state(path, state)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    queue = raw.get("queue")
    history = raw.get("history", [])
    if not isinstance(queue, list):
        raise ValueError(f"{path} field 'queue' must be a list")
    if not isinstance(history, list):
        raise ValueError(f"{path} field 'history' must be a list")
    raw.setdefault("current", None)
    raw.setdefault("history", history)
    raw.setdefault("updated_at", None)
    return raw


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as tmp:
        json.dump(state, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def enqueue_entry(args: argparse.Namespace, *, path: Path | None = None) -> int:
    queue_path = path or default_queue_path()
    entry = {
        "pr": args.pr,
        "branch": args.branch,
        "agent_id": args.agent_id,
        "agent_model": args.agent_model,
        "subagent_type": args.subagent_type,
        "workstream_id": args.workstream_id,
        "status": "pending",
        "enqueued_at": utc_now_z(),
    }
    with locked_state(queue_path) as state:
        state["queue"].append(entry)
        depth = len(state["queue"])
    print(f"enqueued PR #{args.pr} on {args.branch}; queue_depth={depth}")
    return 0


def next_entry(_args: argparse.Namespace, *, path: Path | None = None) -> int:
    queue_path = path or default_queue_path()
    with locked_state(queue_path) as state:
        if state.get("current") is not None:
            print(
                "error: current merge is still active; complete it before taking next",
                file=sys.stderr,
            )
            return 1
        queue = state["queue"]
        if not queue:
            print("queue empty; no PR ready for merge")
            return 1
        entry = queue.pop(0)
        entry["status"] = "current"
        entry["started_at"] = utc_now_z()
        state["current"] = entry
        depth = len(queue)
    print(
        f"next PR #{entry['pr']} from {entry['branch']} "
        f"(agent={entry['agent_id']}, workstream={entry['workstream_id']}); queue_depth={depth}"
    )
    return 0


def status_queue(args: argparse.Namespace, *, path: Path | None = None) -> int:
    queue_path = path or default_queue_path()
    state = read_state(queue_path)
    print(f"queue_depth: {len(state['queue'])}")
    current = state.get("current")
    if current:
        print(f"current: PR #{current.get('pr')} {current.get('branch')} ({current.get('status')})")
    else:
        print("current: none")
    history = state.get("history", [])[-args.last :]
    print(f"last_completed_count: {len(history)}")
    for item in reversed(history):
        note = f" note={item.get('note')!r}" if item.get("note") else ""
        print(f"- PR #{item.get('pr')} {item.get('status')} at {item.get('completed_at')}{note}")
    return 0


def complete_entry(args: argparse.Namespace, *, path: Path | None = None) -> int:
    queue_path = path or default_queue_path()
    with locked_state(queue_path) as state:
        current = state.get("current")
        if not isinstance(current, dict):
            print("error: no current PR to complete", file=sys.stderr)
            return 1
        if current.get("pr") != args.pr:
            print(
                f"error: current PR is #{current.get('pr')}, not #{args.pr}; refusing to complete",
                file=sys.stderr,
            )
            return 1
        completed = {
            **current,
            "status": args.status,
            "note": args.note,
            "completed_at": utc_now_z(),
        }
        state["history"].append(completed)
        state["current"] = None
        depth = len(state["queue"])
    print(f"completed PR #{args.pr} as {args.status}; queue_depth={depth}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    enqueue = subparsers.add_parser("enqueue", help="Append a PR to the merge queue")
    enqueue.add_argument("--pr", type=int, required=True)
    enqueue.add_argument("--branch", required=True)
    enqueue.add_argument("--agent-id", required=True)
    enqueue.add_argument("--agent-model", required=True)
    enqueue.add_argument("--subagent-type", required=True)
    enqueue.add_argument("--workstream-id", required=True)
    enqueue.set_defaults(func=enqueue_entry)
    next_parser = subparsers.add_parser("next", help="Pop queue head into current")
    next_parser.set_defaults(func=next_entry)
    status = subparsers.add_parser("status", help="Show queue depth/current/history")
    status.add_argument("--last", type=int, default=DEFAULT_HISTORY_LIMIT)
    status.set_defaults(func=status_queue)
    complete = subparsers.add_parser("complete", help="Finalize current PR")
    complete.add_argument("--pr", type=int, required=True)
    complete.add_argument("--status", choices=("merged", "failed", "rejected"), required=True)
    complete.add_argument("--note", default="")
    complete.set_defaults(func=complete_entry)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    try:
        return func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
