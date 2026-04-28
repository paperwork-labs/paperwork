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
| Accounts (Clerk satellite root) | `accounts` | `prj_DidXdCyMrnrigX5us9Sv4noysUil` | `apps/accounts` | Next.js | `accounts.paperworklabs.com` |

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

## `accounts` project — Clerk satellite root configuration

The `accounts` project (`prj_DidXdCyMrnrigX5us9Sv4noysUil`) was created via Vercel API on 2026-04-28 to serve `accounts.paperworklabs.com` as the Clerk satellite root. It was created mid-session AFTER the daily deploy quota was exhausted, so the first build was triggered before env vars were wired — the live deployment currently returns HTTP 500 / `MIDDLEWARE_INVOCATION_FAILED` until the next deploy cycle.

### Required env vars (production + preview + development)

These were copied from the `studio` project on 2026-04-28 (Studio is the canonical Clerk consumer reference):

| Key | Source | Notes |
|---|---|---|
| `CLERK_SECRET_KEY` | mirror of `studio` value | server-only; rotation cascades to all Clerk apps |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | mirror of `studio` value | client-exposed |
| `NEXT_PUBLIC_CLERK_FRONTEND_API` | mirror of `studio` value | Clerk frontend API endpoint |
| `NEXT_PUBLIC_CLERK_DOMAIN` | `accounts.paperworklabs.com` | satellite-root specific |
| `NEXT_PUBLIC_CLERK_IS_SATELLITE` | `false` | This IS the primary; sibling apps set `true` and `NEXT_PUBLIC_CLERK_DOMAIN=accounts.paperworklabs.com` |

### Reproducing the env-var copy (if a sibling project ever needs it)

```bash
VERCEL_TOKEN=$(./scripts/vault-get.sh VERCEL_API_TOKEN)
TEAM=team_RwfzJ9ySyLuVcoWdKJfXC7h5
SOURCE=prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT  # studio
TARGET=prj_DidXdCyMrnrigX5us9Sv4noysUil  # accounts (replace as needed)

# Pull all CLERK_* envs from source (decrypted) and POST each to target.
# See the inline python in PR #367 for the exact loop.
```

The `apis/brain/data/required_env_vars.yaml` manifest (shipped with WS-34 pre-deploy guard, PR #365) is the canonical source of which env vars each project needs — `scripts/check_pre_deploy.py` enforces it before any deploy.

### Cloudflare DNS (live)

```
CNAME accounts.paperworklabs.com → cname.vercel-dns.com
       (record id d4aae09b48f38ee62e08774ee82cfc62 on zone 6efe0c9f87c80a21617ff040fa2e55dd)
       proxied=false (Vercel manages SSL termination at the edge)
```

### Clerk dashboard satellite-root configuration (founder one-click)

After the next successful deploy unblocks the 500, configure in Clerk dashboard:

1. **Domains → Satellite domains → Add** → `accounts.paperworklabs.com`
2. **Customization → Appearance** → confirm neutral paperwork-labs branding rendered.
3. Each sibling app (FileFree, AxiomFolio, Distill, LaunchFree, Studio) sets `NEXT_PUBLIC_CLERK_IS_SATELLITE=true` + `NEXT_PUBLIC_CLERK_DOMAIN=accounts.paperworklabs.com` so sign-in always redirects through the satellite root. (Already in place for AxiomFolio and FileFree post WS-13/WS-14 stage 3.)

## `design` project — Storybook canvas

The `design` project (`prj_L14nQSlh3AognlHdC8KaJotVJzit`) builds `apps/design/` as a Vite-compiled Storybook static site. Build command: `pnpm --filter @paperwork-labs/design build-storybook`.

### Known issue (2026-04-28)

The latest Vercel build failed with rolldown 1.0.0-rc.17 `[UNLOADABLE_DEPENDENCY]` on cross-app `@axiomfolio/*` imports in `apps/design/src/stories/`. The current live deployment is from a previous successful build. Fix in flight via PR #366 (decouples design canvas from AxiomFolio internals — stories use local mocks). Will land on next deploy cycle.

## Pre-deploy enforcement

Any workflow or agent triggering a Vercel deploy MUST first call `scripts/check_pre_deploy.py` (shipped in WS-34 / PR #365, runbook at `docs/runbooks/PRE_DEPLOY_GUARD.md`). The script refuses to proceed if:

- Brain `/admin/vercel-quota` reports `< 5` deploys remaining for the day, OR
- Required env vars per `apis/brain/data/required_env_vars.yaml` are missing on the target environment.

This closes the 2026-04-28 incident where (a) the daily Hobby quota was exhausted mid-session and (b) `accounts` deployed without env vars and went live as a 500.

## Related

- `docs/infra/VERCEL_LINKING.md` — linking and env workflows.
- `docs/infra/VERCEL_AUTO_PROMOTE.md` — production promotion.
- `docs/runbooks/CLOUDFLARE_OWNERSHIP.md` — DNS account ownership.
- `docs/runbooks/PRE_DEPLOY_GUARD.md` — pre-deploy quota + env-var enforcement (WS-34).
