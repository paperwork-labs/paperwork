#!/usr/bin/env python3
"""Trigger Brain's sprint-lessons ingestion endpoint.

Walks the deployed Brain's view of `docs/sprints/*.md`, pulls every
``## What we learned`` bullet, and stores it as a memory episode
(``source = "sprint:lessons"``). Idempotent — re-runs only insert
new bullets.

Why a wrapper script instead of just `curl`:
  • Works from CI with one env var (``BRAIN_API_SECRET``) and
    sensible defaults.
  • Prints a structured JSON summary so a Slack notifier can react
    to ``created > 0`` without parsing freeform output.
  • Maps non-2xx responses to a non-zero exit so the GH workflow
    fails loudly when the secret is misconfigured.

Usage (local):

    BRAIN_API_SECRET=$(op read op://...) \
        python scripts/ingest_sprint_lessons.py

Usage (CI — see .github/workflows/sprint-lessons-ingest.yaml):

    env:
      BRAIN_API_SECRET: ${{ secrets.BRAIN_API_SECRET }}
    run: python scripts/ingest_sprint_lessons.py
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
        default=60,
        help="Request timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args()

    if not args.secret:
        print(
            "error: BRAIN_API_SECRET not provided (env var or --secret)",
            file=sys.stderr,
        )
        return 2

    url = args.brain_url.rstrip("/") + "/admin/seed-lessons"
    req = urllib.request.Request(
        url,
        method="POST",
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
        payload = json.loads(body)
    except json.JSONDecodeError:
        print(body)
        return 0

    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, dict):
        data = payload  # type: ignore[assignment]

    created = data.get("created", 0)
    skipped = data.get("skipped", 0)
    scanned = data.get("sprints_scanned", 0)
    print(
        json.dumps(
            {
                "scanned": scanned,
                "created": created,
                "skipped": skipped,
                "url": url,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
