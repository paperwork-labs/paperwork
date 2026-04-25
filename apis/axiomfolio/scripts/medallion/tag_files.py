#!/usr/bin/env python3
"""Shim for the repo-root medallion tag_files script.

Track D of the Infra & Automation Hardening Sprint lifted this script to
scripts/medallion/tag_files.py at the repo root so every backend shares
one implementation. This shim keeps existing runbooks working by
forwarding to the new location with --app-dir=apis/axiomfolio.

Prefer calling the root version directly in new code:
    python scripts/medallion/tag_files.py --app-dir apis/axiomfolio --apply
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ROOT_SCRIPT = REPO_ROOT / "scripts" / "medallion" / "tag_files.py"


def main() -> int:
    if not ROOT_SCRIPT.is_file():
        print(f"error: {ROOT_SCRIPT} missing", file=sys.stderr)
        return 2
    extra = sys.argv[1:]
    args = [sys.executable, str(ROOT_SCRIPT), "--app-dir", "apis/axiomfolio", *extra]
    os.execv(sys.executable, args)


if __name__ == "__main__":
    sys.exit(main())
