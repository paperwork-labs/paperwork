"""Autonomy pillar — self-merge trajectory from merge outcomes.

medallion: ops
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _brain_data_dir() -> Path:
    here = Path(__file__).resolve()
    brain_app = here.parents[2]
    return brain_app / "data"


def _pr_outcomes_path() -> Path:
    env = os.environ.get("BRAIN_PR_OUTCOMES_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "pr_outcomes.json"


def collect() -> tuple[float, bool, str]:
    path = _pr_outcomes_path()
    outcomes: list[object] = []
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("outcomes"), list):
                outcomes = raw["outcomes"]
        except (OSError, json.JSONDecodeError):
            outcomes = []

    if len(outcomes) < 10:
        return (20.0, False, "bootstrap estimate — corpus building")

    brain_merges = 0
    for row in outcomes:
        if not isinstance(row, dict):
            continue
        agent = str(row.get("merged_by_agent") or "")
        if agent.startswith("brain-"):
            brain_merges += 1

    ratio = brain_merges / max(len(outcomes), 1)
    score = min(100.0, ratio * 100.0)
    return (
        score,
        True,
        f"Measured self-merge ratio from pr_outcomes (brain-* / total merges): "
        f"{brain_merges}/{len(outcomes)}",
    )
