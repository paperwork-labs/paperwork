"""Plain-text scrubbing entrypoints."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pii_scrubber import regexes


class ScrubMode(StrEnum):
    SSN = "SSN"
    EIN = "EIN"
    EMAIL = "EMAIL"
    PHONE_US = "PHONE_US"
    CREDIT_CARD = "CREDIT_CARD"
    IP_ADDRESS = "IP_ADDRESS"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    JWT = "JWT"
    API_KEY = "API_KEY"


@dataclass(frozen=True, slots=True)
class ScrubResult:
    """Outcome of :func:`scrub` (text plus per-mode replacement counts)."""

    text: str
    replacements_by_mode: Mapping[ScrubMode, int]

    @property
    def total_replacements(self) -> int:
        return int(sum(self.replacements_by_mode.values(), 0))


def _luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or not (13 <= len(digits) <= 19):
        return False
    if len(set(digits)) == 1:
        return False
    total = 0
    reverse_digits = digits[::-1]
    for idx, ch in enumerate(reverse_digits):
        n = int(ch)
        if idx % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _digits_only(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


_SCRUB_ORDER: Final[tuple[ScrubMode, ...]] = (
    ScrubMode.JWT,
    ScrubMode.CREDIT_CARD,
    ScrubMode.SSN,
    ScrubMode.EIN,
    ScrubMode.PHONE_US,
    ScrubMode.EMAIL,
    ScrubMode.IP_ADDRESS,
    ScrubMode.BANK_ACCOUNT,
    ScrubMode.API_KEY,
)

_COMPILED: Final[dict[ScrubMode, re.Pattern[str]]] = {
    ScrubMode.SSN: re.compile(regexes.SSN),
    ScrubMode.EIN: re.compile(regexes.EIN),
    ScrubMode.EMAIL: re.compile(regexes.EMAIL),
    ScrubMode.PHONE_US: re.compile(regexes.PHONE_US),
    ScrubMode.CREDIT_CARD: re.compile(regexes.CREDIT_CARD),
    ScrubMode.IP_ADDRESS: re.compile(regexes.IP_ADDRESS),
    ScrubMode.BANK_ACCOUNT: re.compile(regexes.BANK_ACCOUNT),
    ScrubMode.JWT: re.compile(regexes.JWT),
    ScrubMode.API_KEY: re.compile(regexes.API_KEY),
}


def _credit_card_repl(match: re.Match[str]) -> str:
    digits = _digits_only(match.group(0))
    if _luhn_ok(digits):
        return f"[REDACTED:{ScrubMode.CREDIT_CARD.name}]"
    return match.group(0)


def scrub(
    text: str,
    *,
    modes: list[ScrubMode] | None = None,
) -> ScrubResult:
    """Redact PII-shaped spans using regex replacement.

    Returns scrubbed text and counts per active mode. A second pass over
    ``ScrubResult.text`` should perform zero replacements (idempotent tokens).
    """
    active: set[ScrubMode] = set(modes) if modes is not None else set(ScrubMode)
    counts: dict[ScrubMode, int] = dict.fromkeys(active, 0)

    out = text
    for mode in _SCRUB_ORDER:
        if mode not in active:
            continue
        pattern = _COMPILED[mode]

        if mode is ScrubMode.CREDIT_CARD:

            def _cc_sub(m: re.Match[str]) -> str:
                repl = _credit_card_repl(m)
                if repl != m.group(0):
                    counts[ScrubMode.CREDIT_CARD] += 1
                return repl

            out = pattern.sub(_cc_sub, out)
            continue

        token = f"[REDACTED:{mode.name}]"

        def _make_sub(
            _m: re.Match[str],
            *,
            _mode: ScrubMode = mode,
            _token: str = token,
        ) -> str:
            counts[_mode] += 1
            return _token

        out, _n = pattern.subn(_make_sub, out)

    return ScrubResult(text=out, replacements_by_mode=counts)
