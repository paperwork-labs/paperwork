#!/usr/bin/env python3
"""Verify each Alembic ``versions`` tree resolves to exactly one migration head.

When multiple branches create revisions that share the same ``down_revision``, Alembic
can end up with multiple heads and ``alembic upgrade head`` / app boot fails at
runtime (Brain incident PR #348).

Run:
    python scripts/check_alembic_heads.py

Exit 1 when any migrations directory reports more than one head. Stdlib only.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _discover_versions_dirs(root: Path) -> list[Path]:
    """Return each ``alembic/versions`` dir that contains at least one ``*.py``."""

    out: list[Path] = []
    for alembic in root.rglob("alembic"):
        if not alembic.is_dir():
            continue
        versions = alembic / "versions"
        if versions.is_dir() and any(versions.glob("*.py")):
            out.append(versions)
    out.sort(key=lambda p: str(p.relative_to(root)))
    return out


def _parse_migration(path: Path, root: Path) -> tuple[str, str | tuple[str, ...] | None]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))

    revision: str | None = None
    got_down = False
    down_revision: str | tuple[str, ...] | None | object = Ellipsis

    def _bind_name_from_simple_assign(
        node: ast.Assign | ast.AnnAssign,
    ) -> tuple[ast.Name | None, ast.expr | None]:
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                return node.target, node.value
            return None, None
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    return tgt, node.value
            return None, None
        return None, None

    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        tgt, value = _bind_name_from_simple_assign(node)
        if tgt is None or value is None:
            continue
        if tgt.id == "revision":
            revision = ast.literal_eval(value)
        elif tgt.id == "down_revision":
            got_down = True
            if isinstance(value, ast.Constant) and value.value is None:
                down_revision = None
            else:
                down_revision = ast.literal_eval(value)

    rel = path.relative_to(root)

    if revision is None:
        raise SystemExit(f"{rel}: missing top-level `revision =` assignment.")
    if not got_down:
        raise SystemExit(f"{rel}: missing top-level `down_revision =` assignment.")

    if isinstance(down_revision, tuple):
        down_revision_t = tuple(str(x) for x in down_revision)
        return str(revision), down_revision_t if down_revision_t else None
    assert down_revision is not Ellipsis

    dr: str | tuple[str, ...] | None = down_revision
    if isinstance(dr, str):
        return str(revision), dr
    if dr is None:
        return str(revision), None
    return str(revision), dr


def _heads_for_versions_dir(
    versions: Path,
    root: Path,
) -> tuple[list[str], dict[str, str | tuple[str, ...] | None]]:
    """Return sorted head revision IDs and revision → down_revision map."""

    all_revisions: set[str] = set()
    down_revision_targets: set[str] = set()
    revision_to_down: dict[str, str | tuple[str, ...] | None] = {}

    for py in sorted(versions.glob("*.py")):
        if py.name.startswith("__"):
            continue
        rev, down = _parse_migration(py, root)
        all_revisions.add(rev)
        revision_to_down[rev] = down
        if down is None:
            continue
        if isinstance(down, tuple):
            down_revision_targets.update(down)
        else:
            down_revision_targets.add(down)

    # Alembic head = a revision ID that never appears as another migration's
    # down_revision (i.e. no newer revision points back to this one).
    head_ids = sorted(all_revisions - down_revision_targets)
    return head_ids, revision_to_down


def main() -> int:
    versions_dirs = _discover_versions_dirs(_REPO_ROOT)
    if not versions_dirs:
        print(
            "check_alembic_heads: no alembic/versions directories with *.py found",
            file=sys.stderr,
        )
        return 1

    failed = False
    for versions in versions_dirs:
        rel = versions.relative_to(_REPO_ROOT)
        try:
            heads, _ = _heads_for_versions_dir(versions, _REPO_ROOT)
        except SystemExit as e:
            print(e, file=sys.stderr)
            failed = True
            continue
        if len(heads) == 1:
            print(f"OK: {rel} — single head {heads[0]!r}")
            continue
        failed = True
        print(
            f"ERROR: {rel} — expected exactly 1 Alembic head, found {len(heads)}: {heads}",
            file=sys.stderr,
        )
        print(
            "\nTo fix a multi-head chain:\n"
            "  - Linearize overlapping branches so down_revision picks a unique order, or\n"
            "  - Add a merge revision with ``down_revision = ('rev_a', 'rev_b')``.\n"
            "See https://alembic.sqlalchemy.org/en/latest/branches.html\n",
            file=sys.stderr,
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
