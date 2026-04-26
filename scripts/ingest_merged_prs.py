#!/usr/bin/env python3
"""Trigger Brain's merged-PR continuous-learning ingestion (GitHub API in-process).

POSTs ``/admin/ingest-merged-prs`` with optional ``dry_run`` and ``limit``.
Requires ``BRAIN_API_SECRET`` (or ``--secret``).

Local verify:

    BRAIN_API_SECRET=$(op read op://...) \\
        python3 scripts/ingest_merged_prs.py --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BRAIN_URL = "https://brain.paperworklabs.com"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brain-url",
        default=os.environ.get("BRAIN_URL", DEFAULT_BRAIN_URL),
        help="Brain base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--secret",
        default=os.environ.get("BRAIN_API_SECRET"),
        help="Admin secret. Defaults to $BRAIN_API_SECRET.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Request timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ask Brain to report what would be ingested without writing episodes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max new PRs to process this run (server default: 50)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 if secret is set, 2 if missing; no HTTP call",
    )
    args = parser.parse_args()

    if args.check:
        if not args.secret:
            print("error: BRAIN_API_SECRET not set", file=sys.stderr)
            return 2
        print("ok: BRAIN_API_SECRET is set")
        return 0

    if not args.secret:
        print(
            "error: BRAIN_API_SECRET not provided (env var or --secret)",
            file=sys.stderr,
        )
        return 2

    url = args.brain_url.rstrip("/") + "/admin/ingest-merged-prs"
    payload: dict = {"dry_run": args.dry_run}
    if args.limit is not None:
        payload["limit"] = args.limit
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=data,
        headers={
            "X-Brain-Secret": args.secret,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"error: brain returned HTTP {e.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"error: could not reach {url}: {e.reason}", file=sys.stderr)
        return 1

    try:
        print(json.dumps(json.loads(body), indent=2))
    except json.JSONDecodeError:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
