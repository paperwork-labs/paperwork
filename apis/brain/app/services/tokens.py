"""Accurate token counting using tiktoken.

Used by PersonaPinnedRoute's `tokens>N` escalation rule. Falls back to
the conservative char-based heuristic (len/4) only if tiktoken cannot
load an encoder — we log a warning on the fallback so we notice if it
happens in production, rather than silently drifting.

Caching: encoders are module-level so we pay the initialization cost
once per process.

medallion: ops
"""
from __future__ import annotations

import logging
from functools import lru_cache

import tiktoken

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _encoding_for(model: str) -> tiktoken.Encoding | None:
    """Best-effort encoder lookup. Returns None if tiktoken has no mapping."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        pass
    # Reasonable default for GPT-4/Claude-compatible token counts.
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        logger.warning("tiktoken failed to initialize cl100k_base encoding")
        return None


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Exact token count for text using the model's encoder.

    Falls back to a char/4 heuristic with a warning if tiktoken is not
    available, so token-threshold escalation still works in degraded
    environments.
    """
    enc = _encoding_for(model)
    if enc is None:
        logger.warning("tiktoken unavailable; using char/4 heuristic")
        return len(text) // 4
    return len(enc.encode(text))
