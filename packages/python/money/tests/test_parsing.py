"""Tests for :mod:`money.parsing`."""

from __future__ import annotations

import pytest

from money import Money, parse_currency_string


def test_parse_plain_dollars() -> None:
    m = parse_currency_string("$1,234.56")
    assert m == Money.from_cents(123_456)


def test_parse_no_dollar_sign() -> None:
    assert parse_currency_string("  99.00 ").cents == 9900


def test_parse_negative_parens() -> None:
    m = parse_currency_string("(1,234.56)")
    assert m.cents == -123_456


def test_parse_usd_prefix() -> None:
    m = parse_currency_string("USD 1,234.56")
    assert m.cents == 123_456
    assert m.currency == "USD"


def test_parse_lowercase_prefix() -> None:
    m = parse_currency_string("eur 10.00")
    assert m.cents == 1000
    assert m.currency == "EUR"


def test_parse_minus_before_dollar() -> None:
    assert parse_currency_string("-$10.00").cents == -1000


def test_parse_dollar_after_minus() -> None:
    assert parse_currency_string("$-10.00").cents == -1000


def test_parse_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_currency_string("")
    with pytest.raises(ValueError, match="empty"):
        parse_currency_string("   ")


def test_parse_malformed_double_dot() -> None:
    with pytest.raises(ValueError):
        parse_currency_string("12.34.56")


def test_parse_malformed_bad_chars() -> None:
    with pytest.raises(ValueError):
        parse_currency_string("$12a.00")


def test_parse_unbalanced_open_paren() -> None:
    with pytest.raises(ValueError, match="unbalanced"):
        parse_currency_string("(12.00")


def test_parse_prefix_only_raises() -> None:
    with pytest.raises(ValueError):
        parse_currency_string("USD")


def test_roundtrip_str_parse() -> None:
    original = Money.from_cents(987654)
    again = parse_currency_string(str(original))
    assert again == original


def test_parse_positive_explicit() -> None:
    assert parse_currency_string("+$5.00").cents == 500


def test_signed_decimal_empty() -> None:
    from money.parsing import signed_decimal_from_amount_text

    with pytest.raises(ValueError, match="empty"):
        signed_decimal_from_amount_text("  ")


def test_signed_decimal_invalid_operation_branch() -> None:
    # `_looks_like_decimal` gate should prevent InvalidOperation; keep regex tight.
    from money.parsing import signed_decimal_from_amount_text

    with pytest.raises(ValueError):
        signed_decimal_from_amount_text("not-a-number")
