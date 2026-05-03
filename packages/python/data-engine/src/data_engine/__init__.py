"""data_engine — canonical reference-data loader + math for Paperwork Labs.

Reads the SAME JSON files as packages/data/src/engine/* (TS), validates with
Pydantic mirrors of the Zod schemas, and exposes byte-compatible math.

Public surface (stable):
  Loaders:       load_tax_year, load_state_tax, load_state_formation,
                 load_state_portal, load_federal, load_all_tax_states,
                 get_available_tax_years, get_available_federal_years
  State tax:     calculate_state_tax, get_state_tax_rules, get_all_tax_states
  Formation:     get_state_formation_rules, get_formation_fee,
                 get_all_formation_states
  Federal:       calculate_federal_tax, get_federal_standard_deduction,
                 get_federal_rules
  Cache helpers: clear_tax_cache, clear_formation_cache, clear_federal_cache,
                 clear_all_caches (test/dev only)

See README.md for usage and the doctrine.
"""

from data_engine.federal import (
    DEFAULT_FEDERAL_YEAR,
    UnknownFilingStatusError,
    calculate_federal_tax,
    clear_federal_cache,
    get_available_federal_years,
    get_federal_rules,
    get_federal_standard_deduction,
)
from data_engine.formation import (
    clear_formation_cache,
    get_all_formation_states,
    get_formation_fee,
    get_state_formation_rules,
)
from data_engine.loader import (
    DATA_DIR_ENV_VAR,
    DataDirNotFoundError,
    clear_all_caches,
    get_data_dir,
    load_all_tax_states,
    load_federal,
    load_state_formation,
    load_state_portal,
    load_state_tax,
    load_tax_year,
)
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
from data_engine.schemas.formation import FormationRules
from data_engine.schemas.tax import (
    IncomeTax,
    IncomeTaxFlat,
    IncomeTaxNone,
    IncomeTaxProgressive,
    StandardDeduction,
    StateTaxRules,
    TaxBracket,
)
from data_engine.tax import (
    DEFAULT_TAX_YEAR,
    calculate_state_tax,
    clear_tax_cache,
    get_all_tax_states,
    get_available_tax_years,
    get_state_tax_rules,
)

__version__ = "0.1.0"

__all__ = [
    "DATA_DIR_ENV_VAR",
    "DEFAULT_FEDERAL_YEAR",
    "DEFAULT_TAX_YEAR",
    "STATE_CODES",
    "DataDirNotFoundError",
    "FederalBracket",
    "FederalStandardDeduction",
    "FederalTaxRules",
    "FilingStatus",
    "FormationRules",
    "IncomeTax",
    "IncomeTaxFlat",
    "IncomeTaxNone",
    "IncomeTaxProgressive",
    "Source",
    "StandardDeduction",
    "StateCode",
    "StateTaxRules",
    "TaxBracket",
    "UnknownFilingStatusError",
    "VerificationMeta",
    "calculate_federal_tax",
    "calculate_state_tax",
    "clear_all_caches",
    "clear_federal_cache",
    "clear_formation_cache",
    "clear_tax_cache",
    "get_all_formation_states",
    "get_all_tax_states",
    "get_available_federal_years",
    "get_available_tax_years",
    "get_data_dir",
    "get_federal_rules",
    "get_federal_standard_deduction",
    "get_formation_fee",
    "get_state_formation_rules",
    "get_state_tax_rules",
    "load_all_tax_states",
    "load_federal",
    "load_state_formation",
    "load_state_portal",
    "load_state_tax",
    "load_tax_year",
]
