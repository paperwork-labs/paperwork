#!/usr/bin/env python3
"""CI guard: every ``scheduler.add_job`` must pass ``misfire_grace_time=``."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _check_add_job_call(node: ast.Call, path: Path) -> str | None:
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "add_job":
        return None
    kw_names = {kw.arg for kw in node.keywords if kw.arg is not None}
    if "misfire_grace_time" in kw_names:
        return None
    return f"{path}:{node.lineno}: add_job(...) missing keyword misfire_grace_time="


def _check_scheduled_job_decorator(dec: ast.expr, path: Path, lineno: int) -> str | None:
    """``@scheduler.scheduled_job(...)`` must include misfire_grace_time."""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute) or func.attr != "scheduled_job":
        return None
    kw_names = {kw.arg for kw in dec.keywords if kw.arg is not None}
    if "misfire_grace_time" in kw_names:
        return None
    return f"{path}:{lineno}: @scheduled_job(...) missing keyword misfire_grace_time="


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno or 0}: syntax error: {exc.msg}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            msg = _check_add_job_call(node, path)
            if msg:
                errors.append(msg)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for dec in node.decorator_list:
                msg = _check_scheduled_job_decorator(dec, path, getattr(dec, "lineno", node.lineno))
                if msg:
                    errors.append(msg)
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    root = repo_root / "apis" / "brain" / "app"
    if not root.is_dir():
        print(f"Expected Brain app dir at {root}", file=sys.stderr)
        return 2
    failures: list[str] = []
    for py in sorted(root.rglob("*.py")):
        failures.extend(check_file(py))
    if failures:
        print("check_apscheduler_misfire: failures\n", file=sys.stderr)
        for line in failures:
            print(line, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
