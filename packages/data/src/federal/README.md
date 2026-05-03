# `packages/data/src/federal/`

Federal IRS tax brackets + standard deductions, one file per year:
`packages/data/src/federal/{year}.json`.

Added in Wave K3 as the canonical home for federal data when killing
FileFree's hand-rolled `apis/filefree/tax-data/2025.json` duplicate.

## Schema

Validated by Pydantic via [`data_engine.schemas.federal.FederalTaxRules`](../../../python/data-engine/src/data_engine/schemas/federal.py).

There is **no Zod sibling yet**. Federal data is intentionally Python-only
during Wave K3 to scope the PR. The TS engine in
[`packages/data/src/engine/`](../engine/) does not currently consume
federal data — only the Python `data-engine` does (via FileFree). When a
TS consumer needs federal data, the docs/data agent should add
`packages/data/src/schemas/federal.schema.ts` mirroring the Pydantic shape
and re-enable that schema in
[`scripts/verify_data_schemas.py`](../../../../scripts/verify_data_schemas.py).

## Conventions

- All amounts in **integer cents**.
- All rates as **integer basis points** (100 bps = 1%; 3700 bps = 37%).
- Bracket boundaries are **half-open**: `[min_income_cents, max_income_cents)`.
  At income exactly equal to a bracket's `max`, that income falls into the
  next bracket (because the next bracket's `min` equals this bracket's `max`).
  Same convention as the state files in `packages/data/src/tax/{year}/*.json`.
- The top bracket has `"max_income_cents": null`.

## Annual update workflow

1. Pull `Rev. Proc. {N}-{N+1}` from IRS for inflation adjustments.
2. Diff against any new public law (One Big Beautiful Bill Act etc.).
3. Edit `packages/data/src/federal/{year}.json`.
4. PR review by CPA persona (CPA legal audit trail; same workflow as
   `packages/data/src/tax/{year}/*.json`).
5. CI runs `data_engine` test suite — federal/state math parity guarded
   by `tests/test_federal.py` and `tests/test_drift.py`.

## Doctrine

Reference data lives in **git-versioned JSON**, not Postgres. See
[`packages/data/README.md`](../../README.md) and Operating Principle 3
of the Brain plan ("The data-storage doctrine").
