# Audit: Vercel `--prebuilt` rollout completeness (T3.8)

**Scope:** Apps under `apps/` that are wired for Vercel in [`scripts/vercel-projects.json`](../../scripts/vercel-projects.json) and/or [`docs/infra/VERCEL_LINKING.md`](../infra/VERCEL_LINKING.md) (Paperwork Labs “link all apps” convention).  
**Excluded from the matrix below:** `apps/probes/` (Playwright harness; no Vercel project), `apps/_archive/**` (archived).

**Audit method (on-disk):**

1. **`package.json` scripts** — `apps/<name>/package.json` `build` (and workspace root `pnpm build:<name>` shortcuts in repo root [`package.json`](../../package.json)).
2. **`vercel.json`** — `installCommand`, `buildCommand`, `outputDirectory`, `framework`; no `vercel.ts` exists in repo.
3. **CI — `vercel deploy` / `--prebuilt`** — [`.github/workflows/vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml), [`.github/actions/vercel-prebuilt/action.yaml`](../../.github/actions/vercel-prebuilt/action.yaml); full-text search under `.github/workflows/` for deployment-related Vercel usage.
4. **Artifact expectation** — The composite action runs `vercel build` then `vercel deploy --prebuilt` with `cwd` = `apps/<name>`. Vercel CLI materializes the Build Output API tree at **`apps/<name>/.vercel/output`** (then uploaded; not committed). Intermediate app output (e.g. `.next`, `storybook-static`) is produced during `vercel build` per project config.

**Explicit unknowns (do not assume in ops):**

- Whether each GitHub Actions secret `VERCEL_PROJECT_ID_*` is populated with a live `prj_…` in the org/repo (workflow **skips** deploy when unset or not matching `prj_*`).
- Whether production traffic for gaps (e.g. trinkets) is updated manually, via dashboard, or another automation not represented in `.github/workflows/`.
- **Doc drift:** [`docs/infra/VERCEL_AUTO_PROMOTE.md`](../infra/VERCEL_AUTO_PROMOTE.md) references `.github/workflows/vercel-promote-on-merge.yaml`, but **that file is not present** under `.github/workflows/` on the audited tree — treat promote automation as **unverified here**.

**Committed project id placeholders:** Rows in `scripts/vercel-projects.json` whose `projectId` is `TBD_CREATE_BEFORE_MERGE` indicate the Vercel project may not exist or the id was not finalized in-repo at audit time — see that file for current values (do not infer ids).

---

## Rollout completeness table

| App | Build command (source) | Artifact path expectation | CI workflow reference | `--prebuilt` used? | Gap | Recommended fix (size) |
| --- | --- | --- | --- | --- | --- | --- |
| **studio** | `package.json`: `prebuild` (docs/persona snapshots) + `next build`. `vercel.json`: no `buildCommand` — install + ignore only; framework/build resolved by Vercel project defaults / auto-detect. | `apps/studio/.vercel/output` after `vercel build` | [`.github/workflows/vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml) matrix `studio`; [`.github/actions/vercel-prebuilt/action.yaml`](../../.github/actions/vercel-prebuilt/action.yaml) (`vercel deploy --prebuilt`) | **yes** (conditional) | Deploy skipped if `VERCEL_PROJECT_ID_STUDIO` missing/invalid; implicit build path less explicit than apps with `buildCommand` in `vercel.json`. | **S** — Add `buildCommand`/`outputDirectory` to `apps/studio/vercel.json` mirroring other Next apps for parity and predictable `vercel build`. |
| **filefree** | `vercel.json`: `pnpm --filter @paperwork-labs/filefree... run build`; `package.json`: `next build`. | `apps/filefree/.vercel/output` | [`.github/workflows/vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml) matrix `filefree`; [`.github/actions/vercel-prebuilt/action.yaml`](../../.github/actions/vercel-prebuilt/action.yaml) | **yes** (conditional) | Secret gate as above. | **XS** — Confirm `VERCEL_PROJECT_ID_FILEFREE` in Actions. |
| **launchfree** | `package.json`: `next build`. `vercel.json`: no `buildCommand` (implicit Next). | `apps/launchfree/.vercel/output` | [`.github/workflows/vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml) matrix `launchfree`; composite action | **yes** (conditional) | Same as studio re: implicit build. | **S** — Optional explicit `buildCommand` in `vercel.json`; **XS** — confirm secret. |
| **distill** | Same as launchfree. | `apps/distill/.vercel/output` | [`.github/workflows/vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml) matrix `distill`; composite action | **yes** (conditional) | Same. | Same. |
| **axiomfolio** | `vercel.json`: `pnpm --filter @paperwork-labs/axiomfolio... run build`; `package.json`: `next build`. | `apps/axiomfolio/.vercel/output` | [`.github/workflows/vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml) matrix `axiomfolio`; [`.github/workflows/vercel-cutover-axiomfolio.yml`](../../.github/workflows/vercel-cutover-axiomfolio.yml) (runs `scripts/vercel-cutover-axiomfolio.mjs`, Vercel REST deploy — **not** `--prebuilt`) | **partial** | Routine prod path uses `--prebuilt`; cutover/maintenance path uses API deployment (consumes quota per [`VERCEL_AUTO_PROMOTE.md`](../infra/VERCEL_AUTO_PROMOTE.md)). | **M** — After cutover is stable, deprecate or narrow cutover workflow; **XS** — document “prebuilt vs cutover” in runbooks. |
| **accounts** | `package.json`: `next build`. `vercel.json`: implicit Next. | `apps/accounts/.vercel/output` | Matrix `accounts` | **partial** | `scripts/vercel-projects.json` lists `projectId` **placeholder** for accounts; workflow skips until valid `VERCEL_PROJECT_ID_ACCOUNTS`. JSON `repoRoot` is **`null`** while `apps/accounts/` exists — mapping drift. | **M** — Set real Vercel project + `projectId`; fix `repoRoot` + add `VERCEL_PROJECT_ID_ACCOUNTS`; **XS** — align JSON note with repo layout. |
| **trinkets** | `package.json`: `next build`. `vercel.json`: install + ignore only (no explicit `buildCommand`). | If prebuilt added: `apps/trinkets/.vercel/output` | **None** in `.github/workflows/` references `trinkets` + `vercel deploy` | **unknown** | Not in `vercel-prebuilt.yaml` filters/matrix; committed mapping exists for linking/promote docs only. Prod update path **not evidenced** from CI in this audit. | **S** — Add `trinkets` to path filters + `matrix.include`; add secret `VERCEL_PROJECT_ID_TRINKETS` handling (name per `scripts/vercel-projects.json`). |
| **design** | `vercel.json`: `pnpm --filter @paperwork-labs/design build-storybook`; `outputDirectory`: `storybook-static`; `package.json`: `build` / `build-storybook`. | `apps/design/.vercel/output` (wrapping Storybook static) | Not in [`vercel-prebuilt.yaml`](../../.github/workflows/vercel-prebuilt.yaml) matrix (no `--prebuilt` CI leg observed) | **no** | Static Storybook deploy not on prebuilt rollout; `projectId` in mapping is placeholder. | **M** — After Vercel project exists, add `design` to prebuilt workflow + secret; extend path filters with `apps/design/**`. |

---

## Coverage summary

| `--prebuilt` | Apps |
| --- | --- |
| **yes** (workflow uses `--prebuilt` when secrets allow) | studio, filefree, launchfree, distill |
| **partial** | axiomfolio (alternate cutover workflow), accounts (mapping/secret blockers) |
| **unknown** | trinkets (no deploy workflow observed) |
| **no** | design (no prebuilt leg) |

## Related artifacts

- [`docs/infra/VERCEL_PREBUILT.md`](../infra/VERCEL_PREBUILT.md) — narrative audit (duplicate detail intentionally avoided here; use this file for rollout table + fix sizing).
- [`docs/infra/VERCEL_LINKING.md`](../infra/VERCEL_LINKING.md) — local `pnpm vercel:link` / mapping file.

---

**Last reviewed:** 2026-05-04 (repo snapshot; branch `docs/t3.8-vercel-prebuilt-audit`).
