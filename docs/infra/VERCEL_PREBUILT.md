# Vercel `--prebuilt` rollout completeness (T3.8)

Read-only audit (2026-05-04) of how each app under `apps/` relates to Vercel and whether production can ship via **Build Output API** + `vercel deploy --prebuilt` (see `.github/workflows/vercel-prebuilt.yaml` and `.github/actions/vercel-prebuilt/action.yaml`).

**Evidence boundaries**

- No `apps/<name>/vercel.json` in this repo sets a `"name"` field; `.vercel/project.json` is gitignored per `docs/infra/VERCEL_LINKING.md`. Dashboard **project slug / id** are taken from committed `scripts/vercel-projects.json` (`slug`, `projectId`) where present, and labeled accordingly.
- Whether GitHub repository secrets (`VERCEL_PROJECT_ID_*`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`) are populated in the live org cannot be verified from git alone — rows use **workflow code path** plus **unknown** where automation is absent or conditional on secrets.

## Main table

| App | Vercel project (committed mapping) | `--prebuilt`? | Build location | Last deploy workflow (on-disk) | Notes |
| --- | --- | --- | --- | --- | --- |
| filefree | `slug` **filefree** (`scripts/vercel-projects.json`; `projectId` `prj_DNPGX5GrYcwer9oANv90NKqIT67I`) | yes | Hetzner self-hosted (`runs-on: [self-hosted, hetzner]` in `.github/workflows/vercel-prebuilt.yaml`) when deploy runs | `.github/workflows/vercel-prebuilt.yaml` | `apps/filefree/vercel.json` sets `"git":{"deploymentEnabled":false}`. Matrix leg `app-name: filefree`. Composite action runs `vercel build` then `npx vercel deploy --prebuilt` (`.github/actions/vercel-prebuilt/action.yaml`). Deploy skipped if `VERCEL_PROJECT_ID_FILEFREE` unset/invalid (see workflow `Resolve project id`). |
| launchfree | `slug` **launchfree** (`prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7`) | yes | Hetzner (same) | `.github/workflows/vercel-prebuilt.yaml` | Same pattern; `git.deploymentEnabled` false. |
| studio | `slug` **studio** (`prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT`) | yes | Hetzner (same) | `.github/workflows/vercel-prebuilt.yaml` | Same pattern. |
| distill | `slug` **distill** (`prj_1TKlkMmY3vLVNfAfRxUY57z43m11`) | yes | Hetzner (same) | `.github/workflows/vercel-prebuilt.yaml` | Same pattern. |
| axiomfolio | `slug` **axiomfolio** (`prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE`) | yes (routine prod path) | Hetzner (same) | `.github/workflows/vercel-prebuilt.yaml` | Same matrix + prebuilt action. **Separate** manual cutover path: `.github/workflows/vercel-cutover-axiomfolio.yml` runs `scripts/vercel-cutover-axiomfolio.mjs`, which uses Vercel **REST** `POST …/deployments` (not `--prebuilt`) — remote build on Vercel for that one-off flow. |
| accounts | `slug` **accounts** (`projectId` placeholder `TBD_CREATE_BEFORE_MERGE` in `scripts/vercel-projects.json`; `repoRoot` in JSON is `null` but `apps/accounts/` exists on disk) | yes (when secret valid) | Hetzner (same) | `.github/workflows/vercel-prebuilt.yaml` | Matrix includes `accounts`; `apps/accounts/vercel.json` present. Prebuilt deploy skips until `VERCEL_PROJECT_ID_ACCOUNTS` looks like `prj_*`. |
| trinkets | `slug` **trinkets** (`prj_MFUxaJCbQuSdJZWWVgaEtRllKjzB`) | **no** | unknown for prod | **none** in `.github/workflows/` invoking `vercel deploy` / `vc deploy` for trinkets | `apps/trinkets/vercel.json` exists and `git.deploymentEnabled` is false, but **trinkets is not** in `vercel-prebuilt.yaml` `matrix.include`. No other workflow under `.github/workflows/` matches `vercel deploy` / `vc deploy` for this app — **production update path from CI is unverifiable here** (mark **unknown** in verdict). |
| design | `slug` **design** (`projectId` `TBD_CREATE_BEFORE_MERGE` in `scripts/vercel-projects.json`) | **no** | unknown for prod | **none** for `--prebuilt` | `apps/design/vercel.json` targets Storybook static (`build-storybook`, `outputDirectory: storybook-static`). Not in `vercel-prebuilt.yaml` matrix. |
| probes | — (no row in `scripts/vercel-projects.json`; no `apps/probes/vercel.json`) | no | n/a | n/a | Playwright probe package only (`apps/probes/package.json`); not a Vercel app in repo. |
| `_archive` | — | no | n/a | n/a | Excluded from `pnpm-workspace.yaml` (`!apps/_archive/**`); no `vercel.json` under `apps/_archive/` in this tree. |

**Workflows on disk that mention Vercel deploy / CLI**

| File | Role |
| --- | --- |
| `.github/workflows/vercel-prebuilt.yaml` | Production path: `vercel pull` → `vercel build` → **`vercel deploy --prebuilt`** via `.github/actions/vercel-prebuilt`. |
| `.github/actions/vercel-prebuilt/action.yaml` | Implements `--prebuilt` deploy step (`npx vercel deploy --prebuilt`). |
| `.github/workflows/vercel-cutover-axiomfolio.yml` | Invokes `vercel-cutover-axiomfolio.mjs` (Vercel API deployment — **not** `--prebuilt`). |
| `.github/workflows/lighthouse-ci.yml` | Waits on / resolves a Studio URL via `gh` checks; **does not** run `vercel deploy`. |
| `.github/workflows/code-quality.yaml` | Runs `node scripts/verify-vercel-json-canon.mjs`; **does not** deploy. |

**`vercel.ts`**

- Glob under `apps/`: **no** `apps/*/vercel.ts` files.

**Root `vercel.json`**

- **None** at repository root (glob verified).

## Verdict per app

| App | Verdict |
| --- | --- |
| filefree | **Migrated (code)** — production deploy is wired to `.github/workflows/vercel-prebuilt.yaml` with `--prebuilt` when secrets allow; live org secret state **unknown**. |
| launchfree | **Migrated (code)** — same. |
| studio | **Migrated (code)** — same. |
| distill | **Migrated (code)** — same. |
| axiomfolio | **Migrated (code)** for the prebuilt workflow; **exception** remains for manual/API cutover (`.github/workflows/vercel-cutover-axiomfolio.yml`). |
| accounts | **Pending / conditional** — prebuilt matrix exists; `scripts/vercel-projects.json` still shows `TBD_CREATE_BEFORE_MERGE` for `projectId` and workflow skips until a real `prj_*` secret. |
| trinkets | **Unknown** — Vercel mapping exists in `scripts/vercel-projects.json`, but **no** `--prebuilt` (or any) deploy workflow references this app in `.github/workflows/`. |
| design | **Pending** — no prebuilt leg; project id placeholder in `scripts/vercel-projects.json`. |
| probes | **N/A** — not a Vercel-deployed app in repo. |
| `_archive` | **N/A** — not an active deployable app surface in workspace. |

## Open questions (need founder action)

- **Vercel Build CPU minutes MTD per project** — requires Vercel team dashboard or API token with analytics scope; not derivable from repo.
- **GitHub Actions secrets** — Confirm each `VERCEL_PROJECT_ID_*` used in `.github/workflows/vercel-prebuilt.yaml` is set to a live `prj_…` (workflow intentionally skips when unset or non-`prj_*`).
- **Trinkets production** — How does `tools.filefree.ai` (or equivalent) receive production deploys today if `git.deploymentEnabled` is false and trinkets is outside `vercel-prebuilt.yaml`? (Manual CLI, Vercel dashboard, or missing automation — **unknown**.)
- **`vercel-promote-on-merge.yaml`** — Multiple docs under `docs/infra/` reference `.github/workflows/vercel-promote-on-merge.yaml`; **that path does not exist** in this worktree’s `.github/workflows/` listing. Either the branch is missing a file present on `main`, the workflow was renamed/removed, or docs are stale — **needs reconcile** (do not assume behavior from docs alone).
- **`scripts/vercel-projects.json` vs tree** — `accounts` row has `"repoRoot": null` while `apps/accounts/` exists; reconcile JSON with reality when touching secrets/matrix.

## `docs/KNOWLEDGE.md`

- Grep for Vercel-related operational text hits general Clerk/Vercel Marketplace and token expiry notes; **no** dedicated decision entry for `--prebuilt` / Build Output API rollout was found under “prebuilt” / “pre-built” (only unrelated “pre-built UI components”).

## Migration checklist (next PR(s))

Ordered by **automation gap first** (highest risk of drift / surprise build minutes where path is undefined), then placeholders.

1. **trinkets** — Add `trinkets` to `vercel-prebuilt.yaml` path filters + `matrix.include` (mirror other apps), add `VERCEL_PROJECT_ID_TRINKETS` handling consistent with existing secrets; confirm `prj_MFUxaJCbQuSdJZWWVgaEtRllKjzB` is the intended production project.
2. **design** — After Vercel project exists and `prj_…` is known, add `design` to prebuilt matrix + `apps/design/**` filter; align `scripts/vercel-projects.json` `projectId` (see `docs/infra/FOUNDER_ACTIONS.md` § design canvas).
3. **accounts** — Replace `TBD_CREATE_BEFORE_MERGE` in `scripts/vercel-projects.json` when a real project exists; ensure `VERCEL_PROJECT_ID_ACCOUNTS` secret matches; optionally fix `repoRoot` to `apps/accounts`.
4. **Docs / workflow drift** — Resolve `vercel-promote-on-merge.yaml` references vs on-disk workflows (update docs or restore workflow).
5. **Optional** — Document or retire one-off **axiomfolio** API deploy path in favor of prebuilt-only if cutover is complete and founders no longer need `vercel-cutover-axiomfolio.yml`.

## Related docs (context only)

- `docs/infra/VERCEL_LINKING.md` — linking and `vercel-projects.json` role.
- `docs/infra/FOUNDER_ACTIONS.md` — design / accounts placeholders, axiomfolio cutover notes.
- `docs/infra/VERCEL_QUOTA_AUDIT_2026Q2.md` — cost motivation for reducing Vercel remote builds.
