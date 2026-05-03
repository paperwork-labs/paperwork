"""Parse human-entered currency strings into :class:`money.types.Money`."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from money.types import Money

# Optional ISO-like prefix (we only normalize case; validation is loose).
_PREFIX_RE = re.compile(r"^(?P<pfx>[A-Za-z]{3})\s+(?P<rest>.+)$")
_PARENS_NEG_RE = re.compile(r"^\(\s*(?P<body>[^)]+)\s*\)$")


def signed_decimal_from_amount_text(text: str) -> Decimal:
    """Parse amount text (``$``, commas, parens) into a signed ``Decimal``.

    For strings with a three-letter currency prefix, use
    :func:`parse_currency_string` instead.

    Raises:
        ValueError: Empty, malformed, or not a finite decimal amount.
    """
    raw = text.strip()
    if not raw:
        msg = "amount text is empty"
        raise ValueError(msg)

    body = raw
    negative = False
    m_paren = _PARENS_NEG_RE.match(body)
    if m_paren:
        negative = True
        body = m_paren.group("body").strip()

    body = body.replace(",", "").strip()
    if body.startswith("("):
        msg = f"unbalanced or invalid parentheses in amount text: {text!r}"
        raise ValueError(msg)

    if body.startswith("+"):
        body = body[1:].strip()

    if body.startswith("-"):
        negative = not negative
        body = body[1:].strip()

    body = body.removeprefix("$").strip()
    if body.startswith("-"):
        negative = not negative
        body = body[1:].strip()
    if body.startswith("+"):
        body = body[1:].strip()

    if not body or not _looks_like_decimal(body):
        msg = f"not a valid amount: {text!r}"
        raise ValueError(msg)

    try:
        d = Decimal(body)
    except InvalidOperation as e:
        msg = f"not a valid amount: {text!r}"
        raise ValueError(msg) from e
    if not d.is_finite():
        msg = f"amount must be finite: {text!r}"
        raise ValueError(msg)

    if negative:
        d = -d
    return d


def parse_currency_string(s: str) -> Money:
    """Parse a currency amount into :class:`Money` (default currency ``USD``).

    Accepted shapes (whitespace stripped first):

    * ``$1,234.56`` or ``1234.56``
    * ``USD 1,234.56`` / ``usd  99.00`` (three-letter prefix + amount)
    * ``(1,234.56)`` meaning negative ``-1234.56``
    * ``-$42.00``, ``$-42.00``

    Raises:
        ValueError: Empty, malformed, or not a finite decimal amount.
    """
    from money.types import Money

    raw = s.strip()
    if not raw:
        msg = "currency string is empty"
        raise ValueError(msg)

    currency = "USD"
    body = raw
    m_prefix = _PREFIX_RE.match(raw)
    if m_prefix:
        currency = m_prefix.group("pfx").upper()
        body = m_prefix.group("rest").strip()

    d = signed_decimal_from_amount_text(body)
    cents_dec = (d * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP)
    cents = int(cents_dec)
    return Money(cents=cents, currency=currency)


def _looks_like_decimal(body: str) -> bool:
    if body.count(".") > 1:
        return False
    return bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", body))
