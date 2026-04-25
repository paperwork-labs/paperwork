#!/usr/bin/env python3
"""Fail if Studio / system graph / n8n use a persona slug outside Brain PersonaSpecs.

Canonical slugs: ``apis/brain/app/personas/specs/*.yaml`` (filename stem = slug).

Scanned:
  - ``apps/studio/src/lib/command-center.ts`` — ``WORKFLOW_META`` ``role`` strings
  - ``apps/studio/src/data/system-graph.json`` — ``owner_persona`` on nodes
  - ``infra/hetzner/workflows/**/*.json`` — ``persona_pin`` in workflow JSON
  - ``data/n8n/workflows/**/*.json`` — same (if the tree exists)

Some ``role`` values are display-only (no Brain persona): see ``WORKFLOW_ROLE_ALLOWLIST``.

Reference / template workflows under ``infra/hetzner/workflows/_reference/`` are skipped.
Archived exports under ``infra/hetzner/workflows/archive/`` are skipped.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "apis" / "brain" / "app" / "personas" / "specs"
COMMAND_CENTER = REPO_ROOT / "apps" / "studio" / "src" / "lib" / "command-center.ts"
SYSTEM_GRAPH = REPO_ROOT / "apps" / "studio" / "src" / "data" / "system-graph.json"
HETZNER_WORKFLOWS = REPO_ROOT / "infra" / "hetzner" / "workflows"
DATA_N8N = REPO_ROOT / "data" / "n8n" / "workflows"

# WORKFLOW_META roles that are not PersonaSpec slugs (deterministic jobs or sticky thread routing).
WORKFLOW_ROLE_ALLOWLIST = frozenset(
    {
        "No AI",
        "thread-resolved persona",
    }
)

ROLE_LINE_RE = re.compile(r'^\s+role:\s*"([^"]*)",?\s*$')
# persona_pin in workflow JSON / expression strings
PERSONA_PIN_RE = re.compile(
    r"""persona_pin['\"]?\s*:\s*['\"]([^'\"]+)['\"]""",
    re.IGNORECASE,
)

SKIP_DIRS = frozenset({"archive", "_reference"})


def load_canonical_slugs() -> set[str]:
    if not SPECS_DIR.is_dir():
        print(f"check_persona_vocabulary: missing specs dir: {SPECS_DIR}", file=sys.stderr)
        sys.exit(2)
    slugs = {p.stem for p in SPECS_DIR.glob("*.yaml")}
    if not slugs:
        print("check_persona_vocabulary: zero *.yaml PersonaSpecs", file=sys.stderr)
        sys.exit(2)
    return slugs


def iter_workflow_json_files() -> list[Path]:
    out: list[Path] = []
    if HETZNER_WORKFLOWS.is_dir():
        for path in HETZNER_WORKFLOWS.rglob("*.json"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            out.append(path)
    if DATA_N8N.is_dir():
        out.extend(DATA_N8N.rglob("*.json"))
    return sorted(out)


def check_command_center(canonical: set[str], errors: list[str]) -> None:
    text = COMMAND_CENTER.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = ROLE_LINE_RE.match(line)
        if not m:
            continue
        role = m.group(1)
        if role in WORKFLOW_ROLE_ALLOWLIST:
            continue
        if role not in canonical:
            errors.append(
                f"{COMMAND_CENTER.relative_to(REPO_ROOT)}:{lineno}: unknown WORKFLOW_META role {role!r}"
            )


def check_system_graph(canonical: set[str], errors: list[str]) -> None:
    data = json.loads(SYSTEM_GRAPH.read_text(encoding="utf-8"))
    for node in data.get("nodes", []):
        slug = node.get("owner_persona")
        if not slug:
            continue
        if slug not in canonical:
            errors.append(
                f"{SYSTEM_GRAPH.relative_to(REPO_ROOT)}: node {node.get('id')!r} "
                f"owner_persona={slug!r} is not a PersonaSpec slug"
            )


def check_n8n_workflows(canonical: set[str], errors: list[str]) -> None:
    skip_values = {"REPLACE_WITH_PERSONA_SLUG", ""}
    for path in iter_workflow_json_files():
        raw = path.read_text(encoding="utf-8", errors="replace")
        for m in PERSONA_PIN_RE.finditer(raw):
            val = m.group(1).strip()
            if val in skip_values:
                continue
            if val not in canonical:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}: unknown persona_pin {val!r}"
                )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Print canonical slug count and paths checked.",
    )
    args = ap.parse_args()

    canonical = load_canonical_slugs()
    errors: list[str] = []

    if not COMMAND_CENTER.is_file():
        errors.append(f"missing {COMMAND_CENTER}")
    if not SYSTEM_GRAPH.is_file():
        errors.append(f"missing {SYSTEM_GRAPH}")
    if errors:
        for e in errors:
            print(f"check_persona_vocabulary: {e}", file=sys.stderr)
        return 2

    check_command_center(canonical, errors)
    check_system_graph(canonical, errors)
    check_n8n_workflows(canonical, errors)

    if args.verbose:
        print(f"canonical PersonaSpec slugs ({len(canonical)}): {', '.join(sorted(canonical))}")
        n_json = len(iter_workflow_json_files())
        print(f"scanned {n_json} workflow JSON file(s) under hetzner + data/n8n (if present)")

    if errors:
        print("check_persona_vocabulary: failed —", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
