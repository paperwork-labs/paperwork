#!/usr/bin/env python3
"""Doc-vs-code truth check — scan every markdown doc for file/path references
and verify the targets still exist on disk.

Also reports heuristic "stale language" hits (multi-repo claims, obsolete paths,
deleted features referenced as live). Owned by the `qa` persona per Track K.

Usage:
    python scripts/check_doc_refs.py                     # scan all of docs/
    python scripts/check_doc_refs.py --strict            # exit 1 on broken refs
    python scripts/check_doc_refs.py --json out.json     # dump machine-readable
    python scripts/check_doc_refs.py --paths docs/       # custom roots

Baseline run on 2026-04-24 establishes `docs/GROUND_TRUTH.md`. Subsequent runs
(Track K, weekly, posted to #qa) diff against that baseline.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

# Markdown link: [label](path) — but skip external http(s) links and anchors.
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+?)(?:#[^)]*)?\)")
# Bare file:line references we also see in docs: `apis/brain/app/agent/loop.py:L129`
FILE_LINE_RE = re.compile(r"`([^`]+\.(?:py|ts|tsx|js|json|yaml|yml|sh))(?::L?\d+)?`")

# Heuristic stale-language patterns (regex, substring match).
STALE_PATTERNS: list[tuple[str, str]] = [
    # Multi-repo era claims — we're a single monorepo as of 2026-04.
    (r"\b(paperwork-labs/axiomfolio|paperwork-labs/filefree|paperwork-labs/launchfree|paperwork-labs/distill)\b", "multi-repo reference (we are a monorepo)"),
    (r"\bacross (?:our )?repos\b", "multi-repo language"),
    (r"\bin the (?:axiomfolio|filefree|launchfree) repo\b", "multi-repo language"),
    # Old render / infra talk.
    (r"\bportal/index\.html\b", "old local portal (superseded by Studio)"),
    # Contradictions about PR automation home.
    (r"\bno cron\b", "stale: PR automation does use cron/scheduler (APScheduler, Track B)"),
]

# Glob-like prefixes we ignore as "external" so we don't try to resolve them.
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "//")

DEFAULT_SCAN_ROOTS = ("docs",)


def is_external(path: str) -> bool:
    return path.startswith(EXTERNAL_PREFIXES)


def resolve_ref(md_path: Path, ref: str) -> Path:
    """Resolve a link target relative to the markdown file, falling back to repo root."""
    ref = ref.strip()
    # Absolute repo path? (starts with /)
    if ref.startswith("/"):
        return REPO_ROOT / ref.lstrip("/")
    # Relative to the markdown file first.
    candidate = (md_path.parent / ref).resolve()
    if candidate.exists():
        return candidate
    # Fallback: relative to repo root (common pattern in our docs).
    return (REPO_ROOT / ref).resolve()


def scan_markdown(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    broken: list[dict] = []
    stale: list[dict] = []

    refs: list[tuple[int, str]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for m in LINK_RE.finditer(line):
            target = m.group(1).strip()
            if is_external(target):
                continue
            refs.append((idx, target))
        for m in FILE_LINE_RE.finditer(line):
            refs.append((idx, m.group(1)))
        for pattern, reason in STALE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                stale.append({"line": idx, "pattern": pattern, "reason": reason, "snippet": line.strip()[:140]})

    for line_no, ref in refs:
        resolved = resolve_ref(md_path, ref)
        if not resolved.exists():
            broken.append({"line": line_no, "ref": ref, "resolved": str(resolved.relative_to(REPO_ROOT)) if REPO_ROOT in resolved.parents else str(resolved)})

    return {
        "path": str(md_path.relative_to(REPO_ROOT)),
        "total_refs": len(refs),
        "broken": broken,
        "stale": stale,
    }


def iter_markdown(roots: Iterable[str]) -> Iterable[Path]:
    for root in roots:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        if base.is_file():
            yield base
            continue
        for p in base.rglob("*.md"):
            # Skip node_modules + generated junk.
            if any(part in {"node_modules", ".next", "dist", "build"} for part in p.parts):
                continue
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="Doc-vs-code truth check")
    ap.add_argument("--paths", nargs="*", default=list(DEFAULT_SCAN_ROOTS))
    ap.add_argument("--strict", action="store_true", help="exit 1 if any broken refs")
    ap.add_argument("--json", dest="json_out", help="write JSON report to path")
    args = ap.parse_args()

    files = list(iter_markdown(args.paths))
    results = [scan_markdown(p) for p in files]

    total_refs = sum(r["total_refs"] for r in results)
    broken_count = sum(len(r["broken"]) for r in results)
    stale_count = sum(len(r["stale"]) for r in results)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "scanned": len(results),
            "total_refs": total_refs,
            "broken_refs": broken_count,
            "stale_hits": stale_count,
            "files": results,
        }, indent=2))

    print(f"Scanned {len(results)} markdown files ({total_refs} refs) in {args.paths}")
    print(f"  Broken refs: {broken_count}")
    print(f"  Stale-language hits: {stale_count}")
    print()

    for r in results:
        if not r["broken"] and not r["stale"]:
            continue
        print(f"── {r['path']}")
        for b in r["broken"]:
            print(f"  ✖ L{b['line']}: {b['ref']}")
        for s in r["stale"]:
            print(f"  ⚠ L{s['line']}: {s['reason']} — {s['snippet']}")
        print()

    if args.strict and broken_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
