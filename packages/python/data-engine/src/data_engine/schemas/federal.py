"""Federal IRS tax tables — net-new canonical schema added by Wave K3.

Lives at packages/data/src/federal/{year}.json. Stored in the same canonical
basis-points + integer-cents form as the state tax tables so the math
implementation is shared (data_engine.tax._round_half_up_div).

There is no Zod sibling yet — this schema was added during Wave K3 to break
FileFree's hand-rolled tax-data duplicate. The intentional asymmetry (Pydantic
without Zod for federal) is a known gap to be closed in a follow-up PR by the
docs/data agent. See packages/data/src/federal/README.md.

Not validated by scripts/verify_data_schemas.py — that script only verifies
the schemas that have both a Pydantic and a Zod definition.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from data_engine.schemas.common import FilingStatus, VerificationMeta


class FederalBracket(BaseModel):
    """One row of the federal progressive bracket table.

    All amounts in integer cents. Rate as integer basis points (100 bps = 1%).
    `max_income_cents = None` means "no cap" (top bracket).

    Identical shape to TaxBracket in tax.py — kept separate so federal and
    state schemas can evolve independently without breaking each other.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_income_cents: Annotated[int, Field(ge=0)]
    max_income_cents: Annotated[int, Field(gt=0)] | None
    rate_bps: Annotated[int, Field(ge=0, le=10_000)]


class FederalStandardDeduction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    filing_status: FilingStatus
    amount_cents: Annotated[int, Field(ge=0)]


class FederalTaxRules(BaseModel):
    """One file per year on disk: packages/data/src/federal/{year}.json."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tax_year: Annotated[int, Field(ge=2024, le=2030)]
    standard_deductions: list[FederalStandardDeduction]
    brackets: dict[FilingStatus, list[FederalBracket]]
    salt_cap_cents: Annotated[int, Field(ge=0)] | None = None
    notes: str | None = None
    verification: VerificationMeta
