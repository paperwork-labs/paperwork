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
    """Tiny YAML parser — handles flat scalars, one-level nested mappings,
    and nested lists. Sufficient for our sprint/plan/doc frontmatter; falls
    back to PyYAML if available for anything more exotic."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end():]

    try:
        import datetime as _dt

        import yaml  # type: ignore

        parsed = yaml.safe_load(raw) or {}

        def _normalize(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: _normalize(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_normalize(v) for v in value]
            if isinstance(value, (_dt.datetime, _dt.date)):
                return value.isoformat()
            return value

        if isinstance(parsed, dict):
            return _normalize(parsed), body
    except ImportError:
        pass
    except Exception:
        pass

    parsed_local: dict[str, Any] = {}
    current_obj: dict[str, Any] | None = None
    pending_list_key: str | None = None
    pending_list_target: dict[str, Any] | None = None
    pending_list: list[Any] | None = None

    def flush_list() -> None:
        nonlocal pending_list, pending_list_key, pending_list_target
        if pending_list is not None and pending_list_key is not None and pending_list_target is not None:
            pending_list_target[pending_list_key] = pending_list
        pending_list = None
        pending_list_key = None
        pending_list_target = None

    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if pending_list is not None and stripped.startswith("- "):
            min_indent = 2 if pending_list_target is parsed_local else 4
            if indent >= min_indent:
                pending_list.append(parse_scalar(stripped[2:].strip()))
                continue
            flush_list()

        if indent >= 2 and current_obj is not None:
            if ":" not in stripped:
                continue
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip()
            if not v:
                flush_list()
                pending_list = []
                pending_list_key = k
                pending_list_target = current_obj
                current_obj[k] = pending_list
                continue
            flush_list()
            current_obj[k] = parse_scalar(v)
            continue

        flush_list()
        current_obj = None

        if indent == 0 and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if not value:
                current_obj = {}
                parsed_local[key] = current_obj
                pending_list = []
                pending_list_key = key
                pending_list_target = parsed_local
                continue
            parsed_local[key] = parse_scalar(value)

    flush_list()

    for key, value in list(parsed_local.items()):
        if isinstance(value, dict) and not value:
            parsed_local[key] = parsed_local.get(f"_{key}_list") or []

    return parsed_local, body


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


SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$", re.MULTILINE)
PR_MENTION_RE = re.compile(r"#(\d{2,5})\b|/pull/(\d{2,5})\b")

# Canonical sprint status vocabulary (see docs/sprints/README.md):
#   planned | in_progress | paused | shipped | deferred | dropped
# Aliases map into this set. "active" is treated as in_progress for back-compat.
CANONICAL_STATUSES = {
    "planned",
    "in_progress",
    "paused",
    "shipped",
    "deferred",
    "dropped",
    "active",
    "abandoned",
}
STATUS_ALIASES = {
    "in-progress": "in_progress",
    "inprogress": "in_progress",
    "wip": "in_progress",
    "research": "in_progress",
    "draft": "in_progress",
    "open": "in_progress",
    "ongoing": "in_progress",
    "active": "in_progress",
    "merged": "shipped",
    "done": "shipped",
    "complete": "shipped",
    "completed": "shipped",
    "closed": "shipped",
    "decided": "in_progress",
    "approved": "in_progress",
    "blocked": "paused",
    "on_hold": "paused",
    "on-hold": "paused",
    "cancelled": "dropped",
    "canceled": "dropped",
    "abandoned": "dropped",
    "dropped": "dropped",
}


def normalize_status(raw: Any) -> str:
    if not isinstance(raw, str):
        return "in_progress"
    key = raw.strip().lower()
    if key in CANONICAL_STATUSES:
        if key == "active":
            return "in_progress"
        if key == "abandoned":
            return "dropped"
        return key
    return STATUS_ALIASES.get(key, "in_progress")


def extract_section(body: str, *titles: str, max_lines: int = 200) -> str | None:
    """Return the body of the first '## <title>' section, or None.
    Matches case-insensitively and accepts multiple aliases."""
    titles_lower = [t.lower() for t in titles]
    matches = list(SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        if m.group("title").strip().lower() in titles_lower:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            chunk = body[start:end].strip()
            lines = chunk.splitlines()
            if len(lines) > max_lines:
                lines = lines[:max_lines]
            return "\n".join(lines).strip() or None
    return None


def first_paragraph(text: str | None) -> str | None:
    if not text:
        return None
    for chunk in re.split(r"\n\s*\n", text):
        chunk = chunk.strip()
        if chunk and not chunk.startswith(("#", "|", "-")):
            return chunk
    return None


def extract_bullets(text: str | None, limit: int = 8) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    for m in BULLET_RE.finditer(text):
        line = m.group("text").strip()
        # Strip leading bold "Foo:" decorations to keep cards tidy
        line = re.sub(r"^\*\*([^*]+)\*\*\s*[-—:]?\s*", r"\1: ", line)
        if line and len(line) < 320:
            out.append(line)
        if len(out) >= limit:
            break
    return out


def extract_pr_numbers(*texts: str | None) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for text in texts:
        if not text:
            continue
        for m in PR_MENTION_RE.finditer(text):
            num = int(m.group(1) or m.group(2))
            if num in seen:
                continue
            seen.add(num)
            ordered.append(num)
    return ordered


def coerce_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[int] = []
        for v in value:
            try:
                out.append(int(str(v).strip().lstrip("#")))
            except (TypeError, ValueError):
                continue
        return out
    return []


def coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def parse_sprint(p: Path) -> dict[str, Any]:
    raw = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    sprint = fm.get("sprint") if isinstance(fm.get("sprint"), dict) else {}
    title = first_h1(body) or p.stem
    pr = sprint.get("pr")

    goal = first_paragraph(extract_section(body, "Goal", "Why", "Objective"))
    outcome_text = extract_section(body, "Outcome", "What shipped", "Result")
    outcome_bullets = extract_bullets(outcome_text)
    lessons_bullets = extract_bullets(
        extract_section(body, "What we learned", "Lessons", "Lessons learned")
    )
    followups_bullets = extract_bullets(
        extract_section(body, "Follow-ups", "Next", "Next steps")
    )

    plans = coerce_str_list(sprint.get("plans") or sprint.get("plan") or fm.get("plan"))
    declared_prs = coerce_int_list(sprint.get("prs") or fm.get("prs"))
    body_prs = extract_pr_numbers(outcome_text, body[:8000])
    if pr:
        try:
            declared_prs.append(int(pr))
        except (TypeError, ValueError):
            pass
    seen_pr: set[int] = set()
    related_prs: list[int] = []
    for n in declared_prs + body_prs:
        if n in seen_pr:
            continue
        seen_pr.add(n)
        related_prs.append(n)

    blocker = sprint.get("blocker") or fm.get("blocker")
    return {
        "slug": slugify(p.stem),
        "path": str(p.relative_to(REPO_ROOT)),
        "title": title,
        "status": normalize_status(fm.get("status", "in_progress")),
        "raw_status": fm.get("status", "in_progress"),
        "last_reviewed": fm.get("last_reviewed"),
        "blocker": blocker,
        "owner": fm.get("owner"),
        "domain": fm.get("domain"),
        "start": sprint.get("start"),
        "end": sprint.get("end"),
        "duration_weeks": sprint.get("duration_weeks"),
        "pr": pr,
        "pr_url": (
            f"https://github.com/paperwork-labs/paperwork/pull/{pr}" if pr else None
        ),
        "ships": coerce_str_list(sprint.get("ships")),
        "personas": coerce_str_list(sprint.get("personas")),
        "plans": plans,
        "related_prs": related_prs,
        "goal": goal,
        "outcome_bullets": outcome_bullets,
        "lessons": lessons_bullets,
        "followups": followups_bullets,
    }


def parse_plan(p: Path, product_slug: str) -> dict[str, Any]:
    raw = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    title = first_h1(body) or p.stem
    return {
        "slug": slugify(p.stem),
        "path": str(p.relative_to(REPO_ROOT)),
        "title": title,
        "status": normalize_status(fm.get("status", "active")),
        "raw_status": fm.get("status", "active"),
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




def compute_effective_sprint_status(sprint: dict[str, Any]) -> str:
    """Read-time reconciliation: stale 'paused' without a blocker can read as shipped when work is done."""
    base = str(sprint.get("status", "in_progress")).lower()
    if base == "active":
        base = "in_progress"
    if base != "paused" and base not in {"on_hold", "on-hold"}:
        return base
    blocker = sprint.get("blocker")
    if blocker and str(blocker).strip():
        return "paused"
    from datetime import date

    def _parse_d(s: Any) -> date | None:
        if not s:
            return None
        try:
            return date.fromisoformat(str(s)[:10])
        except ValueError:
            return None

    end = _parse_d(sprint.get("end"))
    reviewed = _parse_d(sprint.get("last_reviewed"))
    today = date.today()
    stale_days = 14
    stale = False
    if end and (today - end).days > stale_days:
        stale = True
    if reviewed and (today - reviewed).days > stale_days:
        stale = True
    if not stale:
        return "paused"
    outcomes = len(sprint.get("outcome_bullets") or [])
    followups = len(sprint.get("followups") or [])
    prs = len(sprint.get("related_prs") or [])
    denom = max(1, outcomes + followups)
    ratio = outcomes / denom
    if ratio >= 0.55 and (followups <= 2 or prs > 0):
        return "shipped"
    return "paused"


def apply_sprint_reconciliation(sprints: list[dict[str, Any]]) -> None:
    for s in sprints:
        s["effective_status"] = compute_effective_sprint_status(s)


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
    apply_sprint_reconciliation(sprints)
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
