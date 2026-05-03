"""Pydantic mirror of packages/data/src/schemas/*.schema.ts.

Field-for-field parity is enforced by scripts/verify_data_schemas.py in CI.
"""

from data_engine.schemas.common import (
    STATE_CODES,
    FilingStatus,
    Source,
    StateCode,
    VerificationMeta,
)
from data_engine.schemas.federal import (
    FederalBracket,
    FederalStandardDeduction,
    FederalTaxRules,
)
from data_engine.schemas.formation import (
    FilingMethod,
    FilingTier,
    FormationCompliance,
    FormationFees,
    FormationFiling,
    FormationNaming,
    FormationProcessing,
    FormationRequirements,
    FormationRules,
    StateFee,
)
from data_engine.schemas.tax import (
    IncomeTax,
    IncomeTaxFlat,
    IncomeTaxNone,
    IncomeTaxProgressive,
    LocalTaxes,
    NotableCredit,
    NotableDeduction,
    PersonalExemption,
    Reciprocity,
    StandardDeduction,
    StateTaxRules,
    TaxBracket,
)

__all__ = [
    "STATE_CODES",
    "FederalBracket",
    "FederalStandardDeduction",
    "FederalTaxRules",
    "FilingMethod",
    "FilingStatus",
    "FilingTier",
    "FormationCompliance",
    "FormationFees",
    "FormationFiling",
    "FormationNaming",
    "FormationProcessing",
    "FormationRequirements",
    "FormationRules",
    "IncomeTax",
    "IncomeTaxFlat",
    "IncomeTaxNone",
    "IncomeTaxProgressive",
    "LocalTaxes",
    "NotableCredit",
    "NotableDeduction",
    "PersonalExemption",
    "Reciprocity",
    "Source",
    "StandardDeduction",
    "StateCode",
    "StateFee",
    "StateTaxRules",
    "TaxBracket",
    "VerificationMeta",
]
