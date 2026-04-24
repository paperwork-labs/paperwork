#!/usr/bin/env python3
"""
Phase 0.B — Medallion import-layer CI gate.

Parses every .py file under app/services/, reads its `medallion: <layer>`
docstring tag, walks all imports, and asserts every cross-module import
respects the layer hierarchy.

Rules (bronze < silver < gold < execution; ops is escape hatch):
    bronze/    may import from: stdlib, services/clients/, services/ops/*
    silver/    may import from: bronze/, stdlib, services/clients/, services/ops/*
    gold/      may import from: silver/, bronze/, stdlib, services/ops/*
    execution/ may import from: gold/, silver/, bronze/, stdlib, services/ops/*
    ops/       may import from: anywhere (escape hatch)

Exception mechanism:
    Add `# medallion: allow <reason>` on the import line or the line immediately
    preceding it to waive a specific violation. Use sparingly; each waiver is
    reviewed during Wave 0.D cleanup.

Usage:
    python scripts/medallion/check_imports.py              # CI mode
    python scripts/medallion/check_imports.py --stats      # + layer summary
    python scripts/medallion/check_imports.py --warn-only  # never exit 1

Exit codes:
    0  no violations (or --warn-only)
    1  violations found (CI failure)
    2  configuration error
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SERVICES = REPO_ROOT / "app" / "services"
SERVICES_IMPORT_PREFIX = "app.services."

# Import rules: layer → set of layers it may import from.
# "stdlib" (anything not under services_import_prefix) is always allowed.
ALLOW: dict[str, set[str]] = {
    "bronze":    {"ops"},
    "silver":    {"bronze", "ops"},
    "gold":      {"silver", "bronze", "ops"},
    "execution": {"gold", "silver", "bronze", "ops"},
    "ops":       {"bronze", "silver", "gold", "execution", "ops"},  # escape hatch
}

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


def module_to_file(module: str) -> Path | None:
    """Resolve `app.services.foo.bar` → filesystem Path to foo/bar.py or foo/bar/__init__.py."""
    if not module.startswith(SERVICES_IMPORT_PREFIX):
        return None
    rel = module[len(SERVICES_IMPORT_PREFIX):].replace(".", "/")
    candidates = [
        SERVICES / f"{rel}.py",
        SERVICES / rel / "__init__.py",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def get_imports(source: str) -> list[tuple[int, str, str]]:
    """Return [(lineno, module_path, raw_import_line), ...] for all services-touching imports."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    imports: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(SERVICES_IMPORT_PREFIX.rstrip(".")):
                    lno = node.lineno
                    raw = lines[lno - 1] if lno <= len(lines) else ""
                    imports.append((lno, alias.name, raw))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(SERVICES_IMPORT_PREFIX.rstrip(".")):
                lno = node.lineno
                raw = lines[lno - 1] if lno <= len(lines) else ""
                imports.append((lno, node.module, raw))
    return imports


def has_waiver(source_lines: list[str], import_line: int) -> bool:
    # Waiver can be on same line or line immediately preceding.
    idx = import_line - 1
    if 0 <= idx < len(source_lines) and WAIVER_RE.search(source_lines[idx]):
        return True
    if 0 < idx < len(source_lines) and WAIVER_RE.search(source_lines[idx - 1]):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--warn-only", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not SERVICES.is_dir():
        print(f"error: {SERVICES} not found", file=sys.stderr)
        return 2

    file_layer: dict[Path, str] = {}
    untagged: list[Path] = []
    for py in sorted(SERVICES.rglob("*.py")):
        layer = read_layer(py)
        if layer is None:
            untagged.append(py)
        else:
            file_layer[py] = layer

    if untagged:
        print(f"error: {len(untagged)} .py files under app/services/ missing "
              f"medallion tag. Run scripts/medallion/tag_files.py --apply.",
              file=sys.stderr)
        for p in untagged[:10]:
            print(f"  {p.relative_to(REPO_ROOT)}", file=sys.stderr)
        if len(untagged) > 10:
            print(f"  ... and {len(untagged) - 10} more", file=sys.stderr)
        return 2

    violations: list[tuple[Path, int, str, str, str]] = []  # (file, line, src_layer, dst_layer, import_module)
    waivers_used = 0
    imports_checked = 0

    for py, src_layer in file_layer.items():
        try:
            source = py.read_text(encoding="utf-8")
        except Exception:
            continue
        source_lines = source.splitlines()
        for lineno, module, _raw in get_imports(source):
            imports_checked += 1
            target = module_to_file(module)
            if target is None:
                continue
            dst_layer = file_layer.get(target)
            if dst_layer is None:
                continue
            allowed = ALLOW.get(src_layer, set())
            if dst_layer == src_layer:
                continue  # same layer always allowed
            if dst_layer in allowed:
                continue
            if has_waiver(source_lines, lineno):
                waivers_used += 1
                continue
            violations.append((py, lineno, src_layer, dst_layer, module))

    if args.stats:
        by_layer: dict[str, int] = {}
        for layer in file_layer.values():
            by_layer[layer] = by_layer.get(layer, 0) + 1
        print("Files by layer:")
        for layer in ("bronze", "silver", "gold", "execution", "ops"):
            print(f"  {layer:10s} {by_layer.get(layer, 0)}")
        print(f"Imports checked: {imports_checked}")
        print(f"Waivers used:    {waivers_used}")
        print()

    if not violations:
        print(f"✓ Medallion imports clean ({imports_checked} imports, {waivers_used} waivers)")
        return 0

    print(f"✗ {len(violations)} medallion import violations:")
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

    return 0 if args.warn_only else 1


if __name__ == "__main__":
    sys.exit(main())
