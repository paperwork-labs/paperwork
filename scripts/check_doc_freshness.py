#!/usr/bin/env python3
"""Scan docs/ for `last_reviewed` staleness (default threshold 90 days).

Excludes archive, philosophy, templates, generated, _drafts, and
frontmatter with status deprecated|generated. Missing or invalid
`last_reviewed` counts as stale.

Use --warn-only to report without failing (non-zero) until the org is
used to the check.

medallion: ops
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)

EXEMPT_PREFIX = frozenset({"archive", "philosophy", "templates", "generated", "_drafts"})


def parse_frontmatter_shallow(text: str) -> tuple[dict[str, Any], str]:
    """Line-based YAML for flat key: value frontmatter (no PyYAML)."""
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


def path_is_exempt(rel: Path) -> bool:
    """rel is path relative to docs/ (e.g. axiomfolio/README.md)."""
    parts = rel.parts
    if not parts:
        return False
    if parts[0] in EXEMPT_PREFIX:
        return True
    if "_drafts" in parts:
        return True
    return False


def status_is_exempt(status: str) -> bool:
    s = status.strip().lower()
    return s in ("deprecated", "generated")


def parse_last_reviewed(value: str) -> date | None:
    v = value.strip()
    if not v or v.lower() in ("unknown", "n/a", "na", "tbd", "—", "-"):
        return None
    v = v.strip('"').strip("'")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--warn-only",
        action="store_true",
        help="Print stale / summary but always exit 0 unless the script errors.",
    )
    p.add_argument(
        "--threshold-days",
        type=int,
        default=90,
        help="Staleness threshold in days (default: 90).",
    )
    args = p.parse_args()

    today = date.today()
    threshold: int = args.threshold_days

    rows: list[dict[str, Any]] = []

    for md in sorted(DOCS.rglob("*.md")):
        try:
            rel = md.relative_to(DOCS)
        except ValueError:
            continue
        if path_is_exempt(rel):
            continue
        rel_repo = f"docs/{rel.as_posix()}"
        try:
            text = md.read_text(encoding="utf-8")
        except OSError as e:
            print(f"::warning::unreadable {rel_repo}: {e}", file=sys.stderr)
            continue

        parsed, _ = parse_frontmatter_shallow(text)
        st = str(parsed.get("status", ""))
        if status_is_exempt(st):
            continue

        owner = str(parsed.get("owner", "")).strip() or "—"
        raw_lr = str(parsed.get("last_reviewed", "")).strip()
        d = parse_last_reviewed(raw_lr) if raw_lr else None
        if d is not None:
            age_days = (today - d).days
            lr_display = d.isoformat()
        else:
            age_days = None
            lr_display = raw_lr or "—"

        rows.append(
            {
                "path": rel_repo,
                "last_reviewed": lr_display,
                "age_days": age_days,
                "owner": owner,
            }
        )

    def is_stale(r: dict[str, Any]) -> bool:
        ad = r["age_days"]
        if ad is None:
            return True
        return ad > threshold

    def sort_key(r: dict[str, Any]) -> tuple:
        ad = r["age_days"]
        k = 10**9 if ad is None else ad
        return (-k, r["path"])

    rows.sort(key=sort_key)

    stale = [r for r in rows if is_stale(r)]

    # Summary table: all non-exempt docs, oldest first
    w_path = max(len("path"), max((len(x["path"]) for x in rows), default=0))
    w_lr = max(len("last_reviewed"), max((len(str(x["last_reviewed"])) for x in rows), default=0))
    w_age = max(len("age_days"), 8)
    w_owner = max(len("owner"), max((len(x["owner"]) for x in rows), default=0))

    header = f"{'path':<{w_path}}  {'last_reviewed':<{w_lr}}  {'age_days':>{w_age}}  {'owner':<{w_owner}}"
    sep = f"{'-' * w_path}  {'-' * w_lr}  {'-' * w_age}  {'-' * w_owner}"
    print("Docs freshness (last_reviewed)")
    print(f"  today: {today.isoformat()}  threshold: {threshold}d  scoped: {DOCS} (with exemptions)")
    print()
    print(header)
    print(sep)
    for r in rows:
        ad = r["age_days"]
        age_str = "missing" if ad is None else str(ad)
        print(
            f"{r['path']:<{w_path}}  {str(r['last_reviewed']):<{w_lr}}  {age_str:>{w_age}}  {r['owner']:<{w_owner}}"
        )
    print()
    print(f"  Total scanned: {len(rows)}  Stale (>{threshold}d or missing date): {len(stale)}")

    if stale:
        print()
        print("Stale or undated docs (failed check unless --warn-only):")
        for r in sorted(stale, key=sort_key):
            ad = r["age_days"]
            age_h = "missing/invalid last_reviewed" if ad is None else f"{ad}d old"
            print(f"  - {r['path']}: {age_h}")
        if not args.warn_only:
            print(
                f"\n::error::{len(stale)} doc(s) exceed {threshold} days or lack last_reviewed. "
                f"Update frontmatter or use exempt paths/status.",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
