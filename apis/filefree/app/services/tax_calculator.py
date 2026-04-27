"""Tax calculator engine — all values in integer cents. No floats.

medallion: ops
"""

import json
from pathlib import Path
from typing import Any, cast

TAX_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "tax-data"

_cache: dict[int, dict[str, Any]] = {}


def _load_tax_data(year: int) -> dict[str, Any]:
    if year in _cache:
        return _cache[year]
    path = TAX_DATA_DIR / f"{year}.json"
    with path.open(encoding="utf-8") as f:
        data = cast("dict[str, Any]", json.load(f))
    _cache[year] = data
    return data


def get_standard_deduction(filing_status: str, year: int = 2025) -> int:
    data = _load_tax_data(year)
    deductions = data["standard_deductions"]
    if filing_status not in deductions:
        raise ValueError(f"Unknown filing status: {filing_status}")
    return int(deductions[filing_status])


def calculate_federal_tax(taxable_income_cents: int, filing_status: str, year: int = 2025) -> int:
    if taxable_income_cents <= 0:
        return 0

    data = _load_tax_data(year)
    brackets = data["federal_brackets"].get(filing_status)
    if not brackets:
        raise ValueError(f"Unknown filing status: {filing_status}")

    tax = 0
    prev_max = 0

    for bracket in brackets:
        bracket_max = bracket["max"]
        rate = bracket["rate"]

        if bracket_max is None:
            taxable_in_bracket = taxable_income_cents - prev_max
        else:
            taxable_in_bracket = min(taxable_income_cents, bracket_max) - prev_max

        if taxable_in_bracket <= 0:
            break

        tax += taxable_in_bracket * rate // 100
        prev_max = bracket_max if bracket_max is not None else taxable_income_cents

    return tax


def calculate_return(
    total_wages_cents: int,
    total_federal_withheld_cents: int,
    total_state_withheld_cents: int,
    filing_status: str,
    year: int = 2025,
) -> dict[str, Any]:
    """Calculate complete return. All values in cents."""
    agi = total_wages_cents
    standard_deduction = get_standard_deduction(filing_status, year)
    taxable_income = max(0, agi - standard_deduction)

    federal_tax = calculate_federal_tax(taxable_income, filing_status, year)

    total_withheld = total_federal_withheld_cents + total_state_withheld_cents
    total_tax = federal_tax  # state tax not modeled yet

    net = total_withheld - total_tax
    refund_amount = max(0, net)
    owed_amount = max(0, -net)

    return {
        "adjusted_gross_income": agi,
        "standard_deduction": standard_deduction,
        "taxable_income": taxable_income,
        "federal_tax": federal_tax,
        "state_tax": 0,
        "total_withheld": total_withheld,
        "refund_amount": refund_amount,
        "owed_amount": owed_amount,
    }
