"""Accessibility + design system pillar — axe-core runs + optional Studio DS adoption.

Reads ``apis/brain/data/axe_runs.json`` (override ``BRAIN_AXE_RUNS_JSON``). When runs exist,
uses the latest ``score`` from CI; optionally averages with a design-system adoption sub-score
from ``apps/studio/src`` (Tailwind class-soup vs ``@paperwork-labs/ui`` imports).

medallion: ops
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

_BOOTSTRAP = (
    50.0,
    False,
    "no axe-core runs yet — collector deferred until first run",
)

_UI_IMPORT_RE = re.compile(
    r"""import\s+(?:(?P<def>\w+)\s+from|(?P<named>\{[^}]+\})\s+from)\s*['"]@paperwork-labs/ui['"]"""
)
_CLASSNAME_STR_RE = re.compile(
    r"""className\s*=\s*["']([^"']+)["']""",
    re.MULTILINE,
)


def _brain_data_dir() -> Path:
    from app.utils.paths import brain_data_dir

    return brain_data_dir()


def _axe_runs_path() -> Path:
    env = os.environ.get("BRAIN_AXE_RUNS_JSON", "").strip()
    if env:
        return Path(env)
    return _brain_data_dir() / "axe_runs.json"


def _repo_root() -> Path | None:
    env = os.environ.get("BRAIN_REPO_ROOT", "").strip()
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    from app.utils.paths import repo_root

    return repo_root()


def _run_sort_key(run: dict[str, Any]) -> str:
    s = run.get("run_at")
    return (isinstance(s, str) and s) or ""


def _latest_axe_run(doc: dict[str, Any]) -> dict[str, Any] | None:
    raw = doc.get("runs")
    if not isinstance(raw, list) or len(raw) == 0:
        return None
    candidates: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            candidates.append(row)
    if not candidates:
        return None
    return sorted(candidates, key=_run_sort_key, reverse=True)[0]


def _parse_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _count_ui_import_symbols(text: str) -> int:
    n = 0
    for m in _UI_IMPORT_RE.finditer(text):
        if m.group("def"):
            n += 1
            continue
        named = m.group("named")
        if named:
            inner = named.strip("{} \n")
            for part in inner.split(","):
                tok = part.strip().split()
                if not tok:
                    continue
                if tok[0] == "type":
                    continue
                n += 1
    return n


def _count_class_soup_and_ui(studio_src: Path) -> tuple[int, int]:
    soup = 0
    ui = 0
    exts = {".tsx", ".ts", ".jsx", ".js"}
    for p in studio_src.rglob("*"):
        if p.suffix not in exts or "node_modules" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        ui += _count_ui_import_symbols(text)
        for cm in _CLASSNAME_STR_RE.finditer(text):
            inner = cm.group(1)
            segments = [x for x in inner.split() if x.strip()]
            if len(segments) > 5:
                soup += 1
    return soup, ui


def _ds_adoption_score(repo_root: Path) -> tuple[float | None, str]:
    studio = repo_root / "apps" / "studio" / "src"
    if not studio.is_dir():
        raise FileNotFoundError(f"studio src missing: {studio}")
    soup, ds = _count_class_soup_and_ui(studio)
    denom = soup + ds
    if denom <= 0:
        return None, "no Tailwind-heavy nodes or UI imports counted"
    ratio = ds / denom
    if ratio >= 0.8:
        sub = 100.0
    elif ratio < 0.3:
        sub = 0.0
    else:
        sub = 100.0 * (ratio - 0.3) / (0.8 - 0.3)
    note = (
        f"DS adoption ratio={ratio:.3f} (soup={soup} ui_import_symbols={ds}) -> sub-score {sub:.2f}"
    )
    return float(sub), note


def collect() -> tuple[float, bool, str]:
    pth = _axe_runs_path()
    if not pth.is_file():
        return _BOOTSTRAP

    try:
        doc = json.loads(pth.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _BOOTSTRAP

    if not isinstance(doc, dict):
        return _BOOTSTRAP

    latest = _latest_axe_run(doc)
    if latest is None:
        return _BOOTSTRAP

    axe_score = _parse_float(latest.get("score"))
    if axe_score is None:
        return _BOOTSTRAP

    ts = latest.get("run_at")
    ts_disp = (isinstance(ts, str) and ts) or "?"
    base_note = f"from axe_runs.json @ {ts_disp}"

    root = _repo_root()
    if root is None:
        return (float(axe_score), True, base_note)

    try:
        ds_val, ds_note = _ds_adoption_score(root)
    except (OSError, ValueError, FileNotFoundError):
        return (float(axe_score), True, base_note)

    if ds_val is None:
        return (float(axe_score), True, f"{base_note}; {ds_note}")

    combined = (axe_score + ds_val) / 2.0
    return (
        float(combined),
        True,
        f"{base_note}; {ds_note}",
    )
