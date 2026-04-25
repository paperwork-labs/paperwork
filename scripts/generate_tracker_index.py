#!/usr/bin/env python3
"""Generate apps/studio/src/data/tracker-index.json — the single
source-of-truth for /admin/tasks, /admin/sprints, and per-product plan
views.

Walks four sources:

  1. docs/TASKS.md                            — company tracker (root)
  2. docs/sprints/*.md                        — cross-cutting sprint logs
  3. docs/<product>/plans/*.md (axiomfolio…)  — per-product master plans
  4. PR data via `gh pr list` (best effort)   — links each sprint to its PR

Output shape:

    {
      "content_hash": "abc123",
      "company": {
        "path": "docs/TASKS.md",
        "title": "Paperwork Labs — Venture Build Tasks",
        "version": "11.0",
        "updated": "2026-03-22",
        "critical_dates": [...],
        "summary": "first 5 lines"
      },
      "sprints": [
        {
          "slug": "infra-automation-hardening-2026q2",
          "path": "docs/sprints/INFRA_AUTOMATION_HARDENING_2026Q2.md",
          "title": "Infra & Automation Hardening — 2026 Q2",
          "status": "shipped",
          "start": "2026-04-01",
          "end": "2026-04-23",
          "pr": 141,
          "pr_url": "https://github.com/paperwork-labs/paperwork/pull/141",
          "pr_state": "MERGED",
          "ships": ["studio", "brain", ...],
          "personas": [...],
          "owner": "engineering"
        }
      ],
      "products": [
        {
          "slug": "axiomfolio",
          "label": "AxiomFolio",
          "plans": [
            {"slug": "master-plan-2026", "path": "...", "title": "...", "status": "active"}
          ]
        }
      ]
    }

The output is checked into the repo so Studio (Next.js, sometimes
deployed on Vercel without write access to the repo at runtime) can
render the trackers without round-tripping to GitHub for every page
load. CI runs this and fails on drift.

Usage:
    python3 scripts/generate_tracker_index.py [--check]

medallion: ops
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
SPRINTS_DIR = DOCS / "sprints"
TASKS_PATH = DOCS / "TASKS.md"
OUT_PATH = REPO_ROOT / "apps" / "studio" / "src" / "data" / "tracker-index.json"

PRODUCTS = [
    {"slug": "axiomfolio", "label": "AxiomFolio", "plans_dir": DOCS / "axiomfolio" / "plans"},
    {"slug": "filefree", "label": "FileFree", "plans_dir": DOCS / "filefree" / "plans"},
    {"slug": "launchfree", "label": "LaunchFree", "plans_dir": DOCS / "launchfree" / "plans"},
    {"slug": "distill", "label": "Distill", "plans_dir": DOCS / "distill" / "plans"},
    {"slug": "trinkets", "label": "Trinkets", "plans_dir": DOCS / "trinkets" / "plans"},
]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Tiny YAML parser — handles flat scalars and one-level nested
    mappings under the `sprint:` key (the only nested structure we use)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end():]
    parsed: dict[str, Any] = {}
    current_key: str | None = None
    current_obj: dict[str, Any] | None = None
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  ") and current_obj is not None:
            sub = line.strip()
            if ":" not in sub:
                continue
            k, _, v = sub.partition(":")
            current_obj[k.strip()] = parse_scalar(v.strip())
            continue
        if line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            current_key = key
            current_obj = {}
            parsed[key] = current_obj
            continue
        parsed[key] = parse_scalar(value)
        current_key, current_obj = None, None
    return parsed, body


def parse_scalar(v: str) -> Any:
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [s.strip().strip("'\"") for s in inner.split(",")]
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        pass
    return v.strip("'\"")


def first_h1(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def slugify(name: str) -> str:
    s = name.lower().replace(".md", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def parse_company_tasks() -> dict[str, Any]:
    if not TASKS_PATH.exists():
        return {}
    raw = TASKS_PATH.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    title = first_h1(body) or "Company Tasks"
    version = None
    updated = None
    m = re.search(r"\*\*Version\*\*:\s*([\w.]+)\s*\|\s*\*\*Updated\*\*:\s*([\d-]+)", body)
    if m:
        version = m.group(1)
        updated = m.group(2)
    critical_dates: list[dict[str, str]] = []
    in_table = False
    for line in body.splitlines():
        if line.startswith("## Critical Dates"):
            in_table = True
            continue
        if in_table and line.startswith("##"):
            break
        if in_table and line.startswith("| ") and not line.startswith("| ---"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4 and cells[0].lower() != "milestone":
                critical_dates.append(
                    {
                        "milestone": cells[0],
                        "deadline": cells[1],
                        "status": cells[2],
                        "notes": cells[3],
                    }
                )
    return {
        "path": str(TASKS_PATH.relative_to(REPO_ROOT)),
        "title": title,
        "version": version,
        "updated": updated,
        "critical_dates": critical_dates,
        "owner": fm.get("owner", "engineering"),
    }


def parse_sprint(p: Path) -> dict[str, Any]:
    raw = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    sprint = fm.get("sprint") if isinstance(fm.get("sprint"), dict) else {}
    title = first_h1(body) or p.stem
    pr = sprint.get("pr")
    return {
        "slug": slugify(p.stem),
        "path": str(p.relative_to(REPO_ROOT)),
        "title": title,
        "status": fm.get("status", "active"),
        "owner": fm.get("owner"),
        "domain": fm.get("domain"),
        "start": sprint.get("start"),
        "end": sprint.get("end"),
        "duration_weeks": sprint.get("duration_weeks"),
        "pr": pr,
        "pr_url": (
            f"https://github.com/paperwork-labs/paperwork/pull/{pr}" if pr else None
        ),
        "ships": sprint.get("ships") or [],
        "personas": sprint.get("personas") or [],
    }


def parse_plan(p: Path, product_slug: str) -> dict[str, Any]:
    raw = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    title = first_h1(body) or p.stem
    return {
        "slug": slugify(p.stem),
        "path": str(p.relative_to(REPO_ROOT)),
        "title": title,
        "status": fm.get("status", "active"),
        "owner": fm.get("owner"),
        "doc_kind": fm.get("doc_kind", "plan"),
        "last_reviewed": fm.get("last_reviewed"),
        "product": product_slug,
    }


def collect_sprints() -> list[dict[str, Any]]:
    if not SPRINTS_DIR.is_dir():
        return []
    out = []
    for p in sorted(SPRINTS_DIR.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        try:
            out.append(parse_sprint(p))
        except Exception as exc:
            print(f"  ! sprint parse failed: {p.name} ({exc})", file=sys.stderr)
    out.sort(key=lambda s: s.get("end") or s.get("start") or "", reverse=True)
    return out


def collect_products() -> list[dict[str, Any]]:
    products = []
    for product in PRODUCTS:
        plans_dir: Path = product["plans_dir"]  # type: ignore[assignment]
        plans = []
        if plans_dir.is_dir():
            for p in sorted(plans_dir.glob("*.md")):
                if p.name.lower() == "readme.md":
                    continue
                try:
                    plans.append(parse_plan(p, product["slug"]))
                except Exception as exc:
                    print(f"  ! plan parse failed: {p} ({exc})", file=sys.stderr)
        products.append(
            {
                "slug": product["slug"],
                "label": product["label"],
                "plans_dir": str(plans_dir.relative_to(REPO_ROOT)) if plans_dir.is_dir() else None,
                "plans": plans,
            }
        )
    return products


def fetch_pr_states(prs: list[int]) -> dict[int, str]:
    """Best-effort `gh pr view` per PR. Empty dict on failure (offline, no auth)."""
    out: dict[int, str] = {}
    if not prs:
        return out
    for num in prs:
        try:
            res = subprocess.run(
                ["gh", "pr", "view", str(num), "--json", "state"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(REPO_ROOT),
            )
            if res.returncode != 0:
                continue
            data = json.loads(res.stdout)
            out[num] = data.get("state", "")
        except Exception:
            continue
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the on-disk index differs from a freshly generated one.",
    )
    parser.add_argument(
        "--no-pr-fetch",
        action="store_true",
        help="Skip `gh pr view` calls (faster, useful in CI without auth).",
    )
    args = parser.parse_args()

    company = parse_company_tasks()
    sprints = collect_sprints()
    products = collect_products()

    pr_nums = [s["pr"] for s in sprints if s.get("pr")]
    pr_states: dict[int, str] = {}
    if not args.no_pr_fetch:
        pr_states = fetch_pr_states(pr_nums)
    for s in sprints:
        if s.get("pr") in pr_states:
            s["pr_state"] = pr_states[s["pr"]]

    payload: dict[str, Any] = {
        "company": company,
        "sprints": sprints,
        "products": products,
    }
    serialized = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload["content_hash"] = hashlib.sha256(serialized).hexdigest()[:12]
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    if args.check:
        existing = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
        if existing != rendered:
            print(
                "::error::tracker-index.json is stale. "
                "Run: python3 scripts/generate_tracker_index.py",
                file=sys.stderr,
            )
            return 1
        print(f"OK — tracker-index.json is current ({payload['content_hash']})")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)} — "
        f"{len(sprints)} sprints, {sum(len(p['plans']) for p in products)} plans, "
        f"{len(company.get('critical_dates', []))} critical dates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
