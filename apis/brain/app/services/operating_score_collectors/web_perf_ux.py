"""Web perf + UX pillar — Lighthouse-CI results from apis/brain/data/lighthouse_ci_runs.json.

POS pillar 4 aggregates Lighthouse category scores (performance, accessibility,
best-practices, SEO); main-branch CI persists runs via Lighthouse CI workflow.

medallion: ops
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

_BOOTSTRAP = (
    55.0,
    False,
    "no Lighthouse-CI runs yet — collector deferred until first run",
)


def _brain_data_dir() -> Path:
    here = Path(__file__).resolve()
    brain_app = here.parents[2]
    return brain_app / "data"


def _lighthouse_runs_path() -> Path:
    env = os.environ.get("BRAIN_LIGHTHOUSE_CI_RUNS_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "lighthouse_ci_runs.json"


def _parse_score(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _aggregate_from_scores(scores: dict[str, Any]) -> float | None:
    keys = ("performance", "accessibility", "best_practices", "seo")
    sums: list[float] = []
    for k in keys:
        pv = _parse_score(scores.get(k))
        if pv is None:
            return None
        sums.append(pv)
    return sum(sums) / 4.0


def _run_sort_key(run: dict[str, Any]) -> str:
    s = run.get("run_at")
    return (isinstance(s, str) and s) or ""


def _latest_run(blob: dict[str, Any]) -> dict[str, Any] | None:
    raw = blob.get("runs")
    if not isinstance(raw, list) or len(raw) == 0:
        return None
    candidates: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            candidates.append(row)
    if not candidates:
        return None
    sorted_runs = sorted(candidates, key=_run_sort_key, reverse=True)
    chosen = sorted_runs[0]
    sc = chosen.get("scores")
    return chosen if isinstance(sc, dict) else None


def collect() -> tuple[float, bool, str]:
    pth = _lighthouse_runs_path()
    if not pth.is_file():
        return _BOOTSTRAP

    try:
        doc = json.loads(pth.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _BOOTSTRAP

    if not isinstance(doc, dict):
        return _BOOTSTRAP

    latest = _latest_run(doc)
    if latest is None:
        return _BOOTSTRAP

    scores_any = latest.get("scores")
    if not isinstance(scores_any, dict):
        return _BOOTSTRAP

    avg_frac = _aggregate_from_scores(scores_any)
    if avg_frac is None:
        return _BOOTSTRAP

    score_100 = 100.0 * avg_frac

    ts = latest.get("run_at")
    ts_disp = (isinstance(ts, str) and ts) or "?"
    measured = True
    note = f"from lighthouse_ci_runs.json @ {ts_disp}"
    return (float(score_100), measured, note)
