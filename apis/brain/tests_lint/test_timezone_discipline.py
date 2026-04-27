"""Guardrails: avoid naive `datetime.now()` in application code (use UTC)."""

from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"
# `datetime.now()` with an empty argument list (no tz=, no UTC).
_BAD = re.compile(r"\bdatetime\.now\s*\(\s*\)")

def test_no_naive_datetime_now_in_app():
    """`datetime.now()` without a timezone is forbidden in `app/` (Ruff DTZ005)."""
    hits: list[str] = []
    for path in sorted(_APP.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), start=1):
            if "#" in line:
                line = line.split("#", 1)[0]
            if _BAD.search(line):
                hits.append(f"{path.relative_to(_APP.parent)}:{i}:{line.strip()}")
    assert not hits, "Naive datetime.now() found in app/:\n" + "\n".join(hits)
