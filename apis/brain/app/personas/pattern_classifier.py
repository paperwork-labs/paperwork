"""Heuristic pattern compliance — regulated / promotional content (stub).

medallion: ops
"""

from __future__ import annotations

import re
from typing import Final

_DEFAULT_FORBIDDEN_SUBSTRINGS: Final[tuple[str, ...]] = (
    "guaranteed return",
    "risk free",
    "riskfree",
    "double your money",
)

_CASHTAG_RE = re.compile(r"\$[A-Z]{1,5}\b")


def _normalize_for_scan(text: str) -> str:
    lowered = text.lower()
    return lowered.replace("-", " ").replace("\u2014", " ").replace("\u2013", " ")


def pattern_contains_regulated_claims(
    text: str,
    *,
    forbidden_tickers: list[str] | None = None,
    extra_forbidden_phrases: list[str] | None = None,
) -> tuple[bool, str]:
    """Return (True, reason) if text matches forbidden promotional / ticker rules."""
    norm = _normalize_for_scan(text)
    for phrase in _DEFAULT_FORBIDDEN_SUBSTRINGS:
        if phrase in norm:
            return True, f"forbidden_claim:{phrase.replace(' ', '_')}"

    extra = list(extra_forbidden_phrases or ())
    for phrase in extra:
        p = phrase.strip().lower().replace("-", " ")
        if p and p in norm:
            return True, f"forbidden_claim:{p.replace(' ', '_')}"

    tickers = [t.strip().upper().lstrip("$") for t in (forbidden_tickers or ()) if t.strip()]
    upper_blob = text.upper()
    for t in tickers:
        if f"${t}" in upper_blob or re.search(rf"\b{t}\b", upper_blob):
            return True, f"ticker_reference:{t}"

    if _CASHTAG_RE.search(text):
        return True, "ticker_cashtag"

    return False, "ok"


def classify_pattern_compliance(
    text: str,
    *,
    forbidden_tickers: list[str] | None = None,
    extra_forbidden_phrases: list[str] | None = None,
) -> str:
    """Map pattern text to a voice_system compliance level string."""
    violates, _reason = pattern_contains_regulated_claims(
        text,
        forbidden_tickers=forbidden_tickers,
        extra_forbidden_phrases=extra_forbidden_phrases,
    )
    if violates:
        return "regulated_promotional"
    return "regulated_safe"
