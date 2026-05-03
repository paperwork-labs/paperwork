# `data-engine` (Python)

Python loader + math for canonical [`packages/data`](../../data) JSON. Pydantic
mirror of the Zod schemas in [`packages/data/src/schemas/`](../../data/src/schemas).

## Why this exists

This package is the Python sibling of [`packages/data/src/engine/`](../../data/src/engine).

Before Wave K3, [`apis/filefree`](../../../apis/filefree) read tax brackets from
its own hand-rolled `apis/filefree/tax-data/2025.json` — separate from the
canonical state files at `packages/data/src/tax/2025/*.json`. Silent drift =
wrong customer returns = legal risk. This package kills that duplicate.

## Doctrine

Reference data (tax brackets, formation rules, portal configs, federal
brackets) lives in **git-versioned JSON**, not Postgres. Schema changes go
through PR review (CPA legal audit trail). See
[`packages/data/README.md`](../../data/README.md) and the "data-storage doctrine"
section of the Brain plan.

The CI guard at [`.github/workflows/no-tax-data-duplicates.yml`](../../../.github/workflows/no-tax-data-duplicates.yml)
fails any build that re-introduces an `apis/*/tax-data/` directory.

## Install

In an existing FastAPI service that lives under `apis/{product}/`:

```
# apis/{product}/requirements.txt
-e ../../packages/python/data-engine
```

(Once the uv workspace from Wave K1+K2 lands, this becomes a workspace dep
declared in `[tool.uv.workspace]` and the `-e` line is dropped.)

## Usage

```python
from data_engine import (
    FilingStatus,
    StateCode,
    calculate_federal_tax,
    calculate_state_tax,
    get_federal_standard_deduction,
)

# Federal — replaces the deleted apis/filefree/tax-data/2025.json
fed_deduction = get_federal_standard_deduction(FilingStatus.SINGLE, year=2025)
fed_tax = calculate_federal_tax(taxable_income_cents=3_425_000, filing_status=FilingStatus.SINGLE, year=2025)

# State — same canonical JSON as the TS engine
ca_tax = calculate_state_tax(
    state=StateCode.CA,
    gross_income_cents=10_000_000,
    filing_status=FilingStatus.SINGLE,
    tax_year=2025,
)
```

All amounts are integer cents. Rates are integer basis points (100 bps = 1%).
Math uses `round_half_up_div` to match the TS engine's `Math.round((taxable * rate_bps) / 10000)`
semantics byte-for-byte.

## Data-directory resolution

The loader finds `packages/data/src/` by:

1. `PAPERWORK_DATA_DIR` env var (must point at `packages/data/src`)
2. Walking up from `data_engine/__file__` until a `packages/data/src/` directory is found

In production / Docker images that don't bundle the monorepo layout, set
`PAPERWORK_DATA_DIR` explicitly.

## Schemas

| Concern | TS schema (Zod) | Python schema (Pydantic) |
|---|---|---|
| State tax rules | [`packages/data/src/schemas/tax.schema.ts`](../../data/src/schemas/tax.schema.ts) | `data_engine.schemas.tax` |
| Formation rules | [`packages/data/src/schemas/formation.schema.ts`](../../data/src/schemas/formation.schema.ts) | `data_engine.schemas.formation` |
| Common (StateCode, etc.) | [`packages/data/src/schemas/common.schema.ts`](../../data/src/schemas/common.schema.ts) | `data_engine.schemas.common` |
| **Federal tax rules** | _(none yet — see note)_ | `data_engine.schemas.federal` |

`scripts/verify_data_schemas.py` (run in CI) enforces field-for-field parity
between the TS and Python schemas. Federal is intentionally Python-only for
now — see [`packages/data/src/federal/README.md`](../../data/src/federal/README.md).

## Tests

```
cd packages/python/data-engine
pip install -e ".[dev]"
pytest
```

Three test modules:
- `test_tax.py` — table-driven state tax calculations (CA, NY, TX, DC)
- `test_loader.py` — every state file + every formation file loads + validates
- `test_drift.py` — TS vs Python parity (skipped when `node` is unavailable)

## Filing-status mapping

The canonical schema uses IRS-form long names (`married_filing_jointly`,
`married_filing_separately`). FileFree's domain enum
([`apis/filefree/app/models/filing.py`](../../../apis/filefree/app/models/filing.py))
uses shorter aliases (`married_joint`, `married_separate`).
[`apis/filefree/app/services/tax_calculator.py`](../../../apis/filefree/app/services/tax_calculator.py)
maps between them so the public FileFree API surface is unchanged.
