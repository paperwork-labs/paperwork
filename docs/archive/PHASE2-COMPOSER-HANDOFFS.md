# Phase 2 Composer Handoff Prompts

## Session 7: P2.7 — Validation Suite + CI Enforcement

### Branch
```
git checkout -b feat/p2-validation-ci
```

### Context

`packages/data` is a pnpm workspace package (`@paperwork-labs/data`) containing:
- **Tax data**: `src/tax/{2024,2025,2026}/{STATE}.json` (153 files, 51 states × 3 years)
- **Formation data**: `src/formation/{STATE}.json` (51 files)
- **Zod schemas**: `src/schemas/` (common, tax, formation, source-registry)
- **Engine**: `src/engine/` (tax.ts, formation.ts, loader.ts, freshness.ts, index.ts)
- **Review CLI**: `scripts/review.ts` (human review + sanity checks + `--approve`)
- **Tests**: `tests/` (schemas.test.ts, engine.test.ts, loader.test.ts, sources.test.ts)
- **Type config**: `tsconfig.json` (src), `tsconfig.scripts.json` (scripts)

Existing CI lives at `.github/workflows/ci.yaml`. It already has a `changes` job using `dorny/paths-filter@v3` with a `sharedPackages` output that triggers when `packages/**` changes. Existing jobs: `secrets-scan`, `api-lint`, `api-test`, `api-launchfree-lint`, `web-lint`, `web-test`, `web-build`.

Existing `package.json` scripts:
```json
{
  "test": "vitest run",
  "typecheck": "tsc --noEmit --project tsconfig.json && tsc --noEmit --project tsconfig.scripts.json",
  "review": "tsx scripts/review.ts",
  "review:approve": "tsx scripts/review.ts --approve"
}
```

### Tasks

**1. Add parameterized JSON validation tests** (`tests/validate-all-data.test.ts`)

Create a new test file that validates EVERY JSON file on disk against its Zod schema. Use `vitest` with `it.each` or dynamic test generation:

```typescript
import { readdirSync } from "fs";
import { join } from "path";
import { describe, it, expect } from "vitest";
import { StateTaxRulesSchema } from "../src/schemas/tax.schema";
import { FormationRulesSchema } from "../src/schemas/formation.schema";
import { discoverTaxYearDirs } from "../src/engine/loader";

const srcDir = join(__dirname, "../src");
const taxRoot = join(srcDir, "tax");

// Discover all tax JSON files dynamically
const taxFiles: { year: number; state: string; path: string }[] = [];
for (const year of discoverTaxYearDirs(taxRoot)) {
  const yearDir = join(taxRoot, String(year));
  for (const file of readdirSync(yearDir).filter(f => f.endsWith(".json") && !f.startsWith("_"))) {
    taxFiles.push({ year, state: file.replace(".json", ""), path: join(yearDir, file) });
  }
}

// Same for formation
const formationDir = join(srcDir, "formation");
const formationFiles = readdirSync(formationDir)
  .filter(f => f.endsWith(".json") && !f.startsWith("_"))
  .map(f => ({ state: f.replace(".json", ""), path: join(formationDir, f) }));
```

Tests to include:
- `describe("Tax JSON schema validation")` — `it.each(taxFiles)` validates each file against `StateTaxRulesSchema`
- `describe("Formation JSON schema validation")` — `it.each(formationFiles)` validates each against `FormationRulesSchema`
- `describe("Tax: file-content cross-check")` — verify `parsed.state` matches filename, `parsed.tax_year` matches directory
- `describe("Formation: file-content cross-check")` — verify `parsed.state` matches filename
- `describe("Completeness")` — all 51 STATE_CODES present per tax year, all 51 present in formation

**2. Add cross-state sanity tests** (`tests/sanity.test.ts`)

Port the sanity check logic from `scripts/review.ts` into a proper test file. The review CLI already implements all checks — extract the check functions into a shared module or just duplicate the key assertions:

- No-income-tax states (AK, FL, NV, SD, TN, TX, WA, WY) must have `income_tax.type === "none"`
- Standard deductions in cents: any non-zero value must be >= 100000 (>= $1,000)
- Personal exemptions in cents: any non-zero value must be >= 10000 (>= $100)
- Progressive bracket rates: no `rate_bps` exceeding 1500 (15%)
- Progressive brackets must be monotonic (each bracket's min >= previous bracket's max)
- Formation filing fees must be > 0
- Non-first brackets: `min_income_cents` must be >= 10000 (>= $100)

Structure:
```typescript
describe("Sanity: standard deductions", () => { ... });
describe("Sanity: personal exemptions", () => { ... });
describe("Sanity: progressive bracket rates", () => { ... });
describe("Sanity: bracket monotonicity", () => { ... });
describe("Sanity: no-income-tax states", () => { ... });
describe("Sanity: formation filing fees", () => { ... });
```

**3. Add freshness gate test** (`tests/freshness.test.ts`)

Test that no state's `verification.last_verified` is older than 90 days. This should WARN (not fail) since stale data doesn't block CI but should be visible:

```typescript
describe("Data freshness", () => {
  const STALE_DAYS = 90;
  const now = new Date();

  it.each(taxFiles)("tax/$year/$state.json should not be stale", ({ path }) => {
    const data = JSON.parse(readFileSync(path, "utf-8"));
    const lastVerified = new Date(data.verification.last_verified);
    const ageMs = now.getTime() - lastVerified.getTime();
    const ageDays = ageMs / (1000 * 60 * 60 * 24);
    if (ageDays > STALE_DAYS) {
      console.warn(`STALE: ${path} — ${Math.round(ageDays)} days old`);
    }
    // Soft assertion: don't fail CI, just warn
    expect(ageDays).toBeLessThan(365); // hard fail only if > 1 year
  });
});
```

**4. Add `packages/data` CI job** to `.github/workflows/ci.yaml`

Add a new job called `data-validate` that runs when `packages/**` changes. It should run AFTER the `changes` job and be gated by `sharedPackages`:

```yaml
  data-validate:
    name: Data Package Validate
    runs-on: ubuntu-latest
    needs: changes
    if: needs.changes.outputs.sharedPackages == 'true'
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 10
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - name: Type check (src + scripts)
        run: pnpm typecheck
        working-directory: packages/data
      - name: Unit + integration tests
        run: pnpm test
        working-directory: packages/data
      - name: Review CLI (sanity checks)
        run: pnpm review
        working-directory: packages/data
```

This job runs three checks in sequence:
1. `pnpm typecheck` — TypeScript strict mode (both `tsconfig.json` and `tsconfig.scripts.json`)
2. `pnpm test` — all Vitest tests (existing + new parameterized + sanity + freshness)
3. `pnpm review` — the review CLI exits non-zero if any sanity check fails

**5. Verify everything passes**

After making all changes:
```bash
cd packages/data
pnpm typecheck
pnpm test
pnpm review
```

All three must exit 0 before committing.

### Files to create/modify

| Action | File |
|--------|------|
| CREATE | `packages/data/tests/validate-all-data.test.ts` |
| CREATE | `packages/data/tests/sanity.test.ts` |
| CREATE | `packages/data/tests/freshness.test.ts` |
| MODIFY | `.github/workflows/ci.yaml` (add `data-validate` job) |

### Do NOT modify
- Any JSON data files in `src/tax/` or `src/formation/`
- `scripts/review.ts` (the review CLI is done)
- `src/engine/loader.ts` or any engine files
- `src/schemas/` or `src/types/`

### Commit
```
feat(data): P2.7 validation suite + CI enforcement

- Parameterized schema tests for all 153 tax + 51 formation JSONs
- Cross-state sanity tests (deductions, exemptions, rates, brackets)
- Freshness gate (warn >90d, fail >365d)
- CI job: typecheck + vitest + review CLI on packages/** changes
```

### PR
```
gh pr create --title "feat(data): P2.7 validation suite + CI enforcement" --body "$(cat <<'EOF'
## Summary
- Parameterized Vitest tests validate every tax/formation JSON against Zod schemas
- Cross-state sanity tests catch unit conversion errors (dollars-as-cents, rate_bps anomalies)
- Freshness gate warns on stale data (>90 days), hard-fails at >365 days
- New `data-validate` CI job runs typecheck + tests + review CLI on every PR touching `packages/**`

## Test plan
- [ ] `pnpm typecheck` passes in `packages/data`
- [ ] `pnpm test` passes — all parameterized + sanity + freshness tests green
- [ ] `pnpm review` exits 0 (all 153 state-year combos VALID)
- [ ] CI workflow runs `data-validate` job on this PR
EOF
)"
gh pr edit <NUMBER> --add-reviewer @copilot
```
