#!/usr/bin/env python3
"""Enforce a baseline structure on every runbook.

A runbook is any markdown file under `docs/` with frontmatter
`doc_kind: runbook`. Every such file must include the canonical
sections defined in `REQUIRED_SECTIONS` (case-insensitive prefix match
against any H2 heading).

By default the script runs in `--warn-only` mode (exit 0) so it can
land as a CI gate without immediately blocking PRs. Pass `--strict`
once the existing runbooks have all been migrated to the new template.

medallion: ops
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)
H2_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)

REQUIRED_SECTIONS: list[tuple[str, list[str]]] = [
    ("when_fires", ["when this fires", "when this runbook fires", "when to use", "trigger"]),
    ("triage", ["triage", "quick triage"]),
    ("verification", ["verification", "smoke test", "verify"]),
    ("rollback", ["rollback", "recovery", "undo"]),
    ("escalation", ["escalation", "on-call", "escalate"]),
    ("post_incident", ["post-incident", "after the incident", "post mortem", "postmortem"]),
]

EXEMPT_PATHS: set[str] = {
    # Reference-only docs that have `doc_kind: runbook` for taxonomy
    # but aren't strict ops procedures yet — migrate over time.
}


def _frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("-") and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip("'\"")
    return out


def _h2_titles(body: str) -> list[str]:
    return [m.group("title").strip().lower() for m in H2_RE.finditer(body)]


def find_runbooks() -> Iterable[Path]:
    for path in DOCS_DIR.rglob("*.md"):
        if path.name.lower() == "readme.md":
            continue
        if "archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        fm = _frontmatter(text)
        if fm.get("doc_kind") == "runbook":
            yield path


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    titles = _h2_titles(text)
    missing: list[str] = []
    for slug, aliases in REQUIRED_SECTIONS:
        if any(any(t.startswith(alias) for alias in aliases) for t in titles):
            continue
        missing.append(slug)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any runbook is missing a required section.",
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Always exit 0 (default). Useful for the warm-up CI window.",
    )
    args = parser.parse_args()

    issues: list[tuple[Path, list[str]]] = []
    runbooks = sorted(find_runbooks())
    for rb in runbooks:
        rel = str(rb.relative_to(REPO_ROOT))
        if rel in EXEMPT_PATHS:
            continue
        missing = check(rb)
        if missing:
            issues.append((rb, missing))

    print(f"Scanned {len(runbooks)} runbooks under docs/.")
    if not issues:
        print("OK — every runbook has the required sections.")
        return 0

    print(f"\n{len(issues)} runbook(s) missing required sections:\n")
    for path, missing in issues:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}")
        for slug in missing:
            print(f"    - missing: {slug}")
    print(
        f"\nTemplate: docs/RUNBOOK_TEMPLATE.md\n"
        f"Each runbook should have an H2 for: when_fires, triage, verification, "
        f"rollback, escalation, post_incident.\n"
    )

    if args.strict and not args.warn_only:
        return 1
    print("(warn-only mode — exiting 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
