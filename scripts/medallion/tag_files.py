#!/usr/bin/env python3
"""
Phase 0.A — Medallion docstring tagger.

Applies `medallion: <layer>` module-level docstring to every .py file under
backend/services/ based on a directory-to-layer mapping.

Zero behavior change. Idempotent: re-running updates the layer tag but doesn't
break existing docstrings. Safe to run while services are deployed.

Usage:
    python scripts/medallion/tag_files.py --apply   # writes changes
    python scripts/medallion/tag_files.py           # dry run, shows diff summary
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SERVICES = REPO_ROOT / "backend" / "services"

# Directory → medallion layer mapping.
# Based on docs/handoffs/2026-04-22-medallion-wave-0-stage-setting.md §3-4.
LAYER_MAP: dict[str, str] = {
    # Bronze: raw broker I/O, external data ingestion.
    "bronze": "bronze",
    "aggregator": "bronze",
    # Silver: enrichment, indicators, analytics, cross-broker reconciliation.
    "market": "silver",
    "tax": "silver",
    "corporate_actions": "silver",
    "data_quality": "silver",
    "intelligence": "silver",
    "symbols": "silver",
    # Gold: strategy outputs, picks, scoring, backtests, narratives.
    "gold": "gold",
    "strategy": "gold",
    "picks": "gold",
    "backtest": "gold",
    "ml": "gold",
    "narrative": "gold",
    "signals": "gold",
    "risk": "gold",  # Note: some risk logic touches execution; see MEDALLION_AUDIT.md
    # Execution: fourth layer (per §6.6) — reads gold, writes orders to brokers.
    "execution": "execution",
    # Ops: cross-cutting infra, not part of medallion data flow.
    "agent": "ops",
    "billing": "ops",
    "brain": "ops",
    "clients": "ops",
    "connections": "ops",
    "core": "ops",
    "deploys": "ops",
    "engine": "ops",
    "gdpr": "ops",
    "multitenant": "ops",
    "notifications": "ops",
    "oauth": "ops",
    "observability": "ops",
    "ops": "ops",
    "pipeline": "ops",
    "security": "ops",
    "share": "ops",
}

# Portfolio/ split: broker-facing sync services are bronze; analytics are silver.
PORTFOLIO_BRONZE_PATTERNS = (
    "portfolio/ibkr/",
    "portfolio/schwab_sync_service.py",
    "portfolio/schwab/",
    "portfolio/tastytrade_sync_service.py",
    "portfolio/tastytrade/",
    "portfolio/broker_sync_service.py",
)


def classify(path: Path) -> str | None:
    """Return medallion layer for a given .py file, or None to skip."""
    rel = path.relative_to(SERVICES).as_posix()
    top = rel.split("/", 1)[0]

    if "/" not in rel:
        return "ops"

    if top == "portfolio":
        if any(rel.startswith(p) or p in rel for p in PORTFOLIO_BRONZE_PATTERNS):
            return "bronze"
        return "silver"

    return LAYER_MAP.get(top)


TAG_PREFIX = "medallion:"


def has_module_docstring(source: str) -> tuple[bool, str | None]:
    """(has_docstring, existing_docstring_text_or_None)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, None
    if not tree.body:
        return False, None
    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return True, first.value.value
    return False, None


def update_file(path: Path, layer: str, apply: bool) -> tuple[str, str]:
    """Return (status, message). Status: 'added', 'updated', 'skipped', 'error'."""
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        return "error", f"read fail: {e}"

    has_doc, doc = has_module_docstring(source)
    new_tag = f"{TAG_PREFIX} {layer}"

    if has_doc and doc is not None and TAG_PREFIX in doc:
        # Already tagged. Check if layer matches; update if not.
        for line in doc.splitlines():
            stripped = line.strip()
            if stripped.startswith(TAG_PREFIX):
                existing_layer = stripped[len(TAG_PREFIX):].strip()
                if existing_layer == layer:
                    return "skipped", "already tagged correctly"
                # Layer drift — rewrite.
                new_doc = doc.replace(stripped, new_tag)
                new_source = source.replace(doc, new_doc, 1)
                if apply:
                    path.write_text(new_source, encoding="utf-8")
                return "updated", f"{existing_layer} -> {layer}"

    if has_doc and doc is not None:
        # Existing docstring but no tag. Use AST line info to splice tag in
        # just before the closing triple-quote, preserving content exactly.
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return "error", f"reparse failed: {e}"
        first_expr = tree.body[0]
        end_line = first_expr.end_lineno
        if end_line is None:
            return "error", "no end_lineno on docstring"
        lines = source.splitlines(keepends=True)
        closing_line = lines[end_line - 1]
        idx = closing_line.rfind('"""')
        quote = '"""'
        if idx == -1:
            idx = closing_line.rfind("'''")
            quote = "'''"
        if idx == -1:
            return "error", "could not locate closing triple-quote"
        prefix = closing_line[:idx]
        suffix = closing_line[idx:]
        if prefix.rstrip() == "":
            new_closing = f"\n{new_tag}\n{prefix}{suffix}"
        else:
            new_closing = f"{prefix.rstrip()}\n\n{new_tag}\n{suffix}"
        lines[end_line - 1] = new_closing
        new_source = "".join(lines)
        if apply:
            path.write_text(new_source, encoding="utf-8")
        return "added", "tag appended to existing docstring"

    # No docstring. Insert new one at top, preserving shebang and __future__.
    lines = source.splitlines(keepends=True)
    insert_at = 0
    while insert_at < len(lines):
        l = lines[insert_at].strip()
        if l.startswith("#!") or l.startswith("#") or l == "" or l.startswith("from __future__"):
            insert_at += 1
            continue
        break
    new_docstring = f'"""{new_tag}"""\n'
    new_lines = lines[:insert_at] + [new_docstring] + lines[insert_at:]
    new_source = "".join(new_lines)
    if apply:
        path.write_text(new_source, encoding="utf-8")
    return "added", "new docstring inserted"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not SERVICES.is_dir():
        print(f"error: {SERVICES} not found", file=sys.stderr)
        return 2

    counts: dict[str, int] = {"added": 0, "updated": 0, "skipped": 0, "error": 0, "unmapped": 0}
    by_layer: dict[str, int] = {}

    for py_file in sorted(SERVICES.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        layer = classify(py_file)
        if layer is None:
            counts["unmapped"] += 1
            if args.verbose:
                print(f"  unmapped: {rel}")
            continue
        by_layer[layer] = by_layer.get(layer, 0) + 1
        status, msg = update_file(py_file, layer, args.apply)
        counts[status] += 1
        if args.verbose or status in ("error",):
            print(f"  {status:8s}  {rel}  ({layer})  {msg}")

    print()
    print(f"{'DRY RUN' if not args.apply else 'APPLIED'}")
    print(f"  added:    {counts['added']}")
    print(f"  updated:  {counts['updated']}")
    print(f"  skipped:  {counts['skipped']}")
    print(f"  errors:   {counts['error']}")
    print(f"  unmapped: {counts['unmapped']}")
    print()
    print("Files by layer:")
    for layer in ("bronze", "silver", "gold", "execution", "ops"):
        print(f"  {layer:10s} {by_layer.get(layer, 0)}")
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
