"""Mirror of packages/data/src/schemas/formation.schema.ts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from data_engine.schemas.common import StateCode, VerificationMeta

FilingMethod = Literal["api", "portal", "mail"]


class FilingTier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    method: FilingMethod
    url: HttpUrl | None = None
    notes: str | None = None


class StateFee(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount_cents: Annotated[int, Field(ge=0)]
    description: Annotated[str, Field(min_length=1)]
    is_expedited: bool
    processing_days: Annotated[int, Field(gt=0)] | None = None


class FormationFees(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    standard: StateFee
    expedited: StateFee | None = None
    name_reservation: StateFee | None = None


class FormationFiling(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: FilingTier
    fallback: FilingTier | None = None
    portal_url: HttpUrl | None = None
    api_endpoint: HttpUrl | None = None


class FormationRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    articles_of_organization: bool
    operating_agreement_required: bool
    publication_required: bool
    registered_agent_required: bool
    annual_report_required: bool
    annual_report_fee_cents: Annotated[int, Field(ge=0)] | None = None
    franchise_tax: bool
    franchise_tax_amount_cents: Annotated[int, Field(ge=0)] | None = None


class FormationProcessing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    standard_days: Annotated[int, Field(gt=0)]
    expedited_days: Annotated[int, Field(gt=0)] | None = None


class FormationNaming(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    required_suffix: Annotated[list[str], Field(min_length=1)]
    restricted_words: list[str]
    name_check_url: HttpUrl | None = None


class FormationCompliance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    annual_report_due: str | None = None
    franchise_tax_due: str | None = None
    first_report_due_after_formation_days: Annotated[int, Field(gt=0)] | None = None


class FormationRules(BaseModel):
    """Mirror of FormationRulesSchema in packages/data/src/schemas/formation.schema.ts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: StateCode
    state_name: Annotated[str, Field(min_length=1)]
    entity_type: Literal["LLC"]
    sos_url: HttpUrl
    filing_office: Annotated[str, Field(min_length=1)]

    fees: FormationFees
    filing: FormationFiling
    requirements: FormationRequirements
    processing: FormationProcessing
    naming: FormationNaming
    compliance: FormationCompliance

    notes: str | None = None
    verification: VerificationMeta
