#!/usr/bin/env python3
"""Guard module/class scope Path(__file__).parents[K] in Brain trees."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN = ("apis/brain/app", "apis/brain/scripts")

HINT = "apis/brain/app/services/workstreams_loader.py (_repo_root)"


def _enumerate_files(scan_roots: tuple[str, ...]) -> list[Path]:
    hits: list[Path] = []
    for rel in scan_roots:
        base = REPO_ROOT / rel
        if not base.is_dir():
            raise SystemExit(f"missing `{rel}`")
        hits.extend(sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts))

    hits.sort(key=lambda q: q.as_posix())
    return hits


def _parents_hits(rhs: ast.AST | None) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []

    if rhs is None:
        return rows

    for node in ast.walk(rhs):
        if not isinstance(node, ast.Subscript):
            continue

        if isinstance(node.slice, ast.Constant):
            value = getattr(node.slice, "value", None)

            if isinstance(value, int):
                idx = int(value)

                attrs = isinstance(node.value, ast.Attribute) and node.value.attr == "parents"

                if attrs:
                    condensed = "".join(ast.unparse(node).split())

                    if "__file__" in condensed:
                        rows.append((node.lineno, idx))

    return rows


def _mitigate(rhs: ast.AST, idx: int) -> bool:
    if idx <= 3:
        return True
    text = ast.unparse(rhs)
    low = text.lower()
    if "os.environ" in low or "repo_root" in text or "REPO_ROOT" in text:
        return True

    for node in ast.walk(rhs):
        if isinstance(node, ast.For):
            itext = ast.unparse(node.iter)
            if getattr(node.iter, "attr", "") == "parents" or ".parents" in itext.replace(
                " ",
                "",
            ):
                return True

    for node in ast.walk(rhs):
        if isinstance(node, ast.Compare):
            snap = ast.unparse(node)
            if "len(" in snap and "parents" in snap:
                return True

    for node in ast.walk(rhs):
        if isinstance(node, ast.Try):
            names: list[str] = []
            for handler in node.handlers:
                ht = handler.type
                if ht is None:
                    continue
                if isinstance(ht, ast.Tuple):
                    for elt in ht.elts:
                        if isinstance(elt, ast.Name):
                            names.append(elt.id)

                elif isinstance(ht, ast.Name):
                    names.append(ht.id)

            body_txt = "".join(ast.unparse(n) for n in node.body)
            if "IndexError" in names and ".parents[" in body_txt:
                return True

    return False


def _consume_rhs(rhs: ast.AST | None, rel: str, errors: list[str]) -> None:
    if rhs is None:
        return

    for lineno, k in _parents_hits(rhs):
        if k < 4:
            continue

        if _mitigate(rhs, k):
            continue
        errors.append(f"{rel}:{lineno}: parents[{k}] risky at import scope -> {HINT}")


def _walk_block(stmts: list[ast.stmt], rel: str, errors: list[str]) -> None:
    for st in stmts:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            if getattr(st, "value", None) is None:
                continue
            _consume_rhs(st.value, rel, errors)

        elif isinstance(st, ast.Expr):
            _consume_rhs(getattr(st, "value", None), rel, errors)

        elif isinstance(st, ast.ClassDef):
            _walk_block(st.body, rel, errors)

        elif isinstance(st, ast.If):
            _walk_block(st.body, rel, errors)

            _walk_block(st.orelse, rel, errors)

        elif isinstance(st, ast.Try):
            _walk_block(st.body, rel, errors)

            for handler in st.handlers:
                _walk_block(handler.body, rel, errors)

            _walk_block(st.orelse, rel, errors)

            _walk_block(st.finalbody, rel, errors)

        elif isinstance(st, (ast.With, ast.AsyncWith)):
            _walk_block(st.body, rel, errors)

        elif isinstance(st, (ast.For, ast.AsyncFor, ast.While)):
            _walk_block(st.body, rel, errors)
            _walk_block(st.orelse, rel, errors)
        elif hasattr(ast, "Match") and isinstance(st, ast.Match):
            for case in st.cases:
                _walk_block(case.body, rel, errors)


def _check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")

    rel = path.relative_to(REPO_ROOT).as_posix()

    tree = ast.parse(text, filename=rel)

    errors: list[str] = []

    _walk_block(tree.body, rel, errors)

    return errors


def main(argv: list[str]) -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument("--roots", nargs="*", default=None)

    args = parser.parse_args(argv)

    roots = tuple(args.roots) if args.roots else DEFAULT_SCAN

    failures = []

    for path in _enumerate_files(roots):
        failures.extend(_check_file(path))

    if failures:
        print("parents import-safety failures:", file=sys.stderr)

        for line in failures:
            print(line, file=sys.stderr)

        return 1

    print("check_parents_import_safety: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
