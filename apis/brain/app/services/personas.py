"""Deprecated shim — use ``app.personas.routing`` instead.

Kept for one release cycle so external callers don't break on import
while we complete the Track F / H11 migration.

medallion: ops
"""

from __future__ import annotations

import warnings

from app.personas.routing import (
    CHANNEL_BOOST,
    CHANNEL_PERSONA_MAP,
    PHRASE_KEYWORDS,
    SINGLE_WORD_KEYWORDS,
)
from app.personas.routing import (
    route_persona as _route_persona,
)

__all__ = [
    "CHANNEL_BOOST",
    "CHANNEL_PERSONA_MAP",
    "PHRASE_KEYWORDS",
    "SINGLE_WORD_KEYWORDS",
    "route_persona",
]


def route_persona(
    message: str,
    channel_id: str | None = None,
    parent_persona: str | None = None,
    persona_pin: str | None = None,
) -> str:
    """Back-compat wrapper: accepts both ``parent_persona`` and ``persona_pin``.

    New callers should import from ``app.personas.routing`` and use
    ``persona_pin``. This wrapper is scheduled for deletion once all Track H
    callers have migrated.
    """
    if parent_persona is not None and persona_pin is None:
        warnings.warn(
            "route_persona(parent_persona=...) is deprecated, pass persona_pin=... instead",
            DeprecationWarning,
            stacklevel=2,
        )
        persona_pin = parent_persona
    return _route_persona(message, channel_id=channel_id, persona_pin=persona_pin)
