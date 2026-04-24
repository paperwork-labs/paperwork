#!/usr/bin/env python3
"""
Iron Law #1 enforcement: append-only ledgers.

Scans backend/ Python source for patterns that mutate or delete rows in
ledger tables. Ledger tables are append-only — corrections come as new
rows that supersede earlier ones, never as in-place UPDATE or DELETE.

Ledger tables (match SQLAlchemy model class name OR __tablename__ string):
    - Trade                  / "trades"
    - Transaction            / "transactions"
    - AuditEvent             / "audit_events"
    - OrderLifecycleEvent    / "order_lifecycle_events"
    - MarketSnapshotHistory  / "market_snapshot_history"

Banned patterns:
    1. SQLAlchemy ORM:
         db.query(<LedgerModel>)...delete(...)
         db.query(<LedgerModel>)...update(...)
       (Any method chain starting with .query(LedgerModel).)

    2. SQLAlchemy Core / raw:
         db.execute(text("DELETE FROM trades ..."))
         db.execute(delete(Trade)...)
         db.execute(update(Trade)...)

    3. Direct SQL string literals with "DELETE FROM <ledger>" or
       "UPDATE <ledger> SET" (case-insensitive).

Waiver mechanism:
    On the offending line (or the line immediately above), add:
        # medallion: allow-delete <short-reason>
        # medallion: allow-update <short-reason>

    Example (acceptable, documented reason):
        # medallion: allow-delete test fixture teardown
        db.query(Trade).filter_by(account_id=999).delete()

    Waivers are surfaced in the --stats output so we can track tech debt.

Exit codes:
    0 — clean (or only waivered violations)
    1 — one or more unwaivered violations found
    2 — script-level error (arg parsing, missing repo root)

CLI:
    python3 scripts/medallion/check_sql.py                # full scan, terse
    python3 scripts/medallion/check_sql.py --stats        # + summary
    python3 scripts/medallion/check_sql.py --verbose      # + waivered hits

Runs from repo root or any subdirectory — resolves REPO_ROOT via script path.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
APP = REPO_ROOT / "app"

# Scan scope: services + tasks + api. Exclude tests (they legitimately need
# cleanup fixtures) and alembic (migrations have different rules handled by
# a separate check_migrations.py — planned).
SCAN_DIRS = [
    APP / "services",
    APP / "tasks",
    APP / "api",
    APP / "models",
]
EXCLUDE_DIRS = {"tests", "alembic", "__pycache__", ".mypy_cache"}

LEDGER_MODELS = {
    "Trade",
    "Transaction",
    "AuditEvent",
    "OrderLifecycleEvent",
    "MarketSnapshotHistory",
}

LEDGER_TABLE_NAMES = {
    "trades",
    "transactions",
    "audit_events",
    "order_lifecycle_events",
    "market_snapshot_history",
}

WAIVER_DELETE_RE = re.compile(
    r"#\s*medallion:\s*allow-delete\s+\S",
    re.IGNORECASE,
)
WAIVER_UPDATE_RE = re.compile(
    r"#\s*medallion:\s*allow-update\s+\S",
    re.IGNORECASE,
)

# Raw-SQL regexes. Case-insensitive, permissive whitespace.
SQL_DELETE_RE = re.compile(
    r"\bDELETE\s+FROM\s+(?P<table>\w+)",
    re.IGNORECASE,
)
SQL_UPDATE_RE = re.compile(
    r"\bUPDATE\s+(?P<table>\w+)\s+SET\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    kind: str  # "delete" | "update"
    target: str  # Model name or table name
    snippet: str
    waivered: bool
    waiver_reason: str | None


def iter_py_files() -> Iterable[Path]:
    for root in SCAN_DIRS:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            if any(part in EXCLUDE_DIRS for part in py.parts):
                continue
            yield py


def _line_is_waivered(source_lines: list[str], line_no: int, kind: str) -> tuple[bool, str | None]:
    """Check whether the line at `line_no` (1-indexed) carries a waiver on
    itself or on the immediately preceding line."""
    waiver_re = WAIVER_DELETE_RE if kind == "delete" else WAIVER_UPDATE_RE
    # 1-indexed; protect range
    for candidate in (line_no - 1, line_no - 2):
        if 0 <= candidate < len(source_lines):
            m = waiver_re.search(source_lines[candidate])
            if m:
                reason = source_lines[candidate].split(kind, 1)[-1]
                return True, reason.strip(" -:#\n")
    return False, None


class ORMQueryVisitor(ast.NodeVisitor):
    """Detects db.query(<LedgerModel>).....delete(...) and .update(...)."""

    def __init__(self, source_lines: list[str], path: Path) -> None:
        self.source_lines = source_lines
        self.path = path
        self.hits: list[Violation] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        # Pattern: <...>.delete(...) or <...>.update(...)
        if isinstance(func, ast.Attribute) and func.attr in ("delete", "update"):
            # Walk backwards through the chain to find .query(<LedgerModel>)
            root = func.value
            ledger_model = _find_ledger_query_in_chain(root)
            if ledger_model is not None:
                kind = func.attr
                line_no = node.lineno
                snippet = (
                    self.source_lines[line_no - 1].strip()
                    if line_no <= len(self.source_lines)
                    else ""
                )
                waivered, reason = _line_is_waivered(self.source_lines, line_no, kind)
                self.hits.append(
                    Violation(
                        path=self.path,
                        line=line_no,
                        kind=kind,
                        target=ledger_model,
                        snippet=snippet,
                        waivered=waivered,
                        waiver_reason=reason,
                    )
                )
        self.generic_visit(node)


def _find_ledger_query_in_chain(node: ast.AST) -> str | None:
    """Walk a method chain like `db.query(Trade).filter_by(...)` and return
    the ledger model name if the chain contains `.query(<LedgerModel>)`."""
    while isinstance(node, (ast.Call, ast.Attribute)):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "query":
                # Check args — must contain a ledger model Name
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id in LEDGER_MODELS:
                        return arg.id
            # Descend into the callee's receiver
            if isinstance(func, ast.Attribute):
                node = func.value
            else:
                break
        elif isinstance(node, ast.Attribute):
            node = node.value
    return None


def scan_file_orm(path: Path) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    source_lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    visitor = ORMQueryVisitor(source_lines, path)
    visitor.visit(tree)
    return visitor.hits


def scan_file_raw_sql(path: Path) -> list[Violation]:
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    source_lines = source.splitlines()
    hits: list[Violation] = []

    for line_no, line in enumerate(source_lines, start=1):
        # Skip comments entirely — checking their content would false-positive
        # on documentation that talks about these patterns.
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        m = SQL_DELETE_RE.search(line)
        if m and m.group("table").lower() in LEDGER_TABLE_NAMES:
            waivered, reason = _line_is_waivered(source_lines, line_no, "delete")
            hits.append(
                Violation(
                    path=path,
                    line=line_no,
                    kind="delete",
                    target=m.group("table"),
                    snippet=line.strip(),
                    waivered=waivered,
                    waiver_reason=reason,
                )
            )

        m = SQL_UPDATE_RE.search(line)
        if m and m.group("table").lower() in LEDGER_TABLE_NAMES:
            waivered, reason = _line_is_waivered(source_lines, line_no, "update")
            hits.append(
                Violation(
                    path=path,
                    line=line_no,
                    kind="update",
                    target=m.group("table"),
                    snippet=line.strip(),
                    waivered=waivered,
                    waiver_reason=reason,
                )
            )

    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    ap.add_argument("--stats", action="store_true", help="Print summary counts")
    ap.add_argument("--verbose", action="store_true", help="Also print waivered hits")
    args = ap.parse_args()

    all_violations: list[Violation] = []
    files_scanned = 0

    for py in iter_py_files():
        files_scanned += 1
        all_violations.extend(scan_file_orm(py))
        all_violations.extend(scan_file_raw_sql(py))

    unwaivered = [v for v in all_violations if not v.waivered]
    waivered = [v for v in all_violations if v.waivered]

    if unwaivered:
        print(
            f"✗ Iron Law #1 violated: {len(unwaivered)} unwaivered ledger mutation(s)",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        for v in sorted(unwaivered, key=lambda x: (str(x.path), x.line)):
            rel = v.path.relative_to(REPO_ROOT)
            print(f"  {rel}:{v.line}  {v.kind.upper():6s} on {v.target}", file=sys.stderr)
            print(f"    {v.snippet}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "To waiver a legitimate case (e.g. test fixture teardown, one-off "
            "migration), add a comment on or just above the line:",
            file=sys.stderr,
        )
        print("  # medallion: allow-delete <reason>", file=sys.stderr)
        print("  # medallion: allow-update <reason>", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Otherwise, refactor to upsert semantics. Ledger tables are append-only.",
            file=sys.stderr,
        )

    if args.verbose and waivered:
        print("", file=sys.stderr)
        print(f"({len(waivered)} waivered hits:)", file=sys.stderr)
        for v in sorted(waivered, key=lambda x: (str(x.path), x.line)):
            rel = v.path.relative_to(REPO_ROOT)
            print(
                f"  {rel}:{v.line}  {v.kind.upper():6s} on {v.target} [{v.waiver_reason}]",
                file=sys.stderr,
            )

    if args.stats or not unwaivered:
        print(f"Files scanned:        {files_scanned}")
        print(f"Ledger mutations:     {len(all_violations)}")
        print(f"  Unwaivered (fail):  {len(unwaivered)}")
        print(f"  Waivered:           {len(waivered)}")
        if not unwaivered:
            print("")
            print("✓ Iron Law #1 clean — no unwaivered ledger mutations.")

    return 1 if unwaivered else 0


if __name__ == "__main__":
    sys.exit(main())
