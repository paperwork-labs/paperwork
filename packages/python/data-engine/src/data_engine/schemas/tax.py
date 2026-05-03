"""Mirror of packages/data/src/schemas/tax.schema.ts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from data_engine.schemas.common import (
    FilingStatus,
    StateCode,
    VerificationMeta,
)


class TaxBracket(BaseModel):
    """One row of a progressive bracket table.

    All amounts in integer cents. Rate as integer basis points (100 bps = 1%).
    `max_income_cents = None` means "no cap" (top bracket).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_income_cents: Annotated[int, Field(ge=0)]
    max_income_cents: Annotated[int, Field(gt=0)] | None
    rate_bps: Annotated[int, Field(ge=0, le=10_000)]


class StandardDeduction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    filing_status: FilingStatus
    amount_cents: Annotated[int, Field(ge=0)]


class IncomeTaxNone(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["none"]


class IncomeTaxFlat(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["flat"]
    flat_rate_bps: Annotated[int, Field(ge=0, le=10_000)]


class IncomeTaxProgressive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["progressive"]
    brackets: dict[FilingStatus, list[TaxBracket]]


IncomeTax = Annotated[
    IncomeTaxNone | IncomeTaxFlat | IncomeTaxProgressive,
    Field(discriminator="type"),
]


class PersonalExemption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount_cents: Annotated[int, Field(ge=0)]
    phases_out: bool
    phase_out_threshold_cents: Annotated[int, Field(ge=0)] | None = None


class NotableCredit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    max_amount_cents: Annotated[int, Field(ge=0)] | None = None


class NotableDeduction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    max_amount_cents: Annotated[int, Field(ge=0)] | None = None


class LocalTaxes(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    has_local_income_tax: bool
    notable_localities: list[str] | None = None


class Reciprocity(BaseModel):
    # extra="ignore" matches Zod's default strip-on-parse behavior. Required
    # here because the canonical JSON uses key `states` (e.g. WV, WI, VA)
    # while the Zod schema in tax.schema.ts declares `reciprocal_states`.
    # Documented schema drift — see PR body. Don't try to "fix" by editing
    # packages/data/src/schemas/tax.schema.ts (out of scope for Wave K3).
    model_config = ConfigDict(extra="ignore", frozen=True)

    has_reciprocity: bool
    states: list[StateCode] | None = None


class StateTaxRules(BaseModel):
    """Mirror of StateTaxRulesSchema in packages/data/src/schemas/tax.schema.ts.

    One file per state per year on disk: packages/data/src/tax/{year}/{STATE}.json.

    extra="ignore" matches Zod's default strip-on-parse behavior so we don't
    fail validation on canonical data that has stray keys vs the Zod schema.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    state: StateCode
    state_name: Annotated[str, Field(min_length=1)]
    tax_year: Annotated[int, Field(ge=2024, le=2030)]

    income_tax: IncomeTax

    standard_deductions: list[StandardDeduction]

    personal_exemption: PersonalExemption

    notable_credits: list[NotableCredit]
    notable_deductions: list[NotableDeduction]

    local_taxes: LocalTaxes
    reciprocity: Reciprocity

    dor_url: HttpUrl
    tax_foundation_url: HttpUrl | None = None
    notes: str | None = None
    verification: VerificationMeta
