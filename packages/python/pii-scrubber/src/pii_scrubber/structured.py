"""Structured (JSON-like) data scrubbing."""

from __future__ import annotations

from typing import Any

from pii_scrubber.scrubber import scrub


def scrub_dict(d: dict[str, Any], *, recursive: bool = True) -> dict[str, Any]:
    """Return a copy of ``d`` with string values passed through :func:`scrub`.

    When ``recursive`` is true, walks nested dicts and lists; non-string
    scalars are preserved. Dict keys are not scrubbed.
    """
    return {k: _scrub_value(v, recursive=recursive) for k, v in d.items()}


def _scrub_value(value: Any, *, recursive: bool) -> Any:
    if isinstance(value, str):
        return scrub(value).text
    if not recursive:
        return value
    if isinstance(value, dict):
        return scrub_dict(value, recursive=recursive)
    if isinstance(value, list):
        return [_scrub_value(item, recursive=recursive) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub_value(item, recursive=recursive) for item in value)
    return value
