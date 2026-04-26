"""Manual / backfill runner for :mod:`app.schedulers.sprint_auto_logger`.

Usage (from ``apis/brain``):

    python -m app.cli.sprint_auto_logger_cli --since 2026-04-20

Requires ``GITHUB_TOKEN`` and database reachable if you want
``agent_scheduler_runs`` rows (same as the scheduled job).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_BRAIN_ROOT = Path(__file__).resolve().parents[2]
if str(_BRAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRAIN_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app.schedulers.sprint_auto_logger import run_sprint_auto_logger  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Run sprint auto-logger once (backfill / debug).")
    ap.add_argument(
        "--since",
        required=True,
        help="UTC start instant as YYYY-MM-DD (00:00 UTC) or full ISO-8601 datetime",
    )
    args = ap.parse_args()
    raw = args.since.strip()
    try:
        if "T" in raw:
            since = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            since = datetime.fromisoformat(raw + "T00:00:00+00:00")
    except ValueError:
        print("error: could not parse --since (use YYYY-MM-DD or ISO-8601)", file=sys.stderr)
        return 2
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    if not os.getenv("GITHUB_TOKEN", "").strip():
        print("error: GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    asyncio.run(run_sprint_auto_logger(since_override=since))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
