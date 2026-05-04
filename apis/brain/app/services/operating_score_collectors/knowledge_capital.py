"""Knowledge capital — procedural rules density + outcomes corpus completeness.

medallion: ops
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml


def _brain_data_dir() -> Path:
    from app.utils.paths import brain_data_dir

    return brain_data_dir()


def _pr_outcomes_path() -> Path:
    env = os.environ.get("BRAIN_PR_OUTCOMES_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "pr_outcomes.json"


def _procedural_yaml_path() -> Path:
    env = os.environ.get("BRAIN_PROCEDURAL_MEMORY_YAML", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "procedural_memory.yaml"


def collect() -> tuple[float, bool, str]:
    pm_path = _procedural_yaml_path()
    rule_count = 0
    if pm_path.is_file():
        try:
            doc: Any = yaml.safe_load(pm_path.read_text(encoding="utf-8"))
            rules = doc.get("rules") if isinstance(doc, dict) else None
            if isinstance(rules, list):
                rule_count = len(rules)
        except (OSError, yaml.YAMLError):
            rule_count = 0

    pr_path = _pr_outcomes_path()
    outcomes: list[Any] = []
    if pr_path.is_file():
        try:
            raw = json.loads(pr_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("outcomes"), list):
                outcomes = raw["outcomes"]
        except (OSError, json.JSONDecodeError):
            outcomes = []

    with_h24 = 0
    for row in outcomes:
        if not isinstance(row, dict):
            continue
        oc = row.get("outcomes")
        if isinstance(oc, dict) and oc.get("h24") is not None:
            with_h24 += 1

    n = len(outcomes)
    pct = (100.0 * with_h24 / n) if n else 0.0

    raw = rule_count * 5 + pct / 2.0
    score = float(min(100.0, raw))
    note = (
        f"rules={rule_count}; outcomes_total={n}; with_h24={with_h24}; "
        f"completion_pct≈{pct:.1f}; formula=min(100, rules*5 + pct/2)={score:.1f}"
    )
    return (score, True, note)
