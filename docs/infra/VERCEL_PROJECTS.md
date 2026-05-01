---
last_reviewed: 2026-05-01
---

# Vercel projects (monorepo)

This document tracks which Vercel projects are **connected to the git repository** (automatic previews + production deploys from pushes) versus **orphaned** (manual deploy only, dashboard shows "Connect Git Repository").

Source of truth for app roots: `apps/*/vercel.json` and root `package.json` / `pnpm-workspace.yaml`.

Team: `team_RwfzJ9ySyLuVcoWdKJfXC7h5` (Paperwork Labs, Hobby tier — see `docs/runbooks/PRE_DEPLOY_GUARD.md` for the 100/day deploy cap and how to avoid hitting it).

## Connected (git-linked)

All current production-track projects, last verified 2026-04-28:

| App / package | Project name | Project ID | Root dir | Framework | Custom domain |
|---|---|---|---|---|---|
| Studio | `studio` | `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` | `apps/studio` | Next.js | `paperworklabs.com` (apex via Vercel) |
| AxiomFolio | `axiomfolio` | `prj_7L9N3FpOFRsc12tMfKKWa8q2lDLE` | `apps/axiomfolio` | Next.js | `www.axiomfolio.com` (cutover blocked on quota — see WS-02) |
| FileFree | `filefree` | `prj_DNPGX5GrYcwer9oANv90NKqIT67I` | `apps/filefree` | Next.js | `filefree.ai` |
| LaunchFree | `launchfree` | `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` | `apps/launchfree` | Next.js | `launchfree.ai` |
| Distill | `distill` | `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` | `apps/distill` | Next.js | `distill.tax` |
| Design canvas | `design` | `prj_L14nQSlh3AognlHdC8KaJotVJzit` | `apps/design` | Vite (Storybook static) | `design.paperworklabs.com` |

### `accounts` Vercel project (slated for decommission)

The **`accounts`** project (`prj_DidXdCyMrnrigX5us9Sv4noysUil`) was created under a misunderstanding that the Clerk Account Portal had to be self-hosted on Vercel. **Clerk hosts the Account Portal natively** (`accounts.clerk.services`); production DNS is a **CNAME to Clerk**, not a Vercel app. Track **WS-36** removes the redundant code + Vercel project in a follow-up PR. Until then the dashboard project may still exist — it is **not** listed as a connected production app above.

## Orphan / needs git connect

| App / package | Path | Status |
|---|---|---|
| **Trinkets** | `apps/trinkets/` (`@paperwork-labs/trinkets`) | **Orphan** — Vercel project exists but git is not connected (no auto-deploy). Local app has `vercel.json` with monorepo `installCommand` and Dependabot `ignoreCommand`. |

### Trinkets — founder follow-up (CLI)

Do **not** link from automation; run locally after choosing team and scope:

```bash
cd apps/trinkets
vercel link
```

Then connect the Git provider for the project (same flow as dashboard "Connect Git Repository"), or from CLI after `vercel link`:

```bash
vercel git connect
```

**Recommended branch settings (typical monorepo app):**

- **Production branch:** `main` (matches `vercel.json` → `git.deploymentEnabled.main: true`).
- **Preview:** all branches (or your team's default), so PRs that touch Trinkets get preview URLs when the project root directory is set correctly.

Ensure the Vercel project **Root Directory** is set to `apps/trinkets` so `../../scripts/vercel-install.sh` resolves from the monorepo checkout (align with other apps).

**Note:** `apps/trinkets/.vercel/project.json` is not committed (standard); after `vercel link`, that file holds `projectId` and org `accountId` locally.

## `design` project — Storybook canvas

The `design` project (`prj_L14nQSlh3AognlHdC8KaJotVJzit`) builds `apps/design/` as a Vite-compiled Storybook static site. Build command: `pnpm --filter @paperwork-labs/design build-storybook`.

### Known issue (2026-04-28)

The latest Vercel build failed with rolldown 1.0.0-rc.17 `[UNLOADABLE_DEPENDENCY]` on cross-app `@axiomfolio/*` imports in `apps/design/src/stories/`. The current live deployment is from a previous successful build. Fix in flight via PR #366 (decouples design canvas from AxiomFolio internals — stories use local mocks). Will land on next deploy cycle.

## Pre-deploy enforcement

Any workflow or agent triggering a Vercel deploy MUST first call `scripts/check_pre_deploy.py` (shipped in WS-34 / PR #365, runbook at `docs/runbooks/PRE_DEPLOY_GUARD.md`). The script refuses to proceed if:

- Brain `/admin/vercel-quota` reports `< 5` deploys remaining for the day, OR
- Required env vars per `apis/brain/data/required_env_vars.yaml` are missing on the target environment, OR
- For **`studio`**, **`axiomfolio`**, and **`filefree`**: `scripts/reconcile_clerk_dns.py --check-only` reports Clerk↔Cloudflare DNS drift (WS-37).

This closes the 2026-04-28 incidents where (a) the daily Hobby quota was exhausted mid-session, (b) a mis-scoped `accounts` Vercel deploy went live without env vars, and (c) a Cloudflare zone migration dropped Clerk CNAMEs while Vercel still looked healthy.

## Related

- `docs/infra/VERCEL_LINKING.md` — linking and env workflows.
- `docs/infra/VERCEL_AUTO_PROMOTE.md` — production promotion.
- `docs/runbooks/CLOUDFLARE_OWNERSHIP.md` — DNS account ownership.
- `docs/runbooks/PRE_DEPLOY_GUARD.md` — pre-deploy quota + env-var enforcement (WS-34).
