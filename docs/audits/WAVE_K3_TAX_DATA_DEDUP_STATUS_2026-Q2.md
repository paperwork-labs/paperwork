# Wave K3 — Tax reference data dedup (FileFree) — closure status

**Date:** 2026-05-04  
**Status:** **DONE** — no duplicate `apis/filefree/tax-data/` tree; FileFree loads canonical JSON via `packages/python/data-engine`.

## Canonical location (Brain bedrock)

- Reference JSON: **`packages/data/src/**/*.json`** (tax, formation, federal, portals, sources). Contributor workflow and “do not duplicate under backends” rule: [`packages/data/README.md`](../../packages/data/README.md) (especially **What NOT to do** and **How to consume → Python**).
- Python loader / bracket math: **`packages/python/data-engine`** — `from data_engine.loader import load_tax_year, …` and `from data_engine.tax import calculate_state_tax` as documented in the same README.

## Evidence — duplicate tree absent

```text
$ find apis/filefree -type d -name 'tax-data'
(no output)

$ rg -n "tax-data|tax_data" apis/filefree/
apis/filefree/app/services/tax_calculator.py:5:Wave K3: this module no longer reads `apis/filefree/tax-data/{year}.json`.
```

No Python imports under `apis/filefree/` point at a local `tax-data` directory. [`apis/filefree/app/services/tax_calculator.py`](../../apis/filefree/app/services/tax_calculator.py) delegates to `data_engine` (federal + state).

## CI / guardrails

- [`.github/workflows/no-tax-data-duplicates.yml`](../../.github/workflows/no-tax-data-duplicates.yml) — fails if `apis/*/tax-data/` reappears.
- [`.github/workflows/verify-data-schemas.yml`](../../.github/workflows/verify-data-schemas.yml) — Zod ↔ Pydantic drift guard for shared schemas.

## Tests (`data-engine`)

From repo root, use a venv (PEP 668–safe), then:

```bash
cd packages/python/data-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

**Result (2026-05-04):** `58 passed in 0.18s`

## Related doc updates

- [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md) — Reference Data Storage Doctrine: Wave K3 described as **fixed** (no “currently reads duplicate” wording).
- [`docs/plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md`](../plans/PAPERWORK_LABS_2026Q2_MASTER_PLAN.md) — T5.1 bullet points here plus live paths (avoids broken link to deleted `apis/filefree/tax-data/`).
