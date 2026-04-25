#!/usr/bin/env python3
"""Shim for the repo-root medallion check_imports script.

Track D lifted this to scripts/medallion/check_imports.py at the repo
root. This shim forwards to the new location for compatibility.

Prefer calling the root version in CI and new runbooks:
    python scripts/medallion/check_imports.py --app-dir apis/axiomfolio
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ROOT_SCRIPT = REPO_ROOT / "scripts" / "medallion" / "check_imports.py"


def main() -> int:
    if not ROOT_SCRIPT.is_file():
        print(f"error: {ROOT_SCRIPT} missing", file=sys.stderr)
        return 2
    extra = sys.argv[1:]
    args = [sys.executable, str(ROOT_SCRIPT), "--app-dir", "apis/axiomfolio", *extra]
    os.execv(sys.executable, args)


if __name__ == "__main__":
    sys.exit(main())
