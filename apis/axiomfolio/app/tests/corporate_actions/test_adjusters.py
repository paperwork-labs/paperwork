"""Pure-math tests for corporate-action adjusters.

These run without a database (``no_db`` marker). They pin the cardinal
invariants:

* Total cost basis is preserved across split-style adjustments.
* Cash dividends never mutate quantity / cost basis.
* Cash mergers close the position (qty -> 0) and credit the right cash.
* Stock mergers carry cost basis to the new symbol.
* Decimal precision is honored end-to-end (no float drift).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.corporate_actions.adjusters import (
    adjust_for_cash_dividend,
    adjust_for_merger_cash,
    adjust_for_merger_stock,
    adjust_for_reverse_split,
    adjust_for_split,
    adjust_for_stock_dividend,
    decimal_ratio,
)

pytestmark = pytest.mark.no_db


# ---------------------------------------------------------------------------
# decimal_ratio
# ---------------------------------------------------------------------------


def test_decimal_ratio_basic() -> None:
    assert decimal_ratio(3, 1) == Decimal("3")
    assert decimal_ratio(1, 4) == Decimal("0.25")


def test_decimal_ratio_accepts_float_strings_and_decimal() -> None:
    # Floats route through str() -> Decimal so 0.1 doesn't drift.
    assert decimal_ratio(0.1, 1) == Decimal("0.1")
    assert decimal_ratio("21", "20") == Decimal("1.05")
    assert decimal_ratio(Decimal("3"), Decimal("2")) == Decimal("1.5")


def test_decimal_ratio_rejects_zero_denominator() -> None:
    with pytest.raises(ValueError):
        decimal_ratio(1, 0)


# ---------------------------------------------------------------------------
# Forward split
# ---------------------------------------------------------------------------


def test_forward_split_3_for_1_preserves_total_basis() -> None:
    # Held 100 @ $150 = $15,000 cost basis.
    result = adjust_for_split(
        current_qty=Decimal("100"),
        current_cost_basis=Decimal("15000"),
        ratio_numerator=3,
        ratio_denominator=1,
    )
    assert result.new_qty == Decimal("300.000000")
    assert result.new_cost_basis == Decimal("15000.0000")
    assert result.new_avg_cost == Decimal("50.00000000")
    assert result.cash_credited == Decimal("0")
    assert result.new_symbol is None


def test_forward_split_2_for_1_with_fractional_share() -> None:
    # 12.5 shares @ $80, 2-for-1 split -> 25 shares, $40 avg, basis unchanged.
    result = adjust_for_split(
        current_qty=Decimal("12.5"),
        current_cost_basis=Decimal("1000"),
        ratio_numerator=2,
        ratio_denominator=1,
    )
    assert result.new_qty == Decimal("25.000000")
    assert result.new_cost_basis == Decimal("1000.0000")
    assert result.new_avg_cost == Decimal("40.00000000")


def test_forward_split_rejects_zero_or_negative_multiplier() -> None:
    with pytest.raises(ValueError):
        # 0-for-1 is nonsense.
        adjust_for_split(100, 1000, 0, 1)


# ---------------------------------------------------------------------------
# Reverse split
# ---------------------------------------------------------------------------


def test_reverse_split_1_for_10() -> None:
    # 1000 @ $0.50 = $500. After 1:10 reverse: 100 @ $5, basis intact.
    result = adjust_for_reverse_split(
        current_qty=Decimal("1000"),
        current_cost_basis=Decimal("500"),
        ratio_numerator=1,
        ratio_denominator=10,
    )
    assert result.new_qty == Decimal("100.000000")
    assert result.new_cost_basis == Decimal("500.0000")
    assert result.new_avg_cost == Decimal("5.00000000")


def test_reverse_split_produces_fractional_share() -> None:
    # 17 shares 1-for-3 reverse -> 5.666666 shares (provider would
    # actually round-down + cash-in-lieu, but the math itself preserves
    # basis to the share-fraction the provider hands us).
    result = adjust_for_reverse_split(
        current_qty=Decimal("17"),
        current_cost_basis=Decimal("100"),
        ratio_numerator=1,
        ratio_denominator=3,
    )
    # 17/3 = 5.666666... -> banker's-rounded to 6 dp.
    assert result.new_qty == Decimal("5.666667")
    assert result.new_cost_basis == Decimal("100.0000")


# ---------------------------------------------------------------------------
# Stock dividend
# ---------------------------------------------------------------------------


def test_stock_dividend_5_percent() -> None:
    # 5% bonus shares = 21-for-20.
    result = adjust_for_stock_dividend(
        current_qty=Decimal("100"),
        current_cost_basis=Decimal("10000"),
        ratio_numerator=21,
        ratio_denominator=20,
    )
    assert result.new_qty == Decimal("105.000000")
    assert result.new_cost_basis == Decimal("10000.0000")
    # 10000 / 105 ~= 95.23809524 -- rounds half-even to 8 dp.
    assert result.new_avg_cost == Decimal("95.23809524")


# ---------------------------------------------------------------------------
# Cash dividend
# ---------------------------------------------------------------------------


def test_cash_dividend_does_not_change_qty_or_basis() -> None:
    result = adjust_for_cash_dividend(
        current_qty=Decimal("250"),
        current_cost_basis=Decimal("12500"),
        cash_per_share=Decimal("0.88"),
    )
    assert result.new_qty == Decimal("250.000000")
    assert result.new_cost_basis == Decimal("12500.0000")
    assert result.new_avg_cost == Decimal("50.00000000")
    assert result.cash_credited == Decimal("220.0000")  # 250 * 0.88
    assert result.new_symbol is None


def test_cash_dividend_zero_qty_returns_zero_cash() -> None:
    # Defensive: if a stale audit run hits a fully-closed lot, we must
    # not divide by zero in the avg-cost computation.
    result = adjust_for_cash_dividend(
        current_qty=Decimal("0"),
        current_cost_basis=Decimal("0"),
        cash_per_share=Decimal("1.00"),
    )
    assert result.new_qty == Decimal("0.000000")
    assert result.cash_credited == Decimal("0.0000")
    assert result.new_avg_cost == Decimal("0")


# ---------------------------------------------------------------------------
# Stock-for-stock merger
# ---------------------------------------------------------------------------


def test_stock_merger_carries_basis_and_renames() -> None:
    # 100 ATVI @ $90 (basis $9000) -> 0.945 MSFT per ATVI.
    result = adjust_for_merger_stock(
        current_qty=Decimal("100"),
        current_cost_basis=Decimal("9000"),
        target_symbol="msft",  # lowercase on purpose
        ratio_numerator=Decimal("0.945"),
        ratio_denominator=Decimal("1"),
    )
    assert result.new_qty == Decimal("94.500000")
    assert result.new_cost_basis == Decimal("9000.0000")
    # 9000 / 94.5 = 95.23809523... -> 8 dp banker-rounded.
    assert result.new_avg_cost == Decimal("95.23809524")
    assert result.new_symbol == "MSFT"
    assert result.cash_credited == Decimal("0")


def test_stock_merger_requires_target_symbol() -> None:
    with pytest.raises(ValueError):
        adjust_for_merger_stock(
            current_qty=100,
            current_cost_basis=1000,
            target_symbol="",
            ratio_numerator=1,
            ratio_denominator=1,
        )


# ---------------------------------------------------------------------------
# Cash merger / buyout
# ---------------------------------------------------------------------------


def test_cash_merger_closes_position_and_credits_cash() -> None:
    # 200 shares cashed out at $30 -> $6000, position gone.
    result = adjust_for_merger_cash(
        current_qty=Decimal("200"),
        current_cost_basis=Decimal("4500"),
        cash_per_share=Decimal("30"),
    )
    assert result.new_qty == Decimal("0")
    assert result.new_cost_basis == Decimal("0")
    assert result.new_avg_cost == Decimal("0")
    assert result.cash_credited == Decimal("6000.0000")
    assert result.new_symbol is None


# ---------------------------------------------------------------------------
# Float coercion safety -- ensure provider-supplied floats don't drift.
# ---------------------------------------------------------------------------


def test_float_inputs_do_not_introduce_binary_drift() -> None:
    # 0.1 + 0.2 != 0.3 in float; we route through str() -> Decimal.
    result = adjust_for_cash_dividend(
        current_qty=10.0,
        current_cost_basis=100.0,
        cash_per_share=0.3,
    )
    assert result.cash_credited == Decimal("3.0000")
