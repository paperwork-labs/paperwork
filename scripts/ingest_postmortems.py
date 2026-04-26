#!/usr/bin/env python3
"""Trigger Brain's postmortem + runbook-incident ingestion.

POSTs ``/admin/ingest-postmortems``. Requires ``BRAIN_API_SECRET``."""

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
    )
    parser.add_argument("--secret", default=os.environ.get("BRAIN_API_SECRET"))
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--check", action="store_true", help="Verify secret only")
    args = parser.parse_args()

    if args.check:
        if not args.secret:
            print("error: BRAIN_API_SECRET not set", file=sys.stderr)
            return 2
        print("ok: BRAIN_API_SECRET is set")
        return 0
    if not args.secret:
        print("error: BRAIN_API_SECRET not provided", file=sys.stderr)
        return 2

    url = args.brain_url.rstrip("/") + "/admin/ingest-postmortems"
    payload: dict = {"dry_run": args.dry_run}
    if args.limit is not None:
        payload["limit"] = args.limit
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        method="POST",
        data=data,
        headers={"X-Brain-Secret": args.secret, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"error: brain returned HTTP {e.code}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"error: {e.reason}", file=sys.stderr)
        return 1
    try:
        print(json.dumps(json.loads(body), indent=2))
    except json.JSONDecodeError:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
