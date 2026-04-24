"""Unit tests for ``TaxAwareExitCalculator``."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.gold.tax_aware_exit_calculator import (
    DEFAULT_FEDERAL_LT_RATE,
    DEFAULT_FEDERAL_ST_RATE,
    DEFAULT_NIIT_RATE,
    DEFAULT_STATE_RATE,
    ExitLot,
    TaxAwareExitCalculator,
    TaxProfile,
    days_to_long_term,
    long_term_cutoff_date,
)

pytestmark = pytest.mark.no_db


TODAY = date(2026, 4, 21)


def test_happy_path_short_term_gain_single_lot():
    lot = ExitLot(
        shares=Decimal("100"),
        cost_per_share=Decimal("100"),
        acquired_on=TODAY - timedelta(days=90),
    )
    calc = TaxAwareExitCalculator()
    out = calc.evaluate(
        symbol="AAPL",
        current_price=Decimal("150"),
        exit_shares=Decimal("100"),
        lots=[lot],
        as_of=TODAY,
    )
    # Gross proceeds: 100 * 150 = 15000; cost basis: 100 * 100 = 10000; gain: 5000
    assert out.gross_proceeds == Decimal("15000.00")
    assert out.cost_basis == Decimal("10000.00")
    assert out.realized_gain_loss == Decimal("5000.00")
    assert out.short_term_gain_loss == Decimal("5000.00")
    assert out.long_term_gain_loss == Decimal("0.00")
    # Federal ST 37% + state 5% + NIIT 3.8% = 45.8% of 5000 = 2290
    expected_total = Decimal("5000") * (
        DEFAULT_FEDERAL_ST_RATE + DEFAULT_STATE_RATE + DEFAULT_NIIT_RATE
    )
    assert out.total_tax == expected_total.quantize(Decimal("0.01"))
    assert out.after_tax_proceeds == (Decimal("15000") - out.total_tax).quantize(Decimal("0.01"))
    # Days to long-term: match TaxLot (>365); 90 held -> 366 - 90
    assert out.days_to_long_term == 366 - 90
    assert out.days_to_long_term == days_to_long_term(lot.acquired_on, as_of=TODAY)
    assert out.breakeven_price_for_long_term_wait is not None
    assert out.breakeven_price_for_long_term_wait < Decimal("150")
    assert out.tax_advantaged is False


def test_boundary_mixed_short_and_long_lots_are_split_correctly():
    # Two lots: one well past LT threshold, one still ST.
    lt_lot = ExitLot(
        shares=Decimal("50"),
        cost_per_share=Decimal("80"),
        acquired_on=TODAY - timedelta(days=400),
    )
    st_lot = ExitLot(
        shares=Decimal("50"),
        cost_per_share=Decimal("120"),
        acquired_on=TODAY - timedelta(days=100),
    )
    calc = TaxAwareExitCalculator()
    out = calc.evaluate(
        symbol="MSFT",
        current_price=Decimal("200"),
        exit_shares=Decimal("100"),
        lots=[lt_lot, st_lot],
        as_of=TODAY,
    )
    # LT gain: 50 * (200 - 80) = 6000; ST gain: 50 * (200 - 120) = 4000
    assert out.long_term_gain_loss == Decimal("6000.00")
    assert out.short_term_gain_loss == Decimal("4000.00")
    assert out.realized_gain_loss == Decimal("10000.00")
    expected_federal = (
        Decimal("4000") * DEFAULT_FEDERAL_ST_RATE + Decimal("6000") * DEFAULT_FEDERAL_LT_RATE
    )
    assert out.federal_tax == expected_federal.quantize(Decimal("0.01"))
    # days_to_long_term is the minimum remaining on any ST lot
    assert out.days_to_long_term == 366 - 100
    assert out.days_to_long_term == days_to_long_term(st_lot.acquired_on, as_of=TODAY)


def test_empty_zero_exit_shares_returns_zeroed_result():
    calc = TaxAwareExitCalculator()
    out = calc.evaluate(
        symbol="GOOGL",
        current_price=Decimal("140"),
        exit_shares=Decimal("0"),
        lots=[],
        as_of=TODAY,
    )
    assert out.gross_proceeds == Decimal("0.00")
    assert out.total_tax == Decimal("0.00")
    assert out.after_tax_proceeds == Decimal("0.00")
    assert any("zero or negative" in r for r in out.reasons)


def test_tax_advantaged_account_has_no_tax_drag():
    lot = ExitLot(
        shares=Decimal("10"),
        cost_per_share=Decimal("50"),
        acquired_on=TODAY - timedelta(days=30),
    )
    calc = TaxAwareExitCalculator()
    out = calc.evaluate(
        symbol="NVDA",
        current_price=Decimal("800"),
        exit_shares=Decimal("10"),
        lots=[lot],
        as_of=TODAY,
        tax_advantaged=True,
    )
    assert out.tax_advantaged is True
    assert out.total_tax == Decimal("0.00")
    assert out.after_tax_proceeds == out.gross_proceeds
    assert out.days_to_long_term is None


def test_lot_shortfall_returns_zero_and_reason():
    lot = ExitLot(
        shares=Decimal("5"),
        cost_per_share=Decimal("10"),
        acquired_on=TODAY - timedelta(days=10),
    )
    calc = TaxAwareExitCalculator()
    out = calc.evaluate(
        symbol="X",
        current_price=Decimal("20"),
        exit_shares=Decimal("100"),
        lots=[lot],
        as_of=TODAY,
    )
    assert out.shares_exited == Decimal("0")
    assert out.total_tax == Decimal("0.00")
    assert any("cover only" in r for r in out.reasons)


def test_net_loss_produces_zero_tax_and_explanation():
    lot = ExitLot(
        shares=Decimal("10"),
        cost_per_share=Decimal("300"),
        acquired_on=TODAY - timedelta(days=50),
    )
    calc = TaxAwareExitCalculator()
    out = calc.evaluate(
        symbol="X",
        current_price=Decimal("200"),
        exit_shares=Decimal("10"),
        lots=[lot],
        as_of=TODAY,
    )
    assert out.realized_gain_loss == Decimal("-1000.00")
    assert out.total_tax == Decimal("0.00")
    assert any("Net loss" in r for r in out.reasons)


def test_custom_tax_profile_overrides_defaults():
    lot = ExitLot(
        shares=Decimal("10"),
        cost_per_share=Decimal("50"),
        acquired_on=TODAY - timedelta(days=30),
    )
    profile = TaxProfile(
        federal_short_term_rate=Decimal("0.10"),
        federal_long_term_rate=Decimal("0.05"),
        state_rate=Decimal("0"),
        niit_rate=Decimal("0"),
        niit_applies=False,
    )
    calc = TaxAwareExitCalculator(profile)
    out = calc.evaluate(
        symbol="X",
        current_price=Decimal("100"),
        exit_shares=Decimal("10"),
        lots=[lot],
        as_of=TODAY,
    )
    assert out.federal_tax == Decimal("50.00")  # 500 * 10%
    assert out.state_tax == Decimal("0.00")
    assert out.niit_tax == Decimal("0.00")
    assert out.total_tax == Decimal("50.00")


def test_long_term_cutoff_helper_matches_day_count_convention():
    d = date(2024, 1, 1)
    # First date where (d - acq).days > 365 (aligns with TaxLot.is_long_term)
    assert long_term_cutoff_date(d) == d + timedelta(days=366)
    assert days_to_long_term(d, d + timedelta(days=365)) == 1
    assert days_to_long_term(d, d + timedelta(days=366)) == 0
