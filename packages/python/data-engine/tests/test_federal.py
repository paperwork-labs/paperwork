"""Federal-tax tests. Mirror FileFree's TestFederalTax expected values exactly.

If any of these fail, the migration broke math byte-identity for the federal
calculation. The expected values are copy-pasted from
apis/filefree/tests/test_tax_calculator.py:TestFederalTax.
"""

from __future__ import annotations

import pytest

from data_engine import (
    FilingStatus,
    UnknownFilingStatusError,
    calculate_federal_tax,
    get_federal_standard_deduction,
)


class TestFederalStandardDeduction:
    """Mirrors apis/filefree/tests/test_tax_calculator.py::TestStandardDeductions."""

    def test_single(self) -> None:
        assert get_federal_standard_deduction(FilingStatus.SINGLE, 2025) == 1_575_000

    def test_married_jointly(self) -> None:
        assert (
            get_federal_standard_deduction(FilingStatus.MARRIED_FILING_JOINTLY, 2025) == 3_150_000
        )

    def test_married_separately(self) -> None:
        deduction = get_federal_standard_deduction(FilingStatus.MARRIED_FILING_SEPARATELY, 2025)
        assert deduction == 1_575_000

    def test_head_of_household(self) -> None:
        assert (
            get_federal_standard_deduction(FilingStatus.HEAD_OF_HOUSEHOLD, 2025) == 2_362_500
        )


class TestCalculateFederalTax:
    """Verbatim port of apis/filefree/tests/test_tax_calculator.py::TestFederalTax."""

    def test_zero_income(self) -> None:
        assert calculate_federal_tax(0, FilingStatus.SINGLE, 2025) == 0

    def test_negative_income(self) -> None:
        assert calculate_federal_tax(-100_00, FilingStatus.SINGLE, 2025) == 0

    def test_single_10_percent_only(self) -> None:
        assert calculate_federal_tax(1_000_000, FilingStatus.SINGLE, 2025) == 100_000

    def test_single_first_bracket_boundary(self) -> None:
        assert calculate_federal_tax(1_192_500, FilingStatus.SINGLE, 2025) == 119_250

    def test_single_into_12_percent(self) -> None:
        assert calculate_federal_tax(2_000_000, FilingStatus.SINGLE, 2025) == 216_150

    def test_single_second_bracket_boundary(self) -> None:
        assert calculate_federal_tax(4_847_500, FilingStatus.SINGLE, 2025) == 557_850

    def test_single_into_22_percent(self) -> None:
        assert calculate_federal_tax(6_000_000, FilingStatus.SINGLE, 2025) == 811_400

    def test_single_into_24_percent(self) -> None:
        assert calculate_federal_tax(11_000_000, FilingStatus.SINGLE, 2025) == 1_924_700

    def test_married_jointly_10_percent(self) -> None:
        assert (
            calculate_federal_tax(2_000_000, FilingStatus.MARRIED_FILING_JOINTLY, 2025) == 200_000
        )

    def test_married_jointly_first_boundary(self) -> None:
        assert (
            calculate_federal_tax(2_385_000, FilingStatus.MARRIED_FILING_JOINTLY, 2025) == 238_500
        )

    def test_married_jointly_into_12(self) -> None:
        assert (
            calculate_federal_tax(5_000_000, FilingStatus.MARRIED_FILING_JOINTLY, 2025) == 552_300
        )

    def test_head_of_household_10_percent(self) -> None:
        assert (
            calculate_federal_tax(1_500_000, FilingStatus.HEAD_OF_HOUSEHOLD, 2025) == 150_000
        )

    def test_head_of_household_boundary(self) -> None:
        assert (
            calculate_federal_tax(1_700_000, FilingStatus.HEAD_OF_HOUSEHOLD, 2025) == 170_000
        )

    def test_head_of_household_into_12(self) -> None:
        assert (
            calculate_federal_tax(3_000_000, FilingStatus.HEAD_OF_HOUSEHOLD, 2025) == 326_000
        )

    def test_married_separately_same_as_single_at_5m(self) -> None:
        income = 5_000_000
        assert calculate_federal_tax(
            income, FilingStatus.MARRIED_FILING_SEPARATELY, 2025
        ) == calculate_federal_tax(income, FilingStatus.SINGLE, 2025)


class TestErrors:
    def test_unknown_year_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            calculate_federal_tax(1_000_000, FilingStatus.SINGLE, 2099)

    def test_missing_filing_status_raises(self) -> None:
        with pytest.raises(UnknownFilingStatusError):
            get_federal_standard_deduction("not_a_status", 2025)  # type: ignore[arg-type]
