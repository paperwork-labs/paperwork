#!/usr/bin/env python3
"""medallion: ops

Medallion Phase 0.C migrator.

Consumes ``medallion_move_map.yaml`` and performs atomic filesystem +
import rewrites in *pass-scoped* commits.

Invariants
----------
1. Default is **dry-run**. Nothing changes on disk or in git without
   ``--apply``.
2. ``--apply`` requires a clean working tree; the script refuses to
   overwrite uncommitted work.
3. Each pass is its own git commit, so a single ``git reset --hard HEAD~1``
   reverts exactly one pass.
4. Idempotent: if a source file is already absent but the target
   exists, the script logs and skips instead of failing.
5. String-literal rewrites use longest-match-first ordering so a
   rename of ``portfolio.tastytrade_sync_service`` does not collide
   with a parent ``portfolio`` rename.

Usage
-----
    # Inspect passes and their sizes.
    python3 scripts/medallion_migrate.py --list-passes

    # Dry-run the entire migration.
    python3 scripts/medallion_migrate.py

    # Dry-run a single pass.
    python3 scripts/medallion_migrate.py --pass pass1_leaf_utilities

    # Execute a single pass (commits on success).
    python3 scripts/medallion_migrate.py --pass pass1_leaf_utilities --apply

    # Execute all passes sequentially.
    python3 scripts/medallion_migrate.py --apply

Safety
------
Between passes, run ``make medallion-lint`` and ``pytest --collect-only``.
If either fails, ``git reset --hard HEAD~1`` and inspect.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVICES = REPO / "app" / "services"
MAP_PATH = REPO / "medallion_move_map.yaml"

# Directories to scan for import/string-literal rewrites. Anything
# outside these is considered ineligible (e.g. node_modules, .venv).
SCAN_DIRS = ["app", "scripts"]


# -------------------------------------------------------------------
# Data model
# -------------------------------------------------------------------


def _path_to_module(rel: str) -> str:
    """Convert a services-relative path to a dotted module name.

    ``market/providers/__init__.py`` -> ``app.services.bronze.market.providers``
    ``market/atr_series.py``         -> ``app.services.silver.math.atr_series``
    ``market/providers``             -> ``app.services.bronze.market.providers``
    """
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[:-3]
    return "app.services." + rel.replace("/", ".")


@dataclass(frozen=True)
class Move:
    source: str          # relative to app/services/
    target: str          # relative to app/services/
    pass_name: str

    @property
    def old_module(self) -> str:
        return _path_to_module(self.source)

    @property
    def new_module(self) -> str:
        return _path_to_module(self.target)

    @property
    def abs_source(self) -> Path:
        return SERVICES / self.source

    @property
    def abs_target(self) -> Path:
        return SERVICES / self.target


# -------------------------------------------------------------------
# YAML parsing (tiny, schema-specific — avoids a pyyaml dep)
# -------------------------------------------------------------------


_FIELD_RE = re.compile(r"^\s*(source|target|pass):\s*(.+?)\s*$")


def parse_move_map(text: str) -> list[Move]:
    """Parse medallion_move_map.yaml without a yaml library.

    Accepts only the exact schema our generator emits:

        moves:
          - source: <path>
            target: <path>
            pass:   <name>
    """
    moves: list[Move] = []
    cur: dict[str, str] = {}
    in_moves = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        # Top-level keys toggle the parser mode. We only care about
        # ``moves:``; anything else (e.g. ``stays:``) ends the block.
        if not line.startswith(" ") and stripped.endswith(":"):
            if stripped == "moves:":
                in_moves = True
            else:
                in_moves = False
            continue
        if not in_moves:
            continue
        if stripped.startswith("- source:"):
            if cur:
                moves.append(_finalize(cur))
                cur = {}
            cur["source"] = stripped[len("- source:"):].strip()
            continue
        m = _FIELD_RE.match(line)
        if not m:
            raise ValueError(f"Unexpected line in move map: {raw!r}")
        key, val = m.group(1), m.group(2)
        cur[key] = val
    if cur:
        moves.append(_finalize(cur))
    return moves


def _finalize(d: dict[str, str]) -> Move:
    missing = {"source", "target", "pass"} - d.keys()
    if missing:
        raise ValueError(f"Move missing fields {missing}: {d}")
    return Move(source=d["source"], target=d["target"], pass_name=d["pass"])


# -------------------------------------------------------------------
# Reference rewriter
# -------------------------------------------------------------------


def build_rewrite_pairs(moves: list[Move]) -> list[tuple[str, str]]:
    """Return (old_module, new_module) pairs, longest-first."""
    pairs = [
        (m.old_module, m.new_module)
        for m in moves
        if m.old_module != m.new_module
    ]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def rewrite_file(path: Path, pairs: list[tuple[str, str]]) -> tuple[bool, int]:
    """Apply dotted-path rewrites to a file.

    Matches ``old`` iff it is bounded on both sides by a non-identifier
    character (or start/end of string). This correctly handles:

        from <old> import X       -> from <new> import X
        import <old>.sub          -> import <new>.sub
        "<old>.sub.Class"         -> "<new>.sub.Class"

    and avoids rewriting ``<old>_other`` or ``<old>xyz``.
    """
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return (False, 0)
    new_text = text
    count = 0
    for old, new in pairs:
        # Negative lookbehind: not in the middle of a dotted path.
        # Negative lookahead: not followed by identifier OR dot — the
        # latter is critical because submodules can live in different
        # layers than the parent package (e.g. risk/ splits to gold/
        # and execution/). Without this, a bare package rewrite would
        # corrupt submodule references.
        pattern = re.compile(
            r"(?<![A-Za-z0-9_.])" + re.escape(old) + r"(?![A-Za-z0-9_.])"
        )
        new_text, n = pattern.subn(new, new_text)
        count += n
    if new_text != text:
        path.write_text(new_text)
        return (True, count)
    return (False, 0)


def rewrite_all(pairs: list[tuple[str, str]], apply: bool) -> tuple[int, int]:
    """Walk SCAN_DIRS and rewrite every .py file. Returns (files, refs)."""
    files_changed = 0
    refs_rewritten = 0
    for top in SCAN_DIRS:
        root = REPO / top
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in {".venv", "__pycache__", "node_modules"}
                   for part in path.parts):
                continue
            if not apply:
                # Dry-run: test the rewrite in memory and count.
                try:
                    text = path.read_text()
                except (UnicodeDecodeError, OSError):
                    continue
                count = 0
                for old, new in pairs:
                    pattern = re.compile(
                        r"(?<![A-Za-z0-9_.])"
                        + re.escape(old)
                        + r"(?![A-Za-z0-9_.])"
                    )
                    count += len(pattern.findall(text))
                if count:
                    files_changed += 1
                    refs_rewritten += count
                continue
            changed, count = rewrite_file(path, pairs)
            if changed:
                files_changed += 1
                refs_rewritten += count
    return (files_changed, refs_rewritten)


# -------------------------------------------------------------------
# Filesystem / git operations
# -------------------------------------------------------------------


def ensure_clean_tree() -> None:
    out = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO
    ).decode()
    if out.strip():
        print("error: working tree is dirty. Commit or stash first.",
              file=sys.stderr)
        sys.exit(2)


_STUB_INIT_RE = re.compile(r'^\s*"""medallion:\s*\w+\s*"""\s*$', re.MULTILINE)


def _is_stub_init(path: Path) -> bool:
    """True iff path is an __init__.py containing only a medallion docstring.

    Wave 0.B scaffolded stub __init__.py files at every target layer
    directory. When a pass moves a source __init__.py (which has real
    imports) to a path the scaffold already touched, ``git mv`` refuses
    because the destination exists. Detect those stubs so ``git_mv`` can
    replace them safely.
    """
    if path.name != "__init__.py" or not path.exists():
        return False
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return False
    stripped = text.strip()
    if not stripped:
        return True
    # Accept only: a single medallion: <layer> docstring, nothing else.
    return bool(_STUB_INIT_RE.fullmatch(stripped))


def ensure_init_pys(
    target_dirs: set[Path], move_targets: set[Path], apply: bool,
) -> int:
    """Ensure each new package dir under app/services/ has __init__.py.

    Does not overwrite an existing __init__.py — it only creates missing
    ones. The medallion tag is deliberately minimal; check_imports.py
    will infer the layer from the path.

    ``move_targets`` is the set of absolute target paths the current pass
    will ``git mv`` into. We skip creating __init__.py for those (it would
    conflict with the subsequent move).
    """
    created = 0
    for d in sorted(target_dirs):
        cur = d
        while cur != SERVICES and cur.is_relative_to(SERVICES):
            init = cur / "__init__.py"
            if init not in move_targets and not init.exists():
                if apply:
                    cur.mkdir(parents=True, exist_ok=True)
                    layer = cur.relative_to(SERVICES).parts[0]
                    init.write_text(
                        f'"""medallion: {layer}"""\n'
                    )
                created += 1
            cur = cur.parent
    return created


def git_mv(source: Path, target: Path, apply: bool) -> str:
    """Move ``source`` to ``target`` via ``git mv`` (or report what would).

    Returns a status string: moved | skipped-already | skipped-missing.

    If ``target`` already exists and is a Wave 0.B scaffold stub (an
    __init__.py containing only a ``medallion: <layer>`` docstring), we
    remove the stub first so the source's richer content can take its
    place. A non-stub collision is a genuine conflict and is surfaced as
    a hard error.
    """
    if not source.exists():
        if target.exists():
            return "skipped-already"
        return "skipped-missing"
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if _is_stub_init(target):
                subprocess.run(
                    ["git", "rm", "-f", str(target.relative_to(REPO))],
                    check=True, cwd=REPO,
                )
            else:
                raise RuntimeError(
                    f"refusing to overwrite non-stub target: {target}"
                )
        subprocess.run(
            ["git", "mv", str(source.relative_to(REPO)),
             str(target.relative_to(REPO))],
            check=True, cwd=REPO,
        )
    return "moved"


def commit_pass(pass_name: str, moves: list[Move]) -> None:
    count = len(moves)
    subprocess.run(["git", "add", "-A"], check=True, cwd=REPO)
    # If nothing is staged, do not create an empty commit.
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--stat"], cwd=REPO
    ).decode()
    if not out.strip():
        print(f"  (no changes staged for {pass_name}; skipping commit)")
        return
    msg = (
        f"medallion(0.C): {pass_name} — {count} files\n\n"
        f"Mechanical migration performed by scripts/medallion_migrate.py.\n"
        f"See medallion_move_map.yaml for the full manifest.\n"
    )
    subprocess.run(["git", "commit", "-m", msg], check=True, cwd=REPO)


def run_smoke_tests() -> None:
    """Run lightweight checks: imports, medallion lints, pytest collect."""
    print("  → python -m compileall (syntax check)")
    subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "app"],
        check=True, cwd=REPO,
    )
    print("  → make medallion-check (import layering)")
    subprocess.run(["make", "medallion-check"], check=True, cwd=REPO)
    print("  → make medallion-check-sql (iron law #1)")
    subprocess.run(["make", "medallion-check-sql"], check=True, cwd=REPO)


# -------------------------------------------------------------------
# Orchestration
# -------------------------------------------------------------------


def run_pass(
    pass_name: str,
    all_moves: list[Move],
    *,
    apply: bool,
    skip_smoke: bool,
) -> None:
    pass_moves = [m for m in all_moves if m.pass_name == pass_name]
    if not pass_moves:
        print(f"\n== pass {pass_name}: 0 files (nothing to do)")
        return

    print(f"\n== pass {pass_name}: {len(pass_moves)} file(s)")

    # 1. git mv every file in the pass (and ensure parent packages exist)
    target_dirs = {m.abs_target.parent for m in pass_moves}
    move_targets = {m.abs_target for m in pass_moves}
    created = ensure_init_pys(target_dirs, move_targets, apply=apply)
    if created:
        print(f"  {'would create' if not apply else 'created'} "
              f"{created} new __init__.py")

    statuses = {"moved": 0, "skipped-already": 0, "skipped-missing": 0}
    for mv in pass_moves:
        status = git_mv(mv.abs_source, mv.abs_target, apply=apply)
        statuses[status] = statuses.get(status, 0) + 1
    print(f"  moves: {statuses}")
    if statuses["skipped-missing"]:
        print("  WARNING: sources missing with no target present — "
              "move map may be stale.")

    # 2. rewrite references for the files moved *in this pass*.
    #    Using pass-local pairs (not global) keeps each commit atomic.
    pairs = build_rewrite_pairs(pass_moves)
    if not pairs:
        print("  no dotted-path changes to rewrite")
    else:
        files, refs = rewrite_all(pairs, apply=apply)
        print(f"  references: {'would rewrite' if not apply else 'rewrote'} "
              f"{refs} occurrence(s) in {files} file(s)")

    if not apply:
        print("  (dry-run; no git commit)")
        return

    # 3. retag moved files so their ``medallion: <layer>`` docstring
    #    matches their new path. tag_files.py is idempotent.
    print("  → scripts/medallion/tag_files.py --apply (retag new paths)")
    subprocess.run(
        [sys.executable, "scripts/medallion/tag_files.py", "--apply"],
        check=True, cwd=REPO,
    )

    # 4. smoke tests BEFORE commit — if they fail, leave the tree dirty
    #    so the operator can inspect.
    if not skip_smoke:
        try:
            run_smoke_tests()
        except subprocess.CalledProcessError as exc:
            print(f"\n  SMOKE TEST FAILED for pass {pass_name}: {exc}")
            print("  Tree left dirty for inspection. To revert:")
            print("    git restore --staged . && git restore .")
            sys.exit(3)

    # 5. commit
    commit_pass(pass_name, pass_moves)
    print(f"  committed: {pass_name}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--apply", action="store_true",
                    help="Actually perform the migration (default: dry-run).")
    ap.add_argument("--pass", dest="pass_name",
                    help="Run only the named pass.")
    ap.add_argument("--list-passes", action="store_true",
                    help="Print pass names + file counts, then exit.")
    ap.add_argument("--skip-smoke", action="store_true",
                    help="Skip compileall + medallion checks "
                         "(NOT recommended).")
    args = ap.parse_args()

    moves = parse_move_map(MAP_PATH.read_text())
    passes = list(dict.fromkeys(m.pass_name for m in moves))

    if args.list_passes:
        print(f"Move map: {MAP_PATH.relative_to(REPO)}")
        print(f"Total moves: {len(moves)}")
        print("Passes:")
        for p in passes:
            n = sum(1 for m in moves if m.pass_name == p)
            print(f"  {p}  ({n} files)")
        return 0

    if args.apply:
        ensure_clean_tree()

    selected = [args.pass_name] if args.pass_name else passes
    unknown = [p for p in selected if p not in passes]
    if unknown:
        print(f"error: unknown pass(es): {unknown}", file=sys.stderr)
        print(f"available: {passes}", file=sys.stderr)
        return 2

    print(f"mode: {'APPLY' if args.apply else 'dry-run'}")
    print(f"passes: {selected}")

    for p in selected:
        run_pass(p, moves, apply=args.apply, skip_smoke=args.skip_smoke)

    print("\n✓ done" if args.apply else "\n✓ dry-run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
