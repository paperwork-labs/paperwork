"""Autonomy pillar — self-merge trajectory from merge outcomes.

medallion: ops
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.services import app_registry


def _brain_data_dir() -> Path:
    here = Path(__file__).resolve()
    brain_app = here.parents[2]
    return brain_app / "data"


def _pr_outcomes_path() -> Path:
    env = os.environ.get("BRAIN_PR_OUTCOMES_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "pr_outcomes.json"


def _registry_conformance_component() -> tuple[float, bool, str]:
    try:
        registry = app_registry.load_registry()
    except FileNotFoundError:
        return (0.0, False, "app registry missing — no autonomy penalty")

    scores = [entry.conformance.score for entry in registry.apps]
    avg = sum(scores) / len(scores) if scores else 0.0
    points = 10.0 if avg > 0.8 else 0.0
    return (points, True, f"registry conformance avg={avg:.2f}; bonus={points:.0f}")


def collect() -> tuple[float, bool, str]:
    registry_points, registry_measured, registry_note = _registry_conformance_component()
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
        return (
            min(100.0, 20.0 + registry_points),
            registry_measured,
            f"bootstrap estimate — corpus building; {registry_note}",
        )

    brain_merges = 0
    for row in outcomes:
        if not isinstance(row, dict):
            continue
        agent = str(row.get("merged_by_agent") or "")
        if agent.startswith("brain-"):
            brain_merges += 1

    ratio = brain_merges / max(len(outcomes), 1)
    score = min(100.0, ratio * 100.0 + registry_points)
    return (
        score,
        True,
        f"Measured self-merge ratio from pr_outcomes (brain-* / total merges): "
        f"{brain_merges}/{len(outcomes)}; {registry_note}",
    )
