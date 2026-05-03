# Paperwork Labs Reference Data

> **Status**: canonical, single source of truth.
> **Doctrine**: lives in git as JSON, not in Postgres. See [docs/BRAIN_ARCHITECTURE.md → Reference Data Storage Doctrine](../../docs/BRAIN_ARCHITECTURE.md#reference-data-storage-doctrine) for the full rationale (legal audit trail, rollback, perf, multi-language consumption).
> **Touch with care**: every change has legal consequences if wrong (CPA reviews tax brackets, founder reviews formation rules).

## What this is

`@paperwork-labs/data` is the **canonical state-by-state reference data** for the entire venture:

| Subpath | Contents | Cadence | Reviewer |
|---|---|---|---|
| [`src/tax/{year}/{STATE}.json`](src/tax/) | State income tax rules, brackets, standard deductions, credits per filing status | Annual (October release for following tax year) + ad-hoc legislative changes | CPA / Tax Domain Expert |
| [`src/formation/{STATE}.json`](src/formation/) | LLC formation rules, fees, entity types, registered agent requirements | Quarterly + on legislative change | Founder / Formation Domain Expert |
| [`src/portals/{state}.json`](src/portals/) | State portal automation configs (URLs, fee structures, filing methods) | On portal change | Founder |
| [`src/sources/{STATE}.json`](src/sources/) | Source registry per state (SOS URL, DOR URL, Tax Foundation ref, scrape method) | On source rot / verification cycle | Engineering |
| [`src/schemas/`](src/schemas/) | Zod schemas validating every JSON file in this package | On schema change (rare; coordinate with Pydantic mirror in Wave K3 `packages/python/data-engine`) | Engineering |
| [`src/engine/`](src/engine/) | TypeScript engine: `loader`, `tax.calculateStateTax`, `formation.getStateFormationRules`, `freshness.getStateFreshness` | On engine change | Engineering |

This package powers FileFree's tax calculations, LaunchFree's formation flows, Distill's APIs, every product's tax/formation form, and (after Wave K3) the FileFree Python backend through a Pydantic-mirrored `packages/python/data-engine`.

## How it's generated

The JSON files are **deterministic outputs of parsers**, not hand-rolled tables. The parsers live in [`scripts/`](scripts/) and consume upstream fixtures kept under `scripts/fixtures/` (XLSX from Tax Foundation, scraped state SOS pages, etc.).

| Script | Upstream source | Output |
|---|---|---|
| [`scripts/parse-tax-foundation.ts`](scripts/parse-tax-foundation.ts) | `scripts/fixtures/2026-State-Individual-Income-Tax-Rates-Brackets.xlsx` (Tax Foundation annual release) | [`src/tax/{year}/{STATE}.json`](src/tax/) |
| [`scripts/parse-formation-rules.ts`](scripts/parse-formation-rules.ts) | Per-state SOS fixtures + chamber-of-commerce aggregator scrapes | [`src/formation/{STATE}.json`](src/formation/) |
| [`scripts/review.ts`](scripts/review.ts) | Pending JSON diffs + Zod validation | Stdout review report; `--approve` flag commits |

Re-running a parser against the same upstream fixture produces **byte-identical JSON**. That reproducibility is the audit primitive — any reviewer can replay the parser to confirm a JSON diff matches the upstream source.

```bash
pnpm --filter @paperwork-labs/data parse:tax        # regenerate src/tax/{year}/*.json from XLSX
pnpm --filter @paperwork-labs/data parse:formation  # regenerate src/formation/*.json from SOS fixtures
pnpm --filter @paperwork-labs/data review           # show pending changes + Zod validation
pnpm --filter @paperwork-labs/data review:approve   # commit the staged changes
pnpm --filter @paperwork-labs/data test             # Zod schema sanity + loader tests
```

## How to update

**All updates go through PR review.** No exceptions, no admin UI, no hot-patch on prod.

1. **Tax brackets** (`src/tax/`) — drop the new Tax Foundation XLSX into `scripts/fixtures/`, run `pnpm parse:tax`, commit the JSON diff. **CPA review required** before merge. PR title prefix: `data(tax):`. The PR diff IS the legal audit trail; `git blame` answers "who approved this bracket and when, against what source."
2. **Formation rules** (`src/formation/`) — refresh the SOS fixture, run `pnpm parse:formation`, commit. **Founder review required** (formation rules carry trademark + UPL + fee-collection liability). PR title prefix: `data(formation):`.
3. **Portal configs** (`src/portals/`) — hand-edit acceptable when a state portal changes URL or fee structure mid-cycle, but always validate with `pnpm test` before merge. **Founder review required.** PR title prefix: `data(portals):`.
4. **Source registry** (`src/sources/`) — engineering review fine; tracks where parsers fetch upstream from. PR title prefix: `data(sources):`.
5. **Schemas** (`src/schemas/`) — schema changes coordinate with the Pydantic mirror in `packages/python/data-engine` (Wave K3). The CI schema-drift guard (`scripts/verify_data_schemas.py`) fails the build if Zod and Pydantic diverge. **Engineering review + founder approval** for breaking changes.

Rollback is `git revert <sha> && redeploy`. Same primitive as any other code regression. No emergency `UPDATE` against prod, no restore-from-backup ceremony.

## How to consume

### TypeScript (frontends + Next.js server components today)

```typescript
import { getStateTaxRules, calculateStateTax } from "@paperwork-labs/data/engine/tax";
import { getStateFormationRules } from "@paperwork-labs/data/engine/formation";
import { getStateFreshness } from "@paperwork-labs/data/engine/freshness";

const caRules = getStateTaxRules("CA", 2026);
const result = calculateStateTax("CA", 75000_00, "single"); // cents in, cents out
const wyFormation = getStateFormationRules("WY");
```

The loader caches each state-year as an in-memory dict on first read (sub-microsecond per subsequent call). Frontends bundle this statically into Next.js builds — zero SSR/runtime DB hit on tax forms.

### Python (FastAPI backends, after Wave K3)

```python
from data_engine.loader import load_tax_year, load_formation, load_portal
from data_engine.tax import calculate_state_tax

ca_2026 = load_tax_year("CA", 2026)              # Pydantic model mirroring StateTaxRulesSchema
result = calculate_state_tax("CA", 75_000_00, "single")  # Decimal-cents semantics, never floats
wy_formation = load_formation("WY")
fl_portal = load_portal("FL")
```

The Python engine reads the same JSON tree (located via monorepo-root walk or `PAPERWORK_DATA_DIR` env var). Pydantic schemas mirror the Zod ones; the schema-drift CI guard fails the build on divergence. **Wave K3 of the [Brain-as-OS plan](file:///Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_%E2%80%94_final_plan_4c44cfe9.plan.md) ships this.**

## What NOT to do

- **DO NOT duplicate this data inside any backend's `tax-data/`, `formation-data/`, or similar directory.** This is the single most likely future violation. **`apis/filefree/tax-data/` previously duplicated the canonical `src/tax/` tree — that was a bug, fixed in Wave K3** when the Python `data-engine` started reading `packages/data/src/tax/` directly and the duplicate directory was deleted. A CI ripgrep guard now fails the build on any new `apis/*/tax-data/` directory. Silent drift between this package and a backend's local copy is a legal risk class — wrong CA brackets in 2026 means wrong customer returns.
- **DO NOT move this data to a Postgres `tax_brackets` / `formation_rules` table without explicit founder approval.** This is the second most likely violation. The full reasoning lives in [docs/BRAIN_ARCHITECTURE.md → Reference Data Storage Doctrine](../../docs/BRAIN_ARCHITECTURE.md#reference-data-storage-doctrine). Short version: PR review IS the legal audit trail, `git revert` IS the rollback story, in-memory cache IS the perf story, and a DB ops surface sized for hourly mutations is overkill for the ~50-100 PRs/year cadence this data actually changes at. Industry precedent (TurboTax, Drake, Lacerte all ship tax tables bundled, not DB lookups) confirms this is the right shape for the data.
- **DO NOT hand-edit JSON files that are parser outputs without re-running the parser.** Hand-edits to `src/tax/` or `src/formation/` outside the `pnpm parse:*` flow break reproducibility — the next parser run will revert your edit. If the parser produces wrong output, fix the parser, not the JSON.
- **DO NOT add new top-level subpaths** (e.g. `src/compliance/`, `src/credits/`) without coordinating with the engineering review queue and updating both Zod and Pydantic (Wave K3) schemas.
- **DO NOT bypass Zod validation.** Every JSON file is validated by `src/schemas/` on load. If validation fails, the loader throws; that's intentional.

## What DOES go in Postgres (for clarity)

Per-user filings, per-user line items, per-user W-2 entries, submission state, Brain ownership graph, conversations, memory episodes, runbooks, runs, per-tenant configs (multi-tenant isolation via RLS). The line is: **canonical reference (one row per state per year, identical for every customer) → JSON in this package. Per-customer state (one row per filing, unique per customer) → Postgres in the relevant backend's models.**

## Where this is codified

This doctrine appears in five places to make it hard to violate by accident:

1. This README
2. [docs/BRAIN_ARCHITECTURE.md → Reference Data Storage Doctrine](../../docs/BRAIN_ARCHITECTURE.md#reference-data-storage-doctrine) (full rationale + comparison table)
3. [.cursorrules](../../.cursorrules) → "Brain-as-OS Doctrines" section (one-liner that applies to every Cursor agent in this repo)
4. [docs/VENTURE_MASTER_PLAN.md](../../docs/VENTURE_MASTER_PLAN.md) → cross-references at every `packages/data` mention
5. The locked plan at [`/Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_—_final_plan_4c44cfe9.plan.md`](file:///Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_%E2%80%94_final_plan_4c44cfe9.plan.md) (decisions table + Wave K3 fix)

Plus a CI ripgrep guard that fails the build on any new `apis/*/tax-data/` directory.

## Related docs

- [docs/BRAIN_ARCHITECTURE.md](../../docs/BRAIN_ARCHITECTURE.md) — the full Brain-as-OS architecture, including the Brain Gateway and the per-product MCP doctrine.
- [docs/VENTURE_MASTER_PLAN.md](../../docs/VENTURE_MASTER_PLAN.md) — venture-wide strategic plan; section 3B covers the 50-state data pipeline this package is the output of.
- [src/portals/README.md](src/portals/README.md) — sub-package readme for portal automation configs.
