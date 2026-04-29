"""Persona coverage — count Brain persona YAML specs (business surface area).

medallion: ops
"""

from __future__ import annotations

from pathlib import Path


def _cursor_rules_dir() -> Path | None:
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / ".cursor" / "rules"
        if candidate.is_dir():
            return candidate
    return None


def collect() -> tuple[float, bool, str]:
    here = Path(__file__).resolve()
    personas_dir = here.parents[2] / "personas"
    specs = personas_dir / "specs"
    n = 0
    if specs.is_dir():
        n = len(list(specs.glob("*.yaml")))

    cr = _cursor_rules_dir()
    extras = len(list(cr.glob("*.mdc"))) if cr is not None else 0

    persona_count = n + extras
    score = float(min(100.0, persona_count * 5))
    note = (
        f"Counted {n} personas/specs/*.yaml + {extras} persona-shaped .cursor/rules *.mdc; "
        f"score=min(100,count*5)={score:.1f}"
    )
    return (score, True, note)
