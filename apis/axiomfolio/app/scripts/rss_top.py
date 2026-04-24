"""
CLI: print hottest API endpoints by per-request peak RSS delta (read from Redis).

Usage::

    python -m app.scripts.rss_top --hours 6 --top 15

Environment: ``REDIS_URL`` must be set (same as the API process).
"""

from __future__ import annotations

import argparse
import os
import sys

import redis


def main() -> int:
    p = argparse.ArgumentParser(description="Top endpoints by peak RSS (Redis observability).")
    p.add_argument("--hours", type=int, default=6, help="Number of past UTC hours to include.")
    p.add_argument("--top", type=int, default=15, help="Number of rows (default 15).")
    args = p.parse_args()

    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        print("REDIS_URL is not set", file=sys.stderr)
        return 1

    from app.services.observability.rss_store import get_rss_cli_table

    r = redis.from_url(url)
    print(get_rss_cli_table(r, hours=args.hours, top_n=args.top), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
