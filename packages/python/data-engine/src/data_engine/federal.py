"""Federal IRS bracket engine. Reads packages/data/src/federal/{year}.json.

Wave K3 introduced this module + the canonical federal data file as the
fix for FileFree's hand-rolled tax-data/2025.json duplicate. Math semantics
match the state engine: integer cents in, basis-points rates, half-up
rounding via round_half_up_div.
"""

from __future__ import annotations

from data_engine._round import round_half_up_div
from data_engine.loader import (
    clear_all_caches as _clear_all_caches,
)
from data_engine.loader import (
    get_available_federal_years as _loader_get_available_federal_years,
)
from data_engine.loader import (
    load_federal,
)
from data_engine.schemas.common import FilingStatus
from data_engine.schemas.federal import FederalBracket, FederalTaxRules

DEFAULT_FEDERAL_YEAR: int = 2026


class UnknownFilingStatusError(ValueError):
    """Raised when no federal data exists for the requested filing status."""


def get_federal_rules(year: int = DEFAULT_FEDERAL_YEAR) -> FederalTaxRules | None:
    """Return federal rules for the year, or None if no file on disk."""
    try:
        return load_federal(year)
    except FileNotFoundError:
        return None


def get_available_federal_years() -> list[int]:
    return _loader_get_available_federal_years()


def get_federal_standard_deduction(
    filing_status: FilingStatus,
    year: int = DEFAULT_FEDERAL_YEAR,
) -> int:
    """Standard deduction in cents. Raises UnknownFilingStatusError if missing."""
    rules = load_federal(year)
    for d in rules.standard_deductions:
        if d.filing_status == filing_status:
            return d.amount_cents
    fs = filing_status.value if isinstance(filing_status, FilingStatus) else filing_status
    raise UnknownFilingStatusError(
        f"No federal standard deduction for filing_status={fs!r} year={year}"
    )


def calculate_federal_tax(
    taxable_income_cents: int,
    filing_status: FilingStatus,
    year: int = DEFAULT_FEDERAL_YEAR,
) -> int:
    """Federal income tax in cents. Same algorithm as the state engine.

    Returns 0 for non-positive income (matches FileFree's existing behavior).
    Raises UnknownFilingStatusError if no brackets exist for the filing status.
    """
    if taxable_income_cents <= 0:
        return 0

    rules = load_federal(year)
    brackets = rules.brackets.get(filing_status)
    if not brackets:
        raise UnknownFilingStatusError(
            f"No federal brackets for filing_status={filing_status.value} year={year}"
        )

    return _calculate_progressive_tax(taxable_income_cents, brackets)


def _calculate_progressive_tax(
    taxable_income_cents: int,
    brackets: list[FederalBracket],
) -> int:
    tax_cents = 0
    for bracket in brackets:
        if taxable_income_cents <= bracket.min_income_cents:
            break
        bracket_max = (
            bracket.max_income_cents
            if bracket.max_income_cents is not None
            else taxable_income_cents
        )
        taxable_in_bracket = min(taxable_income_cents, bracket_max) - bracket.min_income_cents
        if taxable_in_bracket <= 0:
            continue
        tax_cents += round_half_up_div(taxable_in_bracket * bracket.rate_bps, 10_000)
    return tax_cents


def clear_federal_cache() -> None:
    _clear_all_caches()
