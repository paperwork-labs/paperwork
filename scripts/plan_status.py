#!/usr/bin/env python3
"""Print active plans across products with last-reviewed and owner.

Reads apps/studio/src/data/tracker-index.json (run
generate_tracker_index.py first if it's stale).

Usage:
    python3 scripts/plan_status.py [--product axiomfolio]

medallion: ops
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX = REPO_ROOT / "apps" / "studio" / "src" / "data" / "tracker-index.json"


def age_days(iso_date: str | None) -> str:
    if not iso_date:
        return "—"
    try:
        d = date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return "—"
    return f"{(date.today() - d).days}d"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", help="Filter to a single product slug")
    args = parser.parse_args()

    if not INDEX.exists():
        print(
            f"::error::tracker-index.json missing. Run: make tracker-index",
            file=sys.stderr,
        )
        return 1
    data = json.loads(INDEX.read_text(encoding="utf-8"))

    rows: list[tuple[str, str, str, str, str]] = []
    for product in data.get("products", []):
        if args.product and product["slug"] != args.product:
            continue
        for plan in product.get("plans", []):
            rows.append(
                (
                    product["label"],
                    plan["title"],
                    plan.get("status", "—"),
                    age_days(plan.get("last_reviewed")),
                    plan.get("owner", "—") or "—",
                )
            )

    if not rows:
        print("No plans tracked.")
        return 0

    widths = [
        max(len(r[i]) for r in rows + [("Product", "Plan", "Status", "Age", "Owner")])
        for i in range(5)
    ]
    header = ("Product", "Plan", "Status", "Age", "Owner")
    print(" | ".join(h.ljust(widths[i]) for i, h in enumerate(header)))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(" | ".join(r[i].ljust(widths[i]) for i in range(5)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
