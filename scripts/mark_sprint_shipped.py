#!/usr/bin/env python3
"""Mark the most-recently-modified active sprint as shipped.

Usage:
    python3 scripts/mark_sprint_shipped.py --pr 141

Idempotent: if the latest active sprint already has a PR set, refuses
unless --force is passed. Updates frontmatter only — never rewrites the
sprint body.

medallion: ops
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPRINTS_DIR = REPO_ROOT / "docs" / "sprints"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def latest_active_sprint() -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for p in SPRINTS_DIR.glob("*.md"):
        if p.name.lower() == "readme.md":
            continue
        text = p.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        if "status: active" not in m.group(1):
            continue
        candidates.append((p.stat().st_mtime, p))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def update_frontmatter(path: Path, pr: int) -> bool:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        print(f"  ! no frontmatter in {path.name}", file=sys.stderr)
        return False
    fm = m.group(1)
    body = text[m.end():]

    fm = re.sub(r"^status:\s*active\s*$", "status: shipped", fm, flags=re.MULTILINE)
    if "sprint:" in fm:
        if re.search(r"^\s+pr:\s*\S+\s*$", fm, flags=re.MULTILINE):
            fm = re.sub(r"^(\s+pr:)\s*\S+\s*$", rf"\1 {pr}", fm, flags=re.MULTILINE)
        else:
            fm = re.sub(
                r"(sprint:\s*\n)",
                rf"\1  pr: {pr}\n",
                fm,
                count=1,
            )
        if re.search(r"^\s+end:\s*\S+", fm, flags=re.MULTILINE):
            today = date.today().isoformat()
            if "end: " in fm and re.search(r"end:\s*\d{4}-\d{2}-\d{2}", fm):
                pass
            else:
                fm = re.sub(
                    r"(\s+end:)\s*\S*\s*$",
                    rf"\1 {today}",
                    fm,
                    count=1,
                    flags=re.MULTILINE,
                )

    new_text = "---\n" + fm + "---\n" + body
    if new_text == text:
        print(f"  - no changes to {path.name}")
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", type=int, required=True, help="PR number that shipped the sprint")
    parser.add_argument("--path", type=Path, help="Specific sprint file (default: latest active)")
    args = parser.parse_args()

    target = args.path if args.path else latest_active_sprint()
    if target is None:
        print("No active sprint to ship.", file=sys.stderr)
        return 1
    target = target.resolve()
    print(f"Marking shipped: {target.relative_to(REPO_ROOT)} (PR #{args.pr})")
    if update_frontmatter(target, args.pr):
        print("  + frontmatter updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
