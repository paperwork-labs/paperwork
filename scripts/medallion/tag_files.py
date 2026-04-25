#!/usr/bin/env python3
"""Apply `medallion: <layer>` docstring tag to every .py file in an app.

Track D — this is the repo-root, parametric version that reads
scripts/medallion/apps.yaml. Pass --app-dir apis/<backend> to target a
specific app. Zero behavior change, idempotent.

Usage:
    python scripts/medallion/tag_files.py --app-dir apis/axiomfolio
    python scripts/medallion/tag_files.py --app-dir apis/brain --apply
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import REPO_ROOT, AppConfig, load_config, resolve_app_name  # noqa: E402

TAG_PREFIX = "medallion:"


def has_module_docstring(source: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, None
    if not tree.body:
        return False, None
    first = tree.body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return True, first.value.value
    return False, None


def update_file(path: Path, layer: str, apply: bool) -> tuple[str, str]:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        return "error", f"read fail: {e}"

    has_doc, doc = has_module_docstring(source)
    new_tag = f"{TAG_PREFIX} {layer}"

    if has_doc and doc is not None and TAG_PREFIX in doc:
        for line in doc.splitlines():
            stripped = line.strip()
            if stripped.startswith(TAG_PREFIX):
                existing_layer = stripped[len(TAG_PREFIX):].strip()
                if existing_layer == layer:
                    return "skipped", "already tagged correctly"
                new_doc = doc.replace(stripped, new_tag)
                new_source = source.replace(doc, new_doc, 1)
                if apply:
                    path.write_text(new_source, encoding="utf-8")
                return "updated", f"{existing_layer} -> {layer}"

    if has_doc and doc is not None:
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
        _ = quote
        return "added", "tag appended to existing docstring"

    lines = source.splitlines(keepends=True)
    insert_at = 0
    while insert_at < len(lines):
        line = lines[insert_at].strip()
        if line.startswith("#!"):
            insert_at += 1
            continue
        if line.startswith("# -*- coding") or line.startswith("# coding"):
            insert_at += 1
            continue
        break
    new_docstring = f'"""{new_tag}"""\n'
    suffix = ""
    if insert_at < len(lines) and lines[insert_at].strip() != "":
        suffix = "\n"
    new_lines = lines[:insert_at] + [new_docstring + suffix] + lines[insert_at:]
    new_source = "".join(new_lines)
    if apply:
        path.write_text(new_source, encoding="utf-8")
    return "added", "new docstring inserted at true module-docstring position"


def run(cfg: AppConfig, apply: bool, verbose: bool) -> int:
    if not cfg.services_root.is_dir():
        print(f"[{cfg.name}] error: {cfg.services_root} not found", file=sys.stderr)
        return 2

    counts = {"added": 0, "updated": 0, "skipped": 0, "error": 0, "unmapped": 0}
    by_layer: dict[str, int] = {}

    for py_file in sorted(cfg.services_root.rglob("*.py")):
        rel = py_file.relative_to(REPO_ROOT)
        layer = cfg.classify(py_file)
        if layer is None:
            counts["unmapped"] += 1
            if verbose:
                print(f"  unmapped: {rel}")
            continue
        by_layer[layer] = by_layer.get(layer, 0) + 1
        status, msg = update_file(py_file, layer, apply)
        counts[status] += 1
        if verbose or status == "error":
            print(f"  {status:8s}  {rel}  ({layer})  {msg}")

    print()
    print(f"[{cfg.name}] {'DRY RUN' if not apply else 'APPLIED'}")
    print(f"  added:    {counts['added']}")
    print(f"  updated:  {counts['updated']}")
    print(f"  skipped:  {counts['skipped']}")
    print(f"  errors:   {counts['error']}")
    print(f"  unmapped: {counts['unmapped']}")
    print("Files by layer:")
    for layer in ("bronze", "silver", "gold", "execution", "ops"):
        print(f"  {layer:10s} {by_layer.get(layer, 0)}")
    return 0 if counts["error"] == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--app-dir",
        required=True,
        help="App directory relative to repo root, e.g. apis/axiomfolio",
    )
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    try:
        name = resolve_app_name(args.app_dir)
        cfg = load_config(name)
    except (FileNotFoundError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return run(cfg, apply=args.apply, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
