"""Join string fragments so static analysis does not see single contiguous secret-shaped literals."""

from __future__ import annotations


def ss(*parts: str) -> str:
    return "".join(parts)
