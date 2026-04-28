# Vercel projects (monorepo)

This document tracks which Vercel projects are **connected to the git repository** (automatic previews + production deploys from pushes) versus **orphaned** (manual deploy only, dashboard shows “Connect Git Repository”).

Source of truth for app roots: `apps/*/vercel.json` and root `package.json` / `pnpm-workspace.yaml`.

## Connected (git-linked)

Projects that deploy from this repo should appear here once linked in the Vercel dashboard. Update this list when you add or wire a new app.

| App / package | Path | Notes |
|----------------|------|--------|
| *(add rows as confirmed)* | | |

## Orphan / needs git connect

| App / package | Path | Status |
|----------------|------|--------|
| **Trinkets** | `apps/trinkets/` (`@paperwork-labs/trinkets`) | **Orphan** — Vercel project exists but git is not connected (no auto-deploy). Local app has `vercel.json` with monorepo `installCommand` and Dependabot `ignoreCommand`. |

### Trinkets — founder follow-up (CLI)

Do **not** link from automation; run locally after choosing team and scope:

```bash
cd apps/trinkets
vercel link
```

Then connect the Git provider for the project (same flow as dashboard “Connect Git Repository”), or from CLI after `vercel link`:

```bash
vercel git connect
```

**Recommended branch settings (typical monorepo app):**

- **Production branch:** `main` (matches `vercel.json` → `git.deploymentEnabled.main: true`).
- **Preview:** all branches (or your team’s default), so PRs that touch Trinkets get preview URLs when the project root directory is set correctly.

Ensure the Vercel project **Root Directory** is set to `apps/trinkets` so `../../scripts/vercel-install.sh` resolves from the monorepo checkout (align with other apps).

**Note:** `apps/trinkets/.vercel/project.json` is not committed (standard); after `vercel link`, that file holds `projectId` and org `accountId` locally.

## Related

- `docs/infra/VERCEL_LINKING.md` — linking and env workflows.
- `docs/infra/VERCEL_AUTO_PROMOTE.md` — production promotion.
