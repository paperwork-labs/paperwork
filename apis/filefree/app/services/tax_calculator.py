"""Tax calculator engine — all values in integer cents. No floats.

medallion: ops

Wave K3: this module no longer reads `apis/filefree/tax-data/{year}.json`.
Federal brackets + standard deductions live at canonical
`packages/data/src/federal/{year}.json` and are loaded via the shared
`data_engine` package (packages/python/data-engine). State tax (when wired)
also flows through `data_engine.calculate_state_tax` so FileFree shares one
implementation of bracket math with the TS engine in
packages/data/src/engine/tax.ts.

The public function signatures below are unchanged so the FileFree router
(app/routers/tax.py) and tests (tests/test_tax_calculator.py) keep working
verbatim. The only behavioral change is the data source.
"""

from typing import Any

from data_engine import (
    FilingStatus as CanonicalFilingStatus,
)
from data_engine import (
    StateCode,
    UnknownFilingStatusError,
)
from data_engine import (
    calculate_federal_tax as _de_calculate_federal_tax,
)
from data_engine import (
    calculate_state_tax as _de_calculate_state_tax,
)
from data_engine import (
    get_federal_standard_deduction as _de_get_federal_standard_deduction,
)

# FileFree's domain enum (app.models.filing.FilingStatusType) uses shorter
# aliases than the canonical IRS-form long names in the data_engine schema.
# The mapping is a stable contract — the values on the left are what
# FastAPI receives from the wire (and what tests pass).
_FILING_STATUS_MAP: dict[str, CanonicalFilingStatus] = {
    "single": CanonicalFilingStatus.SINGLE,
    "married_joint": CanonicalFilingStatus.MARRIED_FILING_JOINTLY,
    "married_separate": CanonicalFilingStatus.MARRIED_FILING_SEPARATELY,
    "head_of_household": CanonicalFilingStatus.HEAD_OF_HOUSEHOLD,
}


def _to_canonical(filing_status: str) -> CanonicalFilingStatus:
    """Translate FileFree's domain enum string to the canonical FilingStatus enum.

    Raises ValueError with the exact message FileFree's tests + router expect
    ("Unknown filing status: ...").
    """
    canonical = _FILING_STATUS_MAP.get(filing_status)
    if canonical is None:
        raise ValueError(f"Unknown filing status: {filing_status}")
    return canonical


def get_standard_deduction(filing_status: str, year: int = 2025) -> int:
    """Federal standard deduction in cents for the given filing status + year.

    Reads packages/data/src/federal/{year}.json via data_engine.
    """
    canonical = _to_canonical(filing_status)
    try:
        return _de_get_federal_standard_deduction(canonical, year)
    except UnknownFilingStatusError as err:
        raise ValueError(f"Unknown filing status: {filing_status}") from err


def calculate_federal_tax(taxable_income_cents: int, filing_status: str, year: int = 2025) -> int:
    """Federal income tax in cents for the given taxable income + filing status + year.

    Pure delegation to data_engine. Behavior is byte-identical for all of
    FileFree's existing test inputs (whole-dollar amounts) — see PR body for
    the math equivalence proof and the data_engine.tests.test_federal suite.
    """
    if taxable_income_cents <= 0:
        return 0
    canonical = _to_canonical(filing_status)
    try:
        return _de_calculate_federal_tax(taxable_income_cents, canonical, year)
    except UnknownFilingStatusError as err:
        raise ValueError(f"Unknown filing status: {filing_status}") from err


def calculate_return(
    total_wages_cents: int,
    total_federal_withheld_cents: int,
    total_state_withheld_cents: int,
    filing_status: str,
    year: int = 2025,
    state: str | None = None,
) -> dict[str, Any]:
    """Calculate complete return. All values in cents.

    `state` (new, optional): if provided as a 2-letter code, computes state
    income tax via `data_engine.calculate_state_tax(state, ...)`. If omitted
    or unknown, state_tax stays at 0 (the previous FileFree behavior — see
    apis/filefree/app/services/tax_calculator.py:89 in git history).
    """
    agi = total_wages_cents
    standard_deduction = get_standard_deduction(filing_status, year)
    taxable_income = max(0, agi - standard_deduction)

    federal_tax = calculate_federal_tax(taxable_income, filing_status, year)

    state_tax = _safe_state_tax(agi, filing_status, year, state)

    total_withheld = total_federal_withheld_cents + total_state_withheld_cents
    total_tax = federal_tax + state_tax

    net = total_withheld - total_tax
    refund_amount = max(0, net)
    owed_amount = max(0, -net)

    return {
        "adjusted_gross_income": agi,
        "standard_deduction": standard_deduction,
        "taxable_income": taxable_income,
        "federal_tax": federal_tax,
        "state_tax": state_tax,
        "total_withheld": total_withheld,
        "refund_amount": refund_amount,
        "owed_amount": owed_amount,
    }


def _safe_state_tax(
    gross_income_cents: int,
    filing_status: str,
    year: int,
    state: str | None,
) -> int:
    """Return state tax in cents, or 0 if the lookup fails for any reason.

    Defensive zero: if a caller passes a state code that isn't in canonical
    data, we degrade to "no state tax computed" rather than raising. This
    matches the previous FileFree behavior (state tax was always 0). Once
    every consumer flows a `state` arg through, swap this for a strict
    raising path.
    """
    if state is None:
        return 0
    try:
        canonical_state = StateCode(state.upper())
    except ValueError:
        return 0
    try:
        canonical_status = _to_canonical(filing_status)
    except ValueError:
        return 0
    result = _de_calculate_state_tax(canonical_state, gross_income_cents, canonical_status, year)
    return result if result is not None else 0
