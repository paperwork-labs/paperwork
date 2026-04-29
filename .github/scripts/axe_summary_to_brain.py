#!/usr/bin/env python3
"""Append axe-core CLI JSON summary to apis/brain/data/axe_runs.json (POS pillar 5).

Reads AXE_RESULT_PATH (default /tmp/axe/result.json); writes capped history (200 runs).

medallion: ops (Brain data pipeline artifact; runnable without package imports.)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_OUT = Path("apis/brain/data/axe_runs.json")
_RESULT = Path(os.environ.get("AXE_RESULT_PATH", "/tmp/axe/result.json"))
_SCHEMA = "axe_runs/v1"
_DESC = (
    "axe-core a11y scores per main-branch run. POS pillar 5 (a11y_design_system) "
    "reads the latest entry."
)


def _counts() -> tuple[dict[str, int], int, int, float]:
    raw = json.loads(_RESULT.read_text(encoding="utf-8"))
    doc: dict[str, Any] = raw[0] if isinstance(raw, list) and raw else raw
    if not isinstance(doc, dict):
        raise ValueError("axe result is not an object or non-empty array")

    viols = doc.get("violations") or []
    if not isinstance(viols, list):
        viols = []
    impact_counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    for v in viols:
        if not isinstance(v, dict):
            continue
        imp = str(v.get("impact") or "").lower()
        if imp in impact_counts:
            impact_counts[imp] += 1

    passes = doc.get("passes")
    n_passes = len(passes) if isinstance(passes, list) else 0
    inc = doc.get("incomplete")
    n_inc = len(inc) if isinstance(inc, list) else 0

    c, s, m, mi = (
        impact_counts["critical"],
        impact_counts["serious"],
        impact_counts["moderate"],
        impact_counts["minor"],
    )
    raw_score = 100.0 - (c * 20 + s * 10 + m * 5 + mi * 2)
    score = max(0.0, min(100.0, raw_score))
    return impact_counts, n_passes, n_inc, score


def main() -> int:
    if not _RESULT.is_file():
        print(f"axe result missing: {_RESULT}", file=sys.stderr)
        return 1

    try:
        impact_counts, n_passes, n_inc, score = _counts()
    except (OSError, json.JSONDecodeError, ValueError) as ex:
        print(f"failed to parse axe result: {ex}", file=sys.stderr)
        return 1

    run_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    url = os.environ.get("AXE_TARGET_URL", "https://studio.paperworklabs.com").strip()
    commit_sha = os.environ.get("GITHUB_SHA", "").strip() or "unknown"

    entry = {
        "run_at": run_at,
        "url": url,
        "violations": impact_counts,
        "passes": n_passes,
        "incomplete": n_inc,
        "score": float(score),
        "commit_sha": commit_sha,
    }

    if _OUT.is_file():
        try:
            blob = json.loads(_OUT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            blob = {}
    else:
        blob = {}

    if not isinstance(blob, dict):
        blob = {}
    runs = blob.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(entry)
    runs_sorted = sorted(
        [r for r in runs if isinstance(r, dict)],
        key=lambda r: str(r.get("run_at") or ""),
        reverse=True,
    )
    capped = runs_sorted[:200]

    out = {
        "schema": _SCHEMA,
        "description": _DESC,
        "runs": capped,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
