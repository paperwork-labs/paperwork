#!/usr/bin/env python3
"""Fail CI if Brain persona contracts drift.

Three invariants must always hold:

1. Every slug referenced by the keyword router in
   `app/services/personas.py` (SINGLE_WORD_KEYWORDS + PHRASE_KEYWORDS +
   CHANNEL_PERSONA_MAP) must have a typed YAML spec in
   `app/personas/specs/<slug>.yaml`. Otherwise the router returns a
   persona name that bypasses PersonaPinnedRoute and falls back to
   ClassifyAndRoute — silently — which is the kind of drift we're
   trying to prevent.

2. Every YAML spec must have a matching `.cursor/rules/<slug>.mdc`
   file. The mdc carries the persona's written instructions that
   Brain loads at runtime; if it's missing, we'll 404 against GitHub
   on every request for that persona.

3. The reverse isn't enforced: .mdc files can exist without a spec
   (e.g. `no-silent-fallback.mdc`, `git-workflow.mdc`) because those
   are code-assistant rules, not Brain personas.

Run locally:
    .venv/bin/python apis/brain/scripts/check_persona_coverage.py

Run in CI (see .github/workflows/brain-tests.yaml).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPECS_DIR = REPO_ROOT / "apis" / "brain" / "app" / "personas" / "specs"
MDC_DIR = REPO_ROOT / ".cursor" / "rules"


def _router_persona_slugs() -> set[str]:
    """Extract every persona the keyword router can return.

    We import the module instead of re-parsing text so the check stays
    honest even if the keyword lists get reshuffled.
    """
    sys.path.insert(0, str(REPO_ROOT / "apis" / "brain"))
    from app.personas.routing import (
        CHANNEL_PERSONA_MAP,
        PHRASE_KEYWORDS,
        SINGLE_WORD_KEYWORDS,
    )

    slugs = set(SINGLE_WORD_KEYWORDS.keys())
    slugs |= set(PHRASE_KEYWORDS.keys())
    slugs |= set(CHANNEL_PERSONA_MAP.values())
    return slugs


def _yaml_spec_slugs() -> set[str]:
    return {p.stem for p in SPECS_DIR.glob("*.yaml")}


def _mdc_slugs() -> set[str]:
    return {p.stem for p in MDC_DIR.glob("*.mdc")}


def main() -> int:
    router = _router_persona_slugs()
    specs = _yaml_spec_slugs()
    mdcs = _mdc_slugs()

    failures: list[str] = []

    missing_specs = router - specs
    if missing_specs:
        failures.append(
            "Router can return persona(s) with no YAML spec "
            "(will silently bypass PersonaPinnedRoute): " + ", ".join(sorted(missing_specs))
        )

    missing_mdcs = specs - mdcs
    if missing_mdcs:
        failures.append(
            "YAML spec(s) have no matching .cursor/rules/<name>.mdc "
            "(runtime persona-instruction load will 404): " + ", ".join(sorted(missing_mdcs))
        )

    orphan_specs = specs - router
    if orphan_specs:
        failures.append(
            "YAML spec(s) exist for personas the router can't produce "
            "(dead contracts): " + ", ".join(sorted(orphan_specs))
        )

    if failures:
        for _f in failures:
            pass
        return 1

    mdcs - specs
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
