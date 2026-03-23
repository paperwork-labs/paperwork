"""D11: PII scrubbing — regex-based scrubbing before any text enters storage.
P1: SSN, EIN, CC, phone, bank routing. P2: extended patterns. P9: Presidio NER."""

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "***-**-****"),
    (re.compile(r"\b\d{2}-\d{7}\b"), "**-*******"),
    (re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"), "****-****-****-****"),
    (re.compile(r"\b\d{9}\b(?=.*(?:routing|ABA|bank))"), "*********"),
    (re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "(***) ***-****"),
]


def scrub_pii(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
