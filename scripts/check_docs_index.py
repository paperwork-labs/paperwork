#!/usr/bin/env python3
"""Docs index drift checker.

Track N — fails CI when docs/_index.yaml references a file that does not
exist (or vice versa: a doc on disk that isn't indexed). Keep the agent-
facing taxonomy honest.

Usage:
    python3 scripts/check_docs_index.py              # hard fail on drift
    python3 scripts/check_docs_index.py --warn-only  # print but pass
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX = REPO_ROOT / "docs" / "_index.yaml"
DOCS_DIR = REPO_ROOT / "docs"

# Files under docs/ that we intentionally don't list in _index.yaml (they
# are internal notes, archives, or work-in-progress that shouldn't show up
# in /admin/docs yet).
EXCLUDED_SUBDIRS = {
    "archive",
    "templates",
    "handoffs",
    # The axiomfolio/ subtree is an internal migration snapshot — lots of
    # plan drafts, design-system pages, and per-quarter audits. Not the
    # target of /admin/docs yet. If you need it indexed, add a specific
    # entry in docs/_index.yaml instead of bulk-exposing the whole tree.
    "axiomfolio",
    # Internal philosophy READMEs are CODEOWNERS-locked but only the
    # individual philosophy docs need to appear in /admin/docs. The
    # README is the index page for the folder itself.
}
EXCLUDED_FILES = {
    "docs/SLACK_SPRINT_TEMPLATE.md",
    "docs/PHASE2-COMPOSER-HANDOFFS.md",
    "docs/NEXTJS_MIGRATION_2026Q3.md",
    # Auto-generated from docs/axiomfolio/brain/axiomfolio_tools.yaml by
    # scripts/generate_axiomfolio_integration_doc.py — surfaced in /admin/docs
    # via a generated entry, not the hand-maintained _index.yaml.
    "docs/AXIOMFOLIO_INTEGRATION.generated.md",
    # Folder-level READMEs that document the schema for agents but
    # aren't standalone docs we want to surface in /admin/docs.
    "docs/sprints/README.md",
}


def load_indexed() -> list[dict]:
    data = yaml.safe_load(INDEX.read_text(encoding="utf-8"))
    return data.get("docs") or []


def disk_docs() -> set[str]:
    found: set[str] = set()
    for p in DOCS_DIR.rglob("*.md"):
        if any(part.startswith(".") for part in p.relative_to(REPO_ROOT).parts):
            continue
        rel = p.relative_to(REPO_ROOT).as_posix()
        if any(rel.startswith(f"docs/{excl}/") for excl in EXCLUDED_SUBDIRS):
            continue
        if rel in EXCLUDED_FILES:
            continue
        found.add(rel)
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn-only", action="store_true")
    args = ap.parse_args()

    if not INDEX.is_file():
        print(f"error: {INDEX} missing", file=sys.stderr)
        return 2

    indexed = load_indexed()
    indexed_paths = {entry["path"] for entry in indexed}

    missing_on_disk: list[str] = []
    for entry in indexed:
        full = REPO_ROOT / entry["path"]
        if not full.is_file():
            missing_on_disk.append(entry["path"])

    on_disk = disk_docs()
    not_indexed = sorted(on_disk - indexed_paths)

    had_drift = False

    if missing_on_disk:
        had_drift = True
        print("✗ Docs listed in docs/_index.yaml but missing on disk:")
        for p in missing_on_disk:
            print(f"  {p}")
        print()

    if not_indexed:
        had_drift = True
        print("✗ Markdown files on disk but not in docs/_index.yaml:")
        for p in not_indexed:
            print(f"  {p}")
        print()
        print("  → add them to docs/_index.yaml, or list them in EXCLUDED_FILES in")
        print("    scripts/check_docs_index.py if they're intentionally internal.")

    if not had_drift:
        print(
            f"✓ docs/_index.yaml matches disk "
            f"({len(indexed)} indexed, {len(on_disk)} on-disk)"
        )
        return 0

    return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
