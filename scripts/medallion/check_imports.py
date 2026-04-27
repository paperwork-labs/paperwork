#!/usr/bin/env python3
"""Medallion import-layer CI gate (parametric over --app-dir).

Track D — this is the repo-root version. Reads scripts/medallion/apps.yaml
so we can gate filefree / launchfree / brain / axiomfolio from one
workflow without duplicating mappings.

Rules (bronze < silver < gold < execution; ops is escape hatch):
    bronze/    may import from: stdlib, ops/*
    silver/    may import from: bronze/, stdlib, ops/*
    gold/      may import from: silver/, bronze/, stdlib, ops/*
    execution/ may import from: gold/, silver/, bronze/, stdlib, ops/*
    ops/       may import from: anywhere (escape hatch)

Usage:
    python scripts/medallion/check_imports.py --app-dir apis/axiomfolio --strict
    python scripts/medallion/check_imports.py --app-dir apis/brain --stats --strict
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ALLOW, REPO_ROOT, AppConfig, load_config, resolve_app_name  # noqa: E402

TAG_RE = re.compile(r"^\s*medallion:\s*(bronze|silver|gold|execution|ops)\s*$", re.MULTILINE)
WAIVER_RE = re.compile(r"#\s*medallion:\s*allow\b")


def read_layer(path: Path) -> str | None:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    if not tree.body:
        return None
    first = tree.body[0]
    if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant):
        return None
    docstring = first.value.value
    if not isinstance(docstring, str):
        return None
    m = TAG_RE.search(docstring)
    return m.group(1) if m else None


def module_to_file(cfg: AppConfig, module: str) -> Path | None:
    if not module.startswith(cfg.import_prefix):
        return None
    rel = module[len(cfg.import_prefix):].replace(".", "/")
    candidates = [
        cfg.services_root / f"{rel}.py",
        cfg.services_root / rel / "__init__.py",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def get_imports(cfg: AppConfig, source: str) -> list[tuple[int, str, str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    imports: list[tuple[int, str, str]] = []
    prefix_bare = cfg.import_prefix.rstrip(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(prefix_bare):
                    lno = node.lineno
                    raw = lines[lno - 1] if lno <= len(lines) else ""
                    imports.append((lno, alias.name, raw))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(prefix_bare):
                lno = node.lineno
                raw = lines[lno - 1] if lno <= len(lines) else ""
                imports.append((lno, node.module, raw))
    return imports


def has_waiver(source_lines: list[str], import_line: int) -> bool:
    idx = import_line - 1
    if 0 <= idx < len(source_lines) and WAIVER_RE.search(source_lines[idx]):
        return True
    if 0 < idx < len(source_lines) and WAIVER_RE.search(source_lines[idx - 1]):
        return True
    return False


def run(cfg: AppConfig, *, stats: bool, warn_only: bool, verbose: bool) -> int:
    if not cfg.services_root.is_dir():
        print(f"[{cfg.name}] error: {cfg.services_root} not found", file=sys.stderr)
        return 2

    file_layer: dict[Path, str] = {}
    untagged: list[Path] = []
    for py in sorted(cfg.services_root.rglob("*.py")):
        layer = read_layer(py)
        if layer is None:
            untagged.append(py)
        else:
            file_layer[py] = layer

    if untagged:
        print(
            f"[{cfg.name}] error: {len(untagged)} .py files under {cfg.services_root.relative_to(REPO_ROOT)} "
            f"missing medallion tag. Run scripts/medallion/tag_files.py --app-dir {cfg.app_dir.relative_to(REPO_ROOT)} --apply.",
            file=sys.stderr,
        )
        for p in untagged[:10]:
            print(f"  {p.relative_to(REPO_ROOT)}", file=sys.stderr)
        if len(untagged) > 10:
            print(f"  ... and {len(untagged) - 10} more", file=sys.stderr)
        return 2

    violations: list[tuple[Path, int, str, str, str]] = []
    waivers_used = 0
    imports_checked = 0

    for py, src_layer in file_layer.items():
        try:
            source = py.read_text(encoding="utf-8")
        except Exception:
            continue
        source_lines = source.splitlines()
        for lineno, module, _raw in get_imports(cfg, source):
            imports_checked += 1
            target = module_to_file(cfg, module)
            if target is None:
                continue
            dst_layer = file_layer.get(target)
            if dst_layer is None:
                continue
            allowed = ALLOW.get(src_layer, set())
            if dst_layer == src_layer:
                continue
            if dst_layer in allowed:
                continue
            if has_waiver(source_lines, lineno):
                waivers_used += 1
                continue
            violations.append((py, lineno, src_layer, dst_layer, module))

    if stats:
        by_layer: dict[str, int] = {}
        for layer in file_layer.values():
            by_layer[layer] = by_layer.get(layer, 0) + 1
        print(f"[{cfg.name}] Files by layer:")
        for layer in ("bronze", "silver", "gold", "execution", "ops"):
            print(f"  {layer:10s} {by_layer.get(layer, 0)}")
        print(f"[{cfg.name}] Imports checked: {imports_checked}")
        print(f"[{cfg.name}] Waivers used:    {waivers_used}")
        print()

    if not violations:
        print(
            f"[{cfg.name}] ✓ Medallion imports clean "
            f"({imports_checked} imports, {waivers_used} waivers)"
        )
        return 0

    print(f"[{cfg.name}] ✗ {len(violations)} medallion import violations:")
    print()
    for py, lineno, src_layer, dst_layer, module in violations:
        rel = py.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}  [{src_layer}] → [{dst_layer}]  {module}")
    print()
    print(f"  bronze may import from: {sorted(ALLOW['bronze'])} + stdlib")
    print(f"  silver may import from: {sorted(ALLOW['silver'])} + stdlib")
    print(f"  gold   may import from: {sorted(ALLOW['gold'])} + stdlib")
    print(f"  execution may import from: {sorted(ALLOW['execution'])} + stdlib")
    print()
    print("  Waive a specific violation with `# medallion: allow <reason>`")
    print("  on the import line or the line immediately before.")
    return 0 if warn_only else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--app-dir",
        required=True,
        help="App directory relative to repo root, e.g. apis/axiomfolio",
    )
    ap.add_argument("--stats", action="store_true")
    ap.add_argument(
        "--warn-only",
        action="store_true",
        help="Exit 0 even when import violations are found (local dev only; do not use in CI).",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when violations are found. This is the default; pass explicitly in CI for clarity.",
    )
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.strict and args.warn_only:
        ap.error("Cannot combine --strict and --warn-only")
    try:
        name = resolve_app_name(args.app_dir)
        cfg = load_config(name)
    except (FileNotFoundError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return run(cfg, stats=args.stats, warn_only=args.warn_only, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
