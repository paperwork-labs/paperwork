#!/usr/bin/env python3
"""Summarize Lighthouse-CI artifacts into apis/brain/data/lighthouse_ci_runs.json (main-branch CI)."""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_SCHEMA = "lighthouse_ci_runs/v1"
_MAX_RUNS = 200


def _repo_root() -> Path:
    for key in ("GITHUB_WORKSPACE", "ROOT_WORKTREE_PATH"):
        v = os.environ.get(key, "").strip()
        if v:
            return Path(v)
    return Path.cwd()


def _brain_file(root: Path) -> Path:
    return root / "apis" / "brain" / "data" / "lighthouse_ci_runs.json"


def _dot_lhci(root: Path) -> Path:
    return root / ".lighthouseci"


def _score_from_category(cat_obj: Any) -> float | None:
    if not isinstance(cat_obj, dict):
        return None
    s = cat_obj.get("score")
    if s is None:
        return None
    if isinstance(s, bool):
        return None
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _is_lighthouse_report(doc: Any) -> bool:
    return (
        isinstance(doc, dict)
        and isinstance(doc.get("categories"), dict)
        and isinstance(doc["categories"].get("performance"), dict)
        and "score" in doc["categories"]["performance"]
    )


def _load_lhrs(dot_lhci: Path) -> list[dict[str, Any]]:
    if not dot_lhci.is_dir():
        return []
    reports: list[dict[str, Any]] = []
    for pth in sorted(dot_lhci.rglob("*.json")):
        name = pth.name.lower()
        if name == "manifest.json" or name.endswith("-manifest.json"):
            continue
        try:
            doc = json.loads(pth.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict) and _is_lighthouse_report(doc):
            reports.append(doc)
        elif isinstance(doc, list):
            for elt in doc:
                if isinstance(elt, dict) and _is_lighthouse_report(elt):
                    reports.append(elt)
    return reports


def _rollup_category_scores(
    lhrs: list[dict[str, Any]],
) -> dict[str, float] | None:
    keys = ("performance", "accessibility", "best-practices", "seo")
    sums: dict[str, list[float]] = {k: [] for k in keys}
    for lhr in lhrs:
        cats = lhr.get("categories")
        if not isinstance(cats, dict):
            continue
        for key in keys:
            sc = _score_from_category(cats.get(key))
            if sc is None:
                continue
            sums[key].append(sc)
    out: dict[str, float] = {}
    for key in keys:
        vals = sums[key]
        if not vals:
            return None
        out[key.replace("-", "_")] = round(sum(vals) / len(vals), 6)
    return out


def _metric_audits_numeric(lhrs: list[dict[str, Any]], audit_id: str) -> float | None:
    vals: list[float] = []
    for lhr in lhrs:
        audits = lhr.get("audits")
        if not isinstance(audits, dict):
            continue
        ad = audits.get(audit_id)
        if isinstance(ad, dict) and isinstance(ad.get("numericValue"), (int, float)):
            vals.append(float(ad["numericValue"]))
    if not vals:
        return None
    return sum(vals) / len(vals)


def _rollup_metrics(lhrs: list[dict[str, Any]]) -> dict[str, float]:
    base = {"lcp_ms": 0.0, "cls": 0.0, "tbt_ms": 0.0, "fcp_ms": 0.0}
    lcp = _metric_audits_numeric(lhrs, "largest-contentful-paint")
    if lcp is not None:
        base["lcp_ms"] = round(lcp, 3)
    cls = _metric_audits_numeric(lhrs, "cumulative-layout-shift")
    if cls is not None:
        base["cls"] = round(cls, 6)
    tbt = _metric_audits_numeric(lhrs, "total-blocking-time")
    if tbt is not None:
        base["tbt_ms"] = round(tbt, 3)
    fcp = _metric_audits_numeric(lhrs, "first-contentful-paint")
    if fcp is not None:
        base["fcp_ms"] = round(fcp, 3)
    return base


def _pick_url(lhrs: list[dict[str, Any]], preview: str | None) -> str:
    if preview and preview.startswith("http"):
        return preview
    for lhr in lhrs:
        u = lhr.get("requestedUrl") or lhr.get("finalUrl")
        if isinstance(u, str) and u.startswith("http"):
            return u
    return "https://studio.paperworklabs.com"


def main() -> int:
    root = _repo_root()
    dot_lhci = _dot_lhci(root)
    lhrs = _load_lhrs(dot_lhci)
    preview = os.environ.get("LHCI_PREVIEW_URL", "").strip() or None
    scores = _rollup_category_scores(lhrs)

    bf = _brain_file(root)
    bf.parent.mkdir(parents=True, exist_ok=True)

    if bf.is_file():
        try:
            blob = json.loads(bf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            blob = {}
    else:
        blob = {}

    if not isinstance(blob, dict):
        blob = {}

    blob["schema"] = _SCHEMA
    blob.setdefault(
        "description",
        "Lighthouse-CI scores per main-branch run. POS pillar 4 (web_perf_ux) reads the latest entry.",
    )
    runs_any = blob.get("runs")
    runs_in: list[Any] = list(runs_any) if isinstance(runs_any, list) else []

    sha = (
        os.environ.get("GITHUB_SHA", "").strip()
        or os.environ.get("BUILD_VCS_NUMBER", "").strip()
        or "unknown"
    )
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if scores:
        metrics = _rollup_metrics(lhrs)
        entry = {
            "run_at": ts,
            "url": _pick_url(lhrs, preview),
            "scores": scores,
            "metrics": metrics,
            "commit_sha": sha,
        }
        runs_in.append(entry)
        if len(runs_in) > _MAX_RUNS:
            runs_in = runs_in[-_MAX_RUNS :]
        blob["runs"] = runs_in
        bf.write_text(json.dumps(blob, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        print(json.dumps({"wrote_scored_run": True, "path": str(bf)}, indent=2))
        return 0

    blob["runs"] = runs_in if runs_in else []
    bf.write_text(json.dumps(blob, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote_scored_run": False,
                "reason": "no_lighthouse_reports_in_dot_lighthouseci",
                "path": str(dot_lhci),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
