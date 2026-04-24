"""Static audit: BRAIN_TOOLS_USER_ID and ``user_id = 1`` may only appear in
allowlisted locations.

This is a guard against the D88 regression where a hardcoded
``BRAIN_TOOLS_USER_ID = 1`` snuck back into a route. We allowlist the
specific (file, line-content) pairs we KNOW are safe (config default,
the deprecated-fallback log line, the bootstrap admin seed).
"""

from __future__ import annotations

import os
import re

import pytest


pytestmark = pytest.mark.no_db


_BACKEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)


# Allowlisted occurrences (substring match on the line). Each entry
# documents WHY the occurrence is safe.
_ALLOWLIST: tuple[tuple[str, str], ...] = (
    # config default literal — read at runtime, not a hard-coded scope.
    ("backend/config.py", "BRAIN_TOOLS_USER_ID: int = 1"),
    # docs / deprecated fallback in the helper.
    (
        "backend/api/routes/brain_tools.py",
        'falling back to BRAIN_TOOLS_USER_ID',
    ),
    (
        "backend/api/routes/brain_tools.py",
        "settings.BRAIN_TOOLS_USER_ID",
    ),
    # rate-limit middleware — also a deprecated fallback warning.
    (
        "backend/api/middleware/rate_limit.py",
        "settings.BRAIN_TOOLS_USER_ID",
    ),
    (
        "backend/api/middleware/rate_limit.py",
        "BRAIN_TOOLS_USER_ID",
    ),
    # one-time bootstrap seed of the admin account.
    ("backend/api/main.py", "user_id=1"),
    # README narrative.
    ("backend/models/README.md", "user_id=1"),
    # comment in aggregator route — no executable code.
    ("backend/api/routes/aggregator.py", "user_id=1 for now"),
    # docstrings that *describe* the D88 hazard while implementing
    # the fix — they reference the literal but never assign it.
    ("backend/services/agent/brain.py", "``user_id=1`` (the old prod-corruption hazard, D88)"),
    ("backend/tasks/ops/auto_ops.py", "``user_id=1`` (D88 hazard)"),
    (
        "backend/services/portfolio/portfolio_analytics_service.py",
        "``user_id=1`` defaults) — D88.",
    ),
    (
        "backend/services/portfolio/portfolio_analytics_service.py",
        "D88 — no ``user_id=1`` defaults",
    ),
)


_HARD_PATTERNS = (
    re.compile(r"BRAIN_TOOLS_USER_ID"),
    re.compile(r"\buser_id\s*=\s*1\b"),
    re.compile(r"\buser_id=1\b"),
)


def _is_allowlisted(rel_path: str, line: str) -> bool:
    for ap, snippet in _ALLOWLIST:
        if rel_path.endswith(ap) and snippet in line:
            return True
    return False


def test_no_unscoped_user_id_one_in_production_paths():
    """Walk the backend tree (excluding tests + alembic) and fail if any
    unallowlisted hard-coded user_id=1 / BRAIN_TOOLS_USER_ID appears.
    """
    offenders: list[tuple[str, int, str]] = []

    skip_dirs = {"tests", "alembic", "__pycache__", "node_modules"}
    for root, dirs, files in os.walk(_BACKEND):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if not (f.endswith(".py") or f.endswith(".md")):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, os.path.dirname(_BACKEND))
            try:
                with open(full, encoding="utf-8") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if not any(p.search(line) for p in _HARD_PATTERNS):
                            continue
                        if _is_allowlisted(rel, line):
                            continue
                        offenders.append((rel, lineno, line.rstrip()))
            except (UnicodeDecodeError, OSError):
                continue

    assert not offenders, (
        "Unscoped BRAIN_TOOLS_USER_ID / user_id=1 detected. "
        "Either pass the user_id explicitly, or add to the allowlist with "
        "justification in test_brain_tools_user_id_audit.py:\n  "
        + "\n  ".join(f"{p}:{n}: {ln}" for p, n, ln in offenders)
    )
