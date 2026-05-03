"""Table-driven state-tax tests for the data_engine port.

Expected values were computed by manually walking the canonical JSON
(packages/data/src/tax/2025/{CA,NY,TX,DC}.json) with the same algorithm as
packages/data/src/engine/tax.ts. The drift test (test_drift.py) re-verifies
parity against the TS engine when `node` is available.

All amounts in integer cents. Rates in integer basis points.
"""

from __future__ import annotations

import pytest

from data_engine import (
    DEFAULT_TAX_YEAR,
    FilingStatus,
    StateCode,
    calculate_state_tax,
    get_all_tax_states,
    get_available_tax_years,
    get_state_tax_rules,
)
from data_engine._round import round_half_up_div


class TestRoundHalfUpDiv:
    """Verify the rounding helper matches JS Math.round byte-for-byte."""

    @pytest.mark.parametrize(
        ("numerator", "denominator", "expected"),
        [
            (0, 1, 0),
            (1, 2, 1),
            (3, 2, 2),
            (5, 2, 3),
            (-1, 2, 0),
            (-3, 2, -1),
            (-5, 2, -2),
            (-3, 1, -3),
            (3, 1, 3),
            (1192500 * 1000, 10_000, 119250),
            (3655000 * 1200, 10_000, 438600),
            (1152500 * 2200, 10_000, 253550),
            (1234567 * 2200, 10_000, 271605),
        ],
    )
    def test_matches_math_round(self, numerator: int, denominator: int, expected: int) -> None:
        assert round_half_up_div(numerator, denominator) == expected

    def test_zero_denominator_raises(self) -> None:
        with pytest.raises(ValueError, match="denominator must be positive"):
            round_half_up_div(100, 0)


class TestCaliforniaProgressive:
    """CA is progressive across many brackets — exercises the full loop."""

    def test_below_deduction_returns_zero(self) -> None:
        assert calculate_state_tax(StateCode.CA, 500_000, FilingStatus.SINGLE, 2025) == 0

    def test_zero_income(self) -> None:
        assert calculate_state_tax(StateCode.CA, 0, FilingStatus.SINGLE, 2025) == 0

    def test_50k_single(self) -> None:
        # gross = 5,000,000; std deduction = 570,600; taxable = 4,429,400
        # 1% on 1,107,900 = 11,079
        # 2% on 1,518,500 = 30,370
        # 4% on 1,518,800 = 60,752
        # 6% on 284,200   = 17,052
        # total           = 119,253
        assert calculate_state_tax(StateCode.CA, 5_000_000, FilingStatus.SINGLE, 2025) == 119_253

    def test_50k_married_jointly(self) -> None:
        # gross = 5,000,000; std deduction = 1,141,200; taxable = 3,858,800
        # 1% on 2,215,800 = 22,158
        # 2% on 1,643,000 = 32,860
        # total           = 55,018
        assert calculate_state_tax(
            StateCode.CA, 5_000_000, FilingStatus.MARRIED_FILING_JOINTLY, 2025
        ) == 55_018


class TestNewYorkProgressive:
    """NY has the smaller standard deduction; tests bracket walking."""

    def test_50k_single(self) -> None:
        # gross = 5,000,000; std deduction = 800,000; taxable = 4,200,000
        # 4.00% on 850,000   = 34,000
        # 4.50% on 320,000   = 14,400
        # 5.25% on 220,000   = 11,550
        # 5.50% on 2,810,000 = 154,550
        # total              = 214,500
        assert calculate_state_tax(StateCode.NY, 5_000_000, FilingStatus.SINGLE, 2025) == 214_500

    def test_below_first_bracket(self) -> None:
        # gross = 1,000,000; std deduction = 800,000; taxable = 200,000
        # 4% on 200,000 = 8,000
        assert calculate_state_tax(StateCode.NY, 1_000_000, FilingStatus.SINGLE, 2025) == 8_000


class TestTexasNoTax:
    """TX is the canonical income_tax.type=='none' case."""

    def test_returns_zero_for_any_income(self) -> None:
        assert calculate_state_tax(StateCode.TX, 0, FilingStatus.SINGLE, 2025) == 0
        assert calculate_state_tax(StateCode.TX, 100_000_000, FilingStatus.SINGLE, 2025) == 0

    def test_returns_zero_for_any_filing_status(self) -> None:
        for status in FilingStatus:
            assert calculate_state_tax(StateCode.TX, 5_000_000, status, 2025) == 0


class TestDistrictOfColumbia:
    """DC has a generous standard deduction — exercises the deduction subtraction."""

    def test_50k_single(self) -> None:
        # gross = 5,000,000; std deduction = 1,575,000; taxable = 3,425,000
        # 4% on 1,000,000 = 40,000
        # 6% on 2,425,000 = 145,500
        # total           = 185,500
        assert calculate_state_tax(StateCode.DC, 5_000_000, FilingStatus.SINGLE, 2025) == 185_500


class TestEdgeCases:
    def test_unknown_year_returns_none(self) -> None:
        assert calculate_state_tax(StateCode.CA, 5_000_000, FilingStatus.SINGLE, 2099) is None

    def test_get_state_rules_unknown_year(self) -> None:
        assert get_state_tax_rules(StateCode.CA, 2099) is None

    def test_get_state_rules_known_year(self) -> None:
        rules = get_state_tax_rules(StateCode.CA, 2025)
        assert rules is not None
        assert rules.state == StateCode.CA
        assert rules.tax_year == 2025

    def test_default_year_constant(self) -> None:
        # Sanity: DEFAULT_TAX_YEAR mirrors the TS engine's value.
        assert DEFAULT_TAX_YEAR == 2026


class TestDirectoryDiscovery:
    def test_lists_all_tax_years_on_disk(self) -> None:
        years = get_available_tax_years()
        assert 2024 in years
        assert 2025 in years
        assert 2026 in years
        assert sorted(years) == years

    def test_lists_all_states_for_2025(self) -> None:
        states = get_all_tax_states(2025)
        assert StateCode.CA in states
        assert StateCode.NY in states
        assert StateCode.TX in states
        assert StateCode.DC in states
        assert len(states) >= 50  # 50 states + DC; some years may be a subset
