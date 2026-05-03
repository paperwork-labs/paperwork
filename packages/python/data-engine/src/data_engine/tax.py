"""Python port of packages/data/src/engine/tax.ts.

Same algorithm, same defaults, same caching surface — but reads canonical JSON
via data_engine.loader instead of an in-memory `loadTaxData(...)` registry.

All amounts are integer cents; rates are integer basis points. Math uses
`round_half_up_div` to match the TS `Math.round((taxable * rate_bps) / 10000)`
contract byte-for-byte.
"""

from __future__ import annotations

from data_engine._round import round_half_up_div
from data_engine.loader import (
    clear_all_caches as _clear_all_caches,
)
from data_engine.loader import (
    get_available_tax_years as _loader_get_available_tax_years,
)
from data_engine.loader import (
    load_state_tax,
    load_tax_year,
)
from data_engine.schemas.common import FilingStatus, StateCode
from data_engine.schemas.tax import (
    IncomeTaxFlat,
    IncomeTaxNone,
    IncomeTaxProgressive,
    StateTaxRules,
    TaxBracket,
)

# Intentional hardcode — mirrors DEFAULT_TAX_YEAR in packages/data/src/engine/tax.ts.
# Updated annually alongside new data extraction runs.
DEFAULT_TAX_YEAR: int = 2026


def get_state_tax_rules(
    state: StateCode,
    tax_year: int = DEFAULT_TAX_YEAR,
) -> StateTaxRules | None:
    """Return rules or None if no file on disk for that (state, year)."""
    try:
        return load_state_tax(state, tax_year)
    except FileNotFoundError:
        return None


def get_all_tax_states(tax_year: int = DEFAULT_TAX_YEAR) -> list[StateCode]:
    """Every state with a tax file under tax/{tax_year}/."""
    try:
        return sorted(load_tax_year(tax_year).keys())
    except FileNotFoundError:
        return []


def get_available_tax_years(state: StateCode | None = None) -> list[int]:
    """Discover tax years on disk; if state given, only years that include it."""
    years = _loader_get_available_tax_years()
    if state is None:
        return years
    out: list[int] = []
    for year in years:
        try:
            if state in load_tax_year(year):
                out.append(year)
        except FileNotFoundError:
            continue
    return out


def calculate_state_tax(
    state: StateCode,
    gross_income_cents: int,
    filing_status: FilingStatus,
    tax_year: int = DEFAULT_TAX_YEAR,
) -> int | None:
    """Return state income tax in cents, or None if state/year/status not in data.

    Mirrors calculateStateTax() in packages/data/src/engine/tax.ts:
      - none -> 0
      - flat -> round_half_up_div(taxable * flat_rate_bps, 10000)
      - progressive -> sum over brackets of round_half_up_div(in_bracket * rate_bps, 10000)
      - taxable = max(0, gross - standard_deduction[filing_status])
    """
    rules = get_state_tax_rules(state, tax_year)
    if rules is None:
        return None

    income_tax = rules.income_tax

    if isinstance(income_tax, IncomeTaxNone):
        return 0

    deduction_cents = _standard_deduction_for(rules, filing_status)
    taxable = max(0, gross_income_cents - deduction_cents)

    if isinstance(income_tax, IncomeTaxFlat):
        return round_half_up_div(taxable * income_tax.flat_rate_bps, 10_000)

    if isinstance(income_tax, IncomeTaxProgressive):
        brackets = income_tax.brackets.get(filing_status)
        if not brackets:
            return None
        return _calculate_progressive_tax(taxable, brackets)

    return None


def _standard_deduction_for(rules: StateTaxRules, filing_status: FilingStatus) -> int:
    for d in rules.standard_deductions:
        if d.filing_status == filing_status:
            return d.amount_cents
    return 0


def _calculate_progressive_tax(taxable_income_cents: int, brackets: list[TaxBracket]) -> int:
    """Walk progressive brackets in order. Mirrors TS calculateProgressiveTax()."""
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


def clear_tax_cache() -> None:
    """Test helper. Mirrors clearTaxCache() in the TS engine."""
    _clear_all_caches()
