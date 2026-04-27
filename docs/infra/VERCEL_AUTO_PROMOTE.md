---
title: Vercel auto-promote on merge
last_reviewed: 2026-04-27
owner: infra
status: active
---

# Vercel auto-promote on merge

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

## When promotion runs

| Trigger | When |
| --- | --- |
| `pull_request` `closed` + merged to `main` | One matrix job per app (see below) after every merge. |
| `workflow_dispatch` | On demand. Provide **`pr_number`** (required). Optionally set **`app`** to a single Vercel project slug to run only that leg (e.g. re-promote **studio** for a specific merged PR). |

**paperworklabs.com / Studio:** There is no separate Vercel project named `paperworklabs`. Production for the Studio / marketing surface is the **`studio`** project (`apps/studio`).

## How it works

1. A PR merges to `main` (or you run the workflow manually with a `pr_number`).
2. We resolve the merge’s target SHA (prefer `merge_commit_sha` for squashes).
3. Per app, we check whether the PR changed paths relevant to that app (see [Path filters](#monorepo-path-filters)). If not, that matrix job exits successfully without calling Vercel.
4. We query Vercel: what commit is in **production** for this project? If it already matches the target SHA, we **exit clean** (idempotent).
5. We poll for a `READY` deployment whose metadata matches the merge or head SHA, then `POST` promote — **no rebuild**.
6. On merge events, we comment on the closed PR with per-app results where work ran.

Jobs use **matrix** `fail-fast: false`, so one app failing does not cancel the others. Failures are labeled with the **app** in logs and a final `Report failed promote` step.

**Canonical list:** `scripts/vercel-projects.json` (keep the workflow matrix in sync with this file or update both in one change).

## One-time setup

### 1. Generate a Vercel API token

```
Vercel Dashboard → Settings → Tokens → Create Token
  Name: GH-Actions-promote
  Scope: Full Account (Paperwork Labs)
  TTL: 1 year
```

### 2. Add it to GitHub secrets

```bash
gh secret set VERCEL_API_TOKEN
# paste the token at the prompt
```

The team ID and project IDs are not secret. If `VERCEL_API_TOKEN` is not set, the workflow logs a **warning** and matrix jobs exit **0** (so merges are not blocked by a missing token).

## Tracked apps (matrix + project_id)

| App (Vercel slug / `project`) | `project_id` | Repo root / notes |
| --- | --- | --- |
| `studio` | `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` | `apps/studio` — paperworklabs.com / Studio (not a separate `paperworklabs` row) |
| `filefree` | `prj_DNPGX5GrYcwer9oANv90NKqIT67I` | `apps/filefree` |
| `distill` | `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` | `apps/distill` |
| `launchfree` | `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` | `apps/launchfree` |
| `axiomfolio-next` | `prj_z3JVQGLLfsJO2QZJnK5BvMjfFoK3` | `apps/axiomfolio-next` — primary Next.js AxiomFolio |
| `axiomfolio` | `prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE` | `apps/axiomfolio` — legacy Vite; remove from matrix when G4 retires the deployment |
| `trinkets` | `prj_MFUxaJCbQuSdJZWWVgaEtRllKjzB` | `apps/trinkets` |
| `design` | `TBD_CREATE_BEFORE_MERGE` | `apps/design` (Storybook) — **intentional placeholder** until the Vercel project exists; job skips until you set a real `prj_…` in `scripts/vercel-projects.json` + the workflow |
| `accounts` | `TBD_CREATE_BEFORE_MERGE` | `apps/accounts` (Track H4) — same as above |

**Placeholder rows:** `TBD_CREATE_BEFORE_MERGE` runs a short **Skip** step with a notice (no Vercel API call) so the workflow stays green until the project is created.

## Monorepo path filters

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

Promote is alias-only (no new build in the success path). GitHub Actions time is roughly a few minutes per merge (parallel matrix legs).

**Hobby limits:** A single `main` push can start many Vercel builds; rate limits can delay **builds** (not this promote job), which in turn can cause “no READY deployment” until a build finishes.

## See also

- `.github/workflows/vercel-promote-on-merge.yaml` — the workflow.
- `scripts/vercel-projects.json` — canonical app list and IDs.
- `docs/infra/FOUNDER_ACTIONS.md` — `design` / `accounts` placeholders and DNS.
- `docs/sprints/INFRA_AUTOMATION_HARDENING_2026Q2.md` — sprint tracking.
- `docs/infra/RENDER_INVENTORY.md` — `VERCEL_API_TOKEN` elsewhere.
