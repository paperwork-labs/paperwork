---
title: Vercel auto-promote on merge
last_reviewed: 2026-04-27
owner: infra
status: active
---

# Vercel auto-promote on merge

## Canonical install command

Every `apps/*/vercel.json` in this repo must use the shared install script:

```json
"installCommand": "bash ../../scripts/vercel-install.sh @paperwork-labs/<app>"
```

`scripts/vercel-install.sh` reads the pnpm version from the root `package.json` `packageManager` field — there is one source of truth. Do not duplicate the `corepack enable && corepack prepare ...` chain into individual `vercel.json` files.

Drift is enforced in CI by `scripts/verify-vercel-json-canon.mjs` (wired into `.github/workflows/code-quality.yaml`).

The only exemptions live in the `EXEMPT` set inside the verifier:
- `axiomfolio` — temporary, until the cutover PR lands.
- `_archive` — not deployed.

Adding a new exemption requires editing the verifier with a comment explaining why and a tracking issue.

## Why this exists

Vercel's GitHub App webhook missed two consecutive merges to `main` in
24 hours (PR #142 → commit `f0255542`, PR #143 → commit `83477e70`).
That left **production stuck on stale builds while previews were green**.
The fix in both cases was the same: manually `vercel promote <preview-id>` —
which doesn't burn a build slot, just flips the production alias.

`.github/workflows/vercel-promote-on-merge.yaml` automates that fix as a
**redundant trigger**. The native Vercel webhook still works most of the
time — this workflow only does work when the webhook misses, and exits
cleanly when it lands.

## Canonical matrix

Source of truth: `scripts/vercel-projects.json` (keep the workflow `matrix.include` in lockstep).

| App (`project` / Vercel slug) | Default `project_id` | Optional GitHub repository variable |
| --- | --- | --- |
| `studio` | `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` | `VERCEL_PROJECT_ID_STUDIO` |
| `filefree` | `prj_DNPGX5GrYcwer9oANv90NKqIT67I` | `VERCEL_PROJECT_ID_FILEFREE` |
| `distill` | `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` | `VERCEL_PROJECT_ID_DISTILL` |
| `launchfree` | `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` | `VERCEL_PROJECT_ID_LAUNCHFREE` |
| `axiomfolio-next` | `prj_z3JVQGLLfsJO2QZJnK5BvMjfFoK3` | `VERCEL_PROJECT_ID_AXIOMFOLIO_NEXT` |
| `axiomfolio` | `prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE` | `VERCEL_PROJECT_ID_AXIOMFOLIO` |
| `trinkets` | `prj_MFUxaJCbQuSdJZWWVgaEtRllKjzB` | `VERCEL_PROJECT_ID_TRINKETS` |
| `design` | `TBD_CREATE_BEFORE_MERGE` (skip until linked) | `VERCEL_PROJECT_ID_DESIGN` |
| `accounts` | `TBD_CREATE_BEFORE_MERGE` (optional; no `apps/accounts` today) | `VERCEL_PROJECT_ID_ACCOUNTS` |

**paperworklabs:** There is no separate Vercel project with that name — the primary Paperwork Labs marketing/admin surface is **`studio`** (`apps/studio`).

**brain:** The Brain API runs on **Render** (`apis/brain`), not Vercel — it is intentionally **not** in the promote matrix.

Rows with `TBD_CREATE_BEFORE_MERGE` (and no repository variable override) **skip cleanly** (exit 0) so merges stay green until the founder adds a real `prj_…` id.

## How it works

1. A PR merges to `main`. GitHub fires the workflow (or you run `workflow_dispatch`).
2. Each matrix leg resolves **`PROJECT_ID`**: optional repository variable `VERCEL_PROJECT_ID_*` overrides the default id from the matrix / JSON.
3. We resolve the target git SHA: **`merge_commit_sha`** first (squash merges), then fall back to PR `head.sha` for manual runs.
4. **Path filter:** the leg continues only if the PR touched `apps/<app>/**`, `packages/**`, root `package.json`, or `pnpm-lock.yaml`.
5. We compare Vercel **production** READY deployment SHA to the target SHA; if it already matches (case-insensitive / 7-char prefix), we exit (idempotent).
6. We poll Vercel for a **READY** deployment matching that SHA (meta filter + full scan), up to **5 attempts** with **30s** sleep between attempts. HTTP **429** responses log a warning and count as a retry (back off 30s).
7. We `POST /v10/projects/{id}/promote/{deploymentId}` — alias flip only, **no rebuild**.
8. We comment on the closed PR for auditability.

## One-time setup

### 1. Vercel API token (secret)

```
Vercel Dashboard → Settings → Tokens → Create Token
  Name: GH-Actions-promote
  Scope: Full Account (Paperwork Labs)
```

```bash
gh secret set VERCEL_API_TOKEN
```

If the secret is missing, the workflow logs a warning and exits 0.

### 2. Optional: repository variables for project IDs

If you need to override a project id **without** editing the workflow (e.g. design before the matrix is updated), set a **repository variable** (not a secret) using the names in the table above. Non-empty variables take precedence over `matrix.project_id`.

## Dry-run validation (local)

From the repo root, with `VERCEL_API_TOKEN` set:

```bash
./scripts/vercel/validate-auto-promote-matrix.sh
# Optional: assert newest READY deployment matches a merge SHA
./scripts/vercel/validate-auto-promote-matrix.sh "$(git rev-parse origin/main)"
```

- If no token is set, the script prints a warning and exits 0 (CI-friendly).
- On HTTP **429**, the script logs `::warning::` and **skips remaining** API calls.

## Manual fallback (GitHub Actions UI)

**Actions → Vercel auto-promote on merge → Run workflow**

- `pr_number`: required.
- `app`: optional — run a single matrix leg (e.g. `studio`).

## Monorepo path filters

Some apps use Vercel `ignoreCommand` / dashboard path filters. Cross-cutting PRs that only touch `docs/**` or `apis/**` may not produce a preview for every app; the path filter then skips that leg. Shared roots (`packages/**`, lockfile, root `package.json`) still count as relevant for every app.

Apps are only promoted when the merged PR touches `apps/<app>/**`, or shared roots: `packages/**`, `pnpm-lock.yaml`, or root `package.json`. Pure `docs/**` or `apis/**`–only changes will **not** promote a frontend app (by design). Cross-touching lockfile or `packages/**` still counts as relevant for all apps in the matrix.

**Studio**, **Distill**, and **LaunchFree** often use Vercel `ignoreCommand` / monorepo filters so they do not build on every push. If Vercel never produced a `READY` deployment for the merge commit, the workflow **fails that app’s job** (no silent green). Fix by ensuring a build exists for that SHA, then re-run the workflow (optionally with `app` set).

## Adding or renaming an app

1. Create/link the Vercel project; note `prj_…` from the dashboard or `apps/<name>/.vercel/project.json` after `vercel link`.
2. Add or update the entry in `scripts/vercel-projects.json`.
3. Add or update the corresponding row in `.github/workflows/vercel-promote-on-merge.yaml` under `matrix.include`.

Do **not** change Vercel project path settings here without founder
review; if production looks stale, use the **Manual fallback** section
below, or merge a change under `apps/<app>/` so the next auto-promote run
has a READY preview to pick up.

## Manual fallback (workflow_dispatch)

**Promote for one merged PR** (alias flip, no new build) for **all** apps the path filter includes:

```bash
gh workflow run vercel-promote-on-merge.yaml \
  -f pr_number=267
```

**Only one app** (e.g. Studio), after a bad merge or missed webhook:

```bash
gh workflow run vercel-promote-on-merge.yaml \
  -f pr_number=267 \
  -f app=studio
```

`app` must match the matrix `project` slug (e.g. `studio`, `filefree`, `axiomfolio-next`).

**Check production vs `main`:** In the Vercel dashboard, open the project → **Deployments** → **Production** and compare the commit SHA to `git log -1 --oneline origin/main`.

## Debugging a failed promotion

1. Open the **failed matrix job** (job name is `promote [<app>]`). The last failing step is usually **Find READY preview** or **Promote to production**.
2. **Find READY** errors mean no deployment with the merge/head SHA is `READY` — Vercel may still be building, the app may have been skipped by `ignoreCommand`, or Hobby rate limits. Check the Vercel project’s deployment list for that commit.
3. **Promote** or **Check production** errors include HTTP status and the response body. Fix token/permissions, project ID, or Vercel incident first.
4. **Relevant paths** skipped the job: the merged PR did not touch that app’s paths; merge a change that touches the app, shared package, or lockfile, or use `workflow_dispatch` knowing the path check still applies to that PR’s diff.

## Why not just switch to native webhooks?

1. The GitHub App also drives PR comments and commit statuses. Native webhooks drop that UX.
2. Two missed webhooks is a reliability signal, not a reason to remove the app — redundancy at merge time is cheap.

## Cost

Promote calls do not consume Vercel build credits. GitHub Actions time is a few seconds per leg per merge (plus up to ~2.5 minutes of polling when previews are slow).

## See also

- `.github/workflows/vercel-promote-on-merge.yaml`
- `scripts/vercel-projects.json`
- `scripts/vercel/validate-auto-promote-matrix.sh`
- `docs/sprints/INFRA_AUTOMATION_HARDENING_2026Q2.md`
- `docs/infra/RENDER_INVENTORY.md` — Brain / Render vs Vercel split

*Renamed from `VERCEL_TOKEN` to canonical `VERCEL_API_TOKEN` per Track I2 (2026-04-27).*
