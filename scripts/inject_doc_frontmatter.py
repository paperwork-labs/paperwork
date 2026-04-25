#!/usr/bin/env python3
"""Inject standardized YAML frontmatter into every retained doc.

Source-of-truth for owner/domain/doc_kind = the audit JSON at
docs/generated/docs-streamline-2026q2-decisions.json. Idempotent: if a
field is already set we leave it alone (founder edits win), only filling
in missing keys.

Usage:
    python scripts/inject_doc_frontmatter.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DECISIONS = REPO_ROOT / "docs" / "generated" / "docs-streamline-2026q2-decisions.json"

REQUIRED_KEYS = ("owner", "last_reviewed", "doc_kind", "domain", "status")
RETAIN_CLASSIFICATIONS = {"canonical", "unchanged"}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)


def parse_existing(text: str) -> tuple[dict[str, Any], str]:
    """Return (parsed_frontmatter_dict, body_after_frontmatter).

    We use a dumb line-based YAML parser because every existing
    frontmatter we ship is shallow (key: value) and we don't want a
    PyYAML dependency for the inject script.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end() :]
    parsed: dict[str, Any] = {}
    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        parsed[key] = value
    return parsed, body


def render(frontmatter: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key in REQUIRED_KEYS:
        if key in frontmatter:
            lines.append(f"{key}: {frontmatter[key]}")
    extras = sorted(set(frontmatter) - set(REQUIRED_KEYS))
    for key in extras:
        lines.append(f"{key}: {frontmatter[key]}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + body.lstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.loads(DECISIONS.read_text(encoding="utf-8"))
    decisions = data["decisions"]

    today = date.today().isoformat()
    touched: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []

    for entry in decisions:
        if entry["classify"] not in RETAIN_CLASSIFICATIONS:
            continue
        rel = entry["path"]
        path = REPO_ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        text = path.read_text(encoding="utf-8")
        existing, body = parse_existing(text)
        merged: dict[str, Any] = dict(existing)
        merged.setdefault("owner", entry["owner"])
        merged.setdefault(
            "last_reviewed",
            existing.get("last_reviewed") or entry.get("last_meaningful_change") or today,
        )
        if merged["last_reviewed"] in {"unknown", "", None}:
            merged["last_reviewed"] = today
        merged.setdefault("doc_kind", entry["doc_kind"])
        merged.setdefault("domain", entry["domain"])
        merged.setdefault("status", "active")
        new_text = render(merged, body)
        if new_text == text:
            skipped.append(rel)
            continue
        if args.dry_run:
            touched.append(rel)
            continue
        path.write_text(new_text, encoding="utf-8")
        touched.append(rel)

    print(f"Frontmatter injection — {'DRY RUN' if args.dry_run else 'APPLIED'}")
    print(f"  Touched: {len(touched)}")
    for rel in touched:
        print(f"    + {rel}")
    print(f"  Already current: {len(skipped)}")
    if missing:
        print(f"  Skipped {len(missing)} missing (likely auto-generated or on a feature branch):")
        for rel in missing:
            print(f"    ~ {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
