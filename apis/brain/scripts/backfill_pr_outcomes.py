"""Backfill merged PR outcomes from GitHub into ``apis/brain/data/pr_outcomes.json``.

Usage:
    cd apis/brain
    GITHUB_TOKEN=ghp_... python scripts/backfill_pr_outcomes.py
    GITHUB_TOKEN=ghp_... python scripts/backfill_pr_outcomes.py --days 60

The script reads merged PRs from the last N days (default: 60), calls Brain's
``record_merged_pr`` path for each PR, and overwrites matching ``pr_number``
metadata while preserving already-recorded horizon outcomes. It is safe to
re-run.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_BRAIN_ROOT = Path(__file__).resolve().parents[1]
if str(_BRAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRAIN_ROOT))

from app.schedulers.pr_outcome_recorder import run_backfill_cli  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Brain PR outcomes from GitHub")
    parser.add_argument("--days", type=int, default=60, help="Merged PR lookback window")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = run_backfill_cli(days=args.days)
    sys.stdout.write(f"backfill_pr_outcomes: recorded={report['recorded']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
