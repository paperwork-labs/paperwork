"""Heuristic pattern compliance for persona voice / social drafts (stub).

Detects marketing-style claims and ticker callouts that must not propagate
unchecked. LLM-based classification is deferred; this module is the
deterministic gate.

medallion: ops
"""

from __future__ import annotations

import re

# Substrings treated as regulated / noncompliant claims (case-insensitive).
FORBIDDEN_CLAIM_FRAGMENTS: tuple[str, ...] = (
    "guaranteed return",
    "risk-free",
    "risk free",
    "double your money",
)

# Cashtagged or dollar-prefixed tickers (ticker-specific promotion risk).
_TICKER_RE = re.compile(r"(?:^|\s)\$[A-Za-z]{1,6}(?:\b|$)")


def pattern_contains_regulated_content(pattern: str) -> tuple[bool, str]:
    """Return (True, reason_code) when *pattern* should not be pulled or published as-is."""
    if not pattern.strip():
        return False, ""
    lower = pattern.lower()
    for frag in FORBIDDEN_CLAIM_FRAGMENTS:
        if frag in lower:
            return True, f"forbidden_claim:{frag}"
    if _TICKER_RE.search(pattern):
        return True, "ticker_specific_reference"
    return False, ""


def is_regulated_pattern(pattern: str) -> bool:
    """True if *pattern* matches any regulated-content rule (convenience wrapper)."""
    blocked, _ = pattern_contains_regulated_content(pattern)
    return blocked
