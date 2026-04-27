---
title: Vercel auto-promote on merge
last_reviewed: 2026-04-26
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

## How it works

1. A PR merges to `main`. GitHub fires the workflow.
2. We resolve the PR's head SHA from the merge event payload.
3. We query Vercel: "what's currently in production for `studio`?".
   - If the prod SHA matches → webhook fired correctly, **exit clean**
     (idempotent; no double-promote).
   - If it doesn't match → continue.
4. We poll Vercel up to 6 minutes for a `READY` deployment with
   `meta.githubCommitSha == <PR head SHA>`. The preview build was
   already triggered when the PR opened, so this is usually instant.
5. We `POST /v10/projects/{id}/promote/{deploymentId}` — flips the
   alias, **no rebuild**, doesn't consume a build credit.
6. We comment on the closed PR so the audit log shows the path
   ("webhook fired correctly" vs "auto-promoted as backup").

## One-time setup

Two things needed:

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

That's it. The team ID and project ID are already hardcoded in the
workflow (they aren't secret — only the token is).

The workflow has a graceful no-op if `VERCEL_API_TOKEN` isn't set:
it logs a warning and exits 0, so failing to set the secret won't
block PR merges.

## Tracked apps

Matrix key `project` (Vercel project slug) and `project_id` in `.github/workflows/vercel-promote-on-merge.yaml`:

| App (`project`) | Vercel `project_id` |
| --- | --- |
| `studio` | `prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT` |
| `filefree` | `prj_DNPGX5GrYcwer9oANv90NKqIT67I` |
| `distill` | `prj_1TKlkMmY3vLVNfAfRxUY57z43m11` |
| `launchfree` | `prj_hXQNtz5g7IAwx8lvCkODWxOyHcP7` |
| `axiomfolio-next` | `TBD_CREATE_BEFORE_MERGE` (link `apps/axiomfolio-next` in Vercel, then replace) |
| `trinkets` | `TBD_CREATE_BEFORE_MERGE` (link `apps/trinkets` in Vercel, then replace) |
| `accounts` | `TBD_CREATE_BEFORE_MERGE` (create + link `apps/accounts` after Track H4; then replace) |
| `design` | `TBD_CREATE_BEFORE_MERGE` (create + link `apps/design` Storybook → `design.paperworklabs.com`; see `DESIGN_CANVAS_DEPLOY.md`) |

While an entry is still `TBD_CREATE_BEFORE_MERGE`, that matrix job **skips** the promote path (no API call) so merges stay green until the project exists in the team and the workflow is updated with a real `prj_…` id.

## Monorepo path filters (Studio, Distill, LaunchFree)

**Studio**, **Distill**, and **LaunchFree** are configured in Vercel with
monorepo path filters (or `ignoreCommand`) so they do not build on every
`main` push. **FileFree** does not use the same filter, so it tends to
track `main` automatically.

Cross-cutting edits that never touch an app’s root (for example only
`docs/**`, or an API under `apis/**`) may **not** start a preview or
production build for those filtered projects. The lockfile, workspace
root `package.json`, and `packages/**` are treated as shared: the
auto-promote workflow only runs a promote job for an app when the merged
PR touches `apps/<app>/**`, `packages/**`, `pnpm-lock.yaml`, or root
`package.json`.

Do **not** change Vercel project path settings here without founder
review; if production looks stale, use the **Manual fallback** section
below, or merge a change under `apps/<app>/` so the next auto-promote run
has a READY preview to pick up.

## Adding more projects

Add a row to the matrix in `.github/workflows/vercel-promote-on-merge.yaml`
and document the project ID (from Vercel → Project Settings → General,
or `apps/<project>/.vercel/project.json` after `vercel link`).

## Manual fallback

**Promote a specific merged PR** (alias flip, no new build):

```
GitHub → Actions → Vercel auto-promote on merge → Run workflow
  pr_number: <number>
```

Runs all matrix jobs; each job skips unless the PR touched that
app’s paths (or shared paths above). Use this when the merge event ran
but Vercel never had a READY preview to promote.

**Check production vs `main`:** Compare the latest **Production**
deployment’s commit SHA in the Vercel dashboard (Deployments → filter
Production) with `git log -1 --oneline origin/main`, or use the Vercel
MCP / API (`list_deployments` with `target=production`).

## Why not just switch to native webhooks?

Two reasons we keep the GitHub App AND add this redundancy instead of
switching to native repo-level webhooks:

1. The GitHub App also drives PR comments (preview URLs, build logs,
   inline commit statuses). Native webhooks lose all of that UX.
2. Two missed webhooks isn't a "GitHub App is broken" signal — it's a
   "the network is unreliable" signal. Adding redundancy at the merge
   layer is cheaper than abandoning the integration.

If we ever see > 5 webhook misses in a week, revisit this.

## Cost

Zero on the Vercel side (promote is alias-only, no builds consumed).
Roughly 10 seconds of GitHub Actions per merge — well inside the GH Pro
free tier even at 50 merges/day.

**Hobby build burst:** A single `main` push that starts **multiple**
production builds (one per linked project) can hit Vercel’s per-team
**deployment rate limit** on Hobby. GitHub shows
`Deployment rate limited — retry in 24 hours` on the commit; production
stays on the previous deployment until a build succeeds.

## See also

- `.github/workflows/vercel-promote-on-merge.yaml` — the workflow.
- `docs/sprints/INFRA_AUTOMATION_HARDENING_2026Q2.md` — sprint where
  this followup was tracked.
- `docs/infra/RENDER_INVENTORY.md` — F-3 (Vercel API token env naming on Render; canonical `VERCEL_API_TOKEN`).
