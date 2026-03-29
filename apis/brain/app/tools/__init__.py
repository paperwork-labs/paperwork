"""Brain tools — shared utilities for PII scrubbing and observation trimming."""

from app.services.pii import scrub_pii

__all__ = ["scrub_pii", "trim_output"]


def trim_output(text: str, max_chars: int = 4000) -> str:
    """Trim tool output to stay within reasonable context window limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... (trimmed, {len(text) - max_chars} chars omitted)"
