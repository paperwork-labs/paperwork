"""Mirror of packages/data/src/schemas/common.schema.ts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StateCode(StrEnum):
    """All 50 states + DC. Order must match common.schema.ts StateCodeSchema."""

    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"


STATE_CODES: list[StateCode] = list(StateCode)


class FilingStatus(StrEnum):
    """Canonical filing-status taxonomy. Mirrors FilingStatusSchema in tax.schema.ts.

    NOTE: FileFree's domain enum (apis/filefree/app/models/filing.py:FilingStatusType)
    uses shorter aliases (`married_joint`, `married_separate`). The canonical
    schema uses the IRS-form long names. The FileFree migration shim translates
    between the two.
    """

    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"


VerifiedBy = Literal[
    "sos_extraction",
    "sos_extraction_unverified",
    "human_review",
    "automated_validation",
    "tax_foundation_parse",
    "deterministic_parse",
]


class Source(BaseModel):
    """Provenance row inside VerificationMeta."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Annotated[str, Field(min_length=1)]
    url: HttpUrl
    accessed_at: datetime


class VerificationMeta(BaseModel):
    """Mirror of VerificationMetaSchema. Required on every reference-data file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    last_verified: datetime
    sources: Annotated[list[Source], Field(min_length=1)]
    verified_by: VerifiedBy
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
