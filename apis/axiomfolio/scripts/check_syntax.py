#!/usr/bin/env python3
"""Check all backend Python files for syntax errors without writing .pyc files.

Uses ast.parse() which only parses in memory — no __pycache__ directories
are created, avoiding PermissionError in non-root Docker containers.
"""

import ast
import pathlib
import sys

errs = 0
checked = 0
for f in sorted(pathlib.Path("backend").rglob("*.py")):
    checked += 1
    try:
        ast.parse(f.read_text(), filename=str(f))
    except SyntaxError as e:
        print(e, file=sys.stderr)
        errs += 1

print(f"Syntax check: {checked} files, {errs} errors")
sys.exit(1 if errs else 0)
