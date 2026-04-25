#!/usr/bin/env python3
"""Track K — auto-generate the registry table in docs/BRAIN_PERSONAS.md.

The doc has two halves:
  1. A hand-written narrative ("why this exists", routing flow, etc.)
     that only changes when we redesign the platform.
  2. A registry table (personas, models, ceilings, cadences) that must
     track the YAML files exactly. Hand-maintaining this table is how
     we ended up with doc-vs-code drift in the first place.

This script regenerates (2) in place by rewriting everything between
the ``<!-- BEGIN GENERATED -->`` and ``<!-- END GENERATED -->`` markers.
If the markers are missing, we append the block at the bottom.

Run:
    python scripts/generate_brain_personas_doc.py          # in-place rewrite
    python scripts/generate_brain_personas_doc.py --check  # CI mode; exits 1 on drift

CI calls the --check variant in .github/workflows/brain-personas-doc.yaml
so every PR that touches a spec either refreshes the doc or fails.

medallion: ops
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = REPO_ROOT / "apis" / "brain" / "app" / "personas" / "specs"
DOC_PATH = REPO_ROOT / "docs" / "BRAIN_PERSONAS.md"
BEGIN_MARK = "<!-- BEGIN GENERATED: persona-registry -->"
END_MARK = "<!-- END GENERATED: persona-registry -->"


def _load_specs() -> list[dict]:
    specs: list[dict] = []
    for yaml_path in sorted(SPECS_DIR.glob("*.yaml")):
        data = yaml.safe_load(yaml_path.read_text())
        if not isinstance(data, dict):
            continue
        data["_source"] = yaml_path.relative_to(REPO_ROOT).as_posix()
        specs.append(data)
    return specs


def _dollar(v) -> str:
    return f"${float(v):.2f}" if v is not None else "—"


def _int(v) -> str:
    return str(int(v)) if v is not None else "—"


def _short_model(slug: str | None) -> str:
    if not slug:
        return "—"
    # Keep the model family + size prefix so the table stays scannable.
    return (
        slug.replace("claude-", "")
        .replace("-20250514", "")
        .replace("-20250618", "")
        .replace("-20250219", "")
    )


def _badge(v: bool) -> str:
    return "✅" if v else "—"


def _render_registry_table(specs: list[dict]) -> list[str]:
    lines = [
        "| Persona | Default model | Escalation | Ceiling/day | RPM | Max out | Tools | Compliance | Cadence |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in specs:
        lines.append(
            "| `{name}` | `{default}` | `{esc}` | {ceiling} | {rpm} | {max_out} | {tools} | {compliance} | {cadence} |".format(
                name=s["name"],
                default=_short_model(s.get("default_model")),
                esc=_short_model(s.get("escalation_model")),
                ceiling=_dollar(s.get("daily_cost_ceiling_usd")),
                rpm=_int(s.get("requests_per_minute")),
                max_out=_int(s.get("max_output_tokens")),
                tools=_badge(bool(s.get("requires_tools"))),
                compliance=_badge(bool(s.get("compliance_flagged"))),
                cadence=s.get("proactive_cadence", "never"),
            )
        )
    return lines


def _render_escalation_table(specs: list[dict]) -> list[str]:
    lines = [
        "",
        "### Escalation rules",
        "",
        "| Persona | `escalate_if` | Owner channel |",
        "|---|---|---|",
    ]
    for s in specs:
        rules = s.get("escalate_if") or []
        rules_str = ", ".join(f"`{r}`" for r in rules) if rules else "—"
        lines.append(
            "| `{name}` | {rules} | {channel} |".format(
                name=s["name"],
                rules=rules_str,
                channel=f"`#{s['owner_channel']}`" if s.get("owner_channel") else "—",
            )
        )
    return lines


def _render_block(specs: list[dict]) -> str:
    count = len(specs)
    lines = [
        BEGIN_MARK,
        "",
        "## Registered personas",
        "",
        (
            f"_Generated from `apis/brain/app/personas/specs/*.yaml`. "
            f"{count} persona{'s' if count != 1 else ''}. "
            f"Run `python scripts/generate_brain_personas_doc.py` to refresh._"
        ),
        "",
        *_render_registry_table(specs),
        *_render_escalation_table(specs),
        "",
        END_MARK,
    ]
    return "\n".join(lines) + "\n"


def _build_new_doc(current: str, generated_block: str) -> str:
    if BEGIN_MARK in current and END_MARK in current:
        pre, rest = current.split(BEGIN_MARK, 1)
        _, post = rest.split(END_MARK, 1)
        return pre.rstrip() + "\n\n" + generated_block + post.lstrip()
    stripped = current.rstrip() + "\n\n"
    return stripped + generated_block


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the generated block differs from file on disk.",
    )
    args = parser.parse_args()

    specs = _load_specs()
    generated = _render_block(specs)
    current = DOC_PATH.read_text() if DOC_PATH.exists() else ""
    new_doc = _build_new_doc(current, generated)

    if args.check:
        if current == new_doc:
            print(f"OK: {DOC_PATH.relative_to(REPO_ROOT)} is up to date.")
            return 0
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            new_doc.splitlines(keepends=True),
            fromfile=str(DOC_PATH.relative_to(REPO_ROOT)) + " (on disk)",
            tofile=str(DOC_PATH.relative_to(REPO_ROOT)) + " (expected)",
            n=3,
        )
        sys.stdout.writelines(diff)
        print(
            "\nERROR: BRAIN_PERSONAS.md is stale relative to the registry. "
            "Run:\n  python scripts/generate_brain_personas_doc.py",
            file=sys.stderr,
        )
        return 1

    if current == new_doc:
        print(f"Already up to date: {DOC_PATH.relative_to(REPO_ROOT)}")
        return 0
    DOC_PATH.write_text(new_doc)
    print(f"Updated: {DOC_PATH.relative_to(REPO_ROOT)} ({len(specs)} personas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
