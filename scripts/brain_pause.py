#!/usr/bin/env python3
"""Pause or resume Brain APScheduler jobs via ``apis/brain/data/brain_paused.flag``.

When the flag file is **empty** or **missing**, schedulers run normally.
When **non-empty**, schedulers wrapped with ``skip_if_brain_paused`` no-op.

Usage::

    uv run python scripts/brain_pause.py --reason "maintenance window"
    uv run python scripts/brain_pause.py --resume

Environment:

    ``BRAIN_PAUSED_FLAG_PATH`` — optional absolute path to the flag file (tests / custom deploys).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


def _default_flag_path() -> Path:
    override = (os.environ.get("BRAIN_PAUSED_FLAG_PATH") or "").strip()
    if override:
        return Path(override)
    repo = Path(__file__).resolve().parent.parent
    return repo / "apis" / "brain" / "data" / "brain_paused.flag"


def _print_status(path: Path) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        print("status: active (flag missing or unreadable)")
        return
    if not raw.strip():
        print("status: active (flag empty)")
        print(f"path: {path}")
        return
    first = raw.splitlines()[0] if raw.splitlines() else ""
    print("status: paused")
    print(f"path: {path}")
    print(f"first_line: {first}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reason",
        default="",
        help="Reason text written with UTC timestamp when pausing (required unless --resume).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Clear the flag file (Brain schedulers active).",
    )
    args = parser.parse_args()

    path = _default_flag_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if args.resume:
        path.write_text("", encoding="utf-8")
        print("brain: resumed (flag cleared)")
        _print_status(path)
        return 0

    reason = (args.reason or "").strip()
    if not reason:
        print("error: --reason is required to pause (or pass --resume)", file=sys.stderr)
        return 2

    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(f"{stamp} {reason}\n", encoding="utf-8")
    print("brain: paused")
    _print_status(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
