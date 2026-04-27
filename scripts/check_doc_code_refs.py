#!/usr/bin/env python3
"""Track K — fail when docs reference dead paths or stale line numbers.

Markdown under ``/docs`` often points at code with patterns like:
    apis/brain/app/services/agent.py:393
    apps/studio/src/app/admin/overview-client.tsx
    .cursor/rules/cpa.mdc

When the underlying code moves or gets renamed, those refs rot. This
script scans docs, extracts those refs, and verifies:
  1. The referenced file exists.
  2. If a ``:N`` line number is attached, the file has at least N lines.
     (We don't try to check that line N still means what the doc claims
     — that's an LLM-level job — but "dead line number" is a cheap win.)

Runs in CI via ``.github/workflows/brain-personas-doc.yaml`` alongside
the BRAIN_PERSONAS.md drift check so agent-ops persona docs stay
tethered to the code.

Opt-outs:
  - Files in ``IGNORE_DIRS`` are skipped (generated markdown, historical
    sprint plans, etc.).
  - Refs listed in ``EXPECTED_DEAD`` are whitelisted for legitimate
    "this used to exist" mentions; update sparingly.

medallion: ops
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
BASELINE_PATH = REPO_ROOT / "docs" / ".doc-drift-baseline.json"

IGNORE_DIRS: set[str] = {
    "docs/philosophy",
    "docs/sprints",
    "docs/generated",
    "docs/archive",
}

# Whitelisted refs that intentionally mention removed/moved paths.
EXPECTED_DEAD: set[str] = {
    "apis/brain/app/services/personas.py",
    ".github/workflows/auto-merge-sweep.yaml",
    ".github/workflows/dependabot-auto-approve.yaml",
    ".github/workflows/dependabot-major-triage.yaml",
    # .cursor/ is gitignored so the file exists locally for IDE config but
    # never lands in the CI checkout. The references are intentional and
    # correct from a developer's perspective.
    ".cursor/mcp.json",
    # Archived to docs/archive/MARKET_DATA_FLOWS.md; merge note in MARKET_DATA.md keeps provenance path.
    "docs/axiomfolio/MARKET_DATA_FLOWS.md",
    # Archived to docs/archive/VMP-SUMMARY-2026-03-18.md; merge notes in
    # VENTURE_MASTER_PLAN.md + DOCS_STREAMLINE_2026Q2.md keep provenance path.
    "docs/VMP-SUMMARY.md",
    # PR #234 consolidated 6 per-app Clerk Appearance files into named presets
    # in packages/auth/src/appearance/presets.ts. CLERK_*.md docs still mention
    # the old paths in narrative copy; pending a docs rewrite that redirects to
    # the shared package + preset names.
    "apps/distill/src/lib/clerk-appearance.ts",
    "apps/axiomfolio-next/src/lib/axiomfolio-clerk-appearance.ts",
    "apps/launchfree/src/lib/launchfree-clerk-appearance.ts",
    "apps/filefree/src/lib/filefree-clerk-appearance.ts",
    "apps/trinkets/src/lib/trinkets-clerk-appearance.ts",
    "apps/studio/src/lib/studio-clerk-appearance.ts",
    # Pending design app + Chromatic wiring (FOUNDER_ACTIONS.md; paths land with apps/design PRs).
    "apps/design/vercel.json",
    "apps/design/chromatic.config.json",
    "docs/infra/CHROMATIC_VRT.md",
}

# Match:
#   apis/brain/app/foo.py
#   apis/brain/app/foo.py:123
#   apps/studio/src/app/.../page.tsx
#   .cursor/rules/cpa.mdc
REF_PATTERN = re.compile(
    r"(?<![a-zA-Z0-9._/-])"  # no letter / dot / slash before
    r"((?:apis|apps|packages|scripts|infra|services|docs|\.github|\.cursor)"
    # Longer extensions listed first so the regex engine doesn't match
    # `.ts` on a `.tsx` path and then flag it as missing.
    r"/[a-zA-Z0-9._/-]+\.(?:tsx|jsx|yaml|toml|json|mdc|yml|md|py|ts|js|sh))"
    r"(?::(\d+))?"
)


def _is_ignored(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return any(rel.startswith(ignored) for ignored in IGNORE_DIRS)


def _collect_refs() -> dict[Path, list[tuple[str, int | None, int]]]:
    results: dict[Path, list[tuple[str, int | None, int]]] = {}
    for md_path in DOCS_ROOT.rglob("*.md"):
        if _is_ignored(md_path):
            continue
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), start=1):
            # Skip fenced code blocks? Keep them: they are still refs people
            # expect to resolve.
            for m in REF_PATTERN.finditer(line):
                ref = m.group(1)
                line_no = int(m.group(2)) if m.group(2) else None
                results.setdefault(md_path, []).append((ref, line_no, i))
    return results


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def _compute_findings() -> tuple[list[tuple[Path, str, int | None, int]], list[tuple[Path, str, int, int, int]], int]:
    refs = _collect_refs()
    total = sum(len(v) for v in refs.values())
    dead: list[tuple[Path, str, int | None, int]] = []
    stale_lineno: list[tuple[Path, str, int, int, int]] = []

    for md_path, items in refs.items():
        for ref, line_no, md_line in items:
            if ref in EXPECTED_DEAD:
                continue
            target = REPO_ROOT / ref
            if not target.exists():
                dead.append((md_path, ref, line_no, md_line))
                continue
            if line_no is None or not target.is_file():
                continue
            total_lines = _count_lines(target)
            if line_no > total_lines:
                stale_lineno.append((md_path, ref, line_no, total_lines, md_line))

    return dead, stale_lineno, total


def _load_baseline() -> dict[str, list[str]]:
    if not BASELINE_PATH.exists():
        return {"dead": [], "stale": []}
    try:
        return json.loads(BASELINE_PATH.read_text())
    except json.JSONDecodeError:
        return {"dead": [], "stale": []}


def _key_dead(md_path: Path, ref: str) -> str:
    return f"{md_path.relative_to(REPO_ROOT).as_posix()}::{ref}"


def _key_stale(md_path: Path, ref: str, line_no: int) -> str:
    return f"{md_path.relative_to(REPO_ROOT).as_posix()}::{ref}:{line_no}"


def _write_baseline(dead, stale) -> None:
    payload = {
        "_doc": (
            "Baseline of pre-existing doc/code drift. CI fails only on NEW "
            "entries beyond this set. Regenerate with: "
            "python scripts/check_doc_code_refs.py --update-baseline"
        ),
        "dead": sorted({_key_dead(p, r) for p, r, _, _ in dead}),
        "stale": sorted({_key_stale(p, r, n) for p, r, n, _, _ in stale}),
    }
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"Wrote baseline to {BASELINE_PATH.relative_to(REPO_ROOT)} — "
        f"{len(payload['dead'])} dead refs, {len(payload['stale'])} stale lines.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Write the current set of findings to the baseline file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any drift, ignoring the baseline (use once debt is paid down).",
    )
    args = parser.parse_args()

    dead, stale_lineno, total = _compute_findings()
    rel = lambda p: p.relative_to(REPO_ROOT).as_posix()

    if args.update_baseline:
        _write_baseline(dead, stale_lineno)
        return 0

    baseline = _load_baseline() if not args.strict else {"dead": [], "stale": []}
    known_dead = set(baseline.get("dead", []))
    known_stale = set(baseline.get("stale", []))

    new_dead = [
        (p, r, ln, l) for p, r, ln, l in dead if _key_dead(p, r) not in known_dead
    ]
    new_stale = [
        (p, r, ln, tot, l)
        for p, r, ln, tot, l in stale_lineno
        if _key_stale(p, r, ln) not in known_stale
    ]

    print(
        f"Scanned {total} code references. "
        f"Total dead: {len(dead)} (baseline {len(known_dead)}, new {len(new_dead)}). "
        f"Total stale lines: {len(stale_lineno)} "
        f"(baseline {len(known_stale)}, new {len(new_stale)})."
    )

    if new_dead:
        print("\n--- NEW dead references (file missing) ---", file=sys.stderr)
        for md_path, ref, _line_no, md_line in new_dead:
            print(
                f"  {rel(md_path)}:{md_line}  →  {ref}  (not found)",
                file=sys.stderr,
            )

    if new_stale:
        print(
            "\n--- NEW stale line numbers (file exists but is shorter) ---",
            file=sys.stderr,
        )
        for md_path, ref, line_no, total_lines, md_line in new_stale:
            print(
                f"  {rel(md_path)}:{md_line}  →  {ref}:{line_no}  "
                f"(file has {total_lines} lines)",
                file=sys.stderr,
            )

    if new_dead or new_stale:
        print(
            "\nERROR: NEW doc ↔ code drift detected. Either update the reference, "
            "add it to EXPECTED_DEAD, or — only when intentionally accepting debt — "
            "run: python scripts/check_doc_code_refs.py --update-baseline",
            file=sys.stderr,
        )
        return 1

    print("OK: no new doc ↔ code drift introduced.")
    if dead or stale_lineno:
        print(
            "  (baseline debt remains: "
            f"{len(dead)} dead refs, {len(stale_lineno)} stale lines — "
            "track in the weekly QA report)",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
