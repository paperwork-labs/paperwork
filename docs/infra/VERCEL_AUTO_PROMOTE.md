---
title: Vercel auto-promote on merge
last_reviewed: 2026-04-25
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

## Adding more projects

When AxiomFolio or LaunchFree get a Next.js Vercel project, add a row
to the matrix in the workflow:

```yaml
matrix:
  include:
    - project: studio
      project_id: prj_FZvJJnDdQqawjBpJAwC0SuwyMzFT
    - project: axiomfolio          # NEW
      project_id: prj_xxxxxxxxxxxxxxxxxxxx
```

You can find the project ID in `apps/<project>/.vercel/project.json`
after running `vercel link`.

## Manual fallback

If you need to re-promote a PR that already merged:

```
GitHub → Actions → Vercel auto-promote on merge → Run workflow
  pr_number: 142
```

This works even after the original `pull_request: closed` event has
been fully consumed.

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

## See also

- `.github/workflows/vercel-promote-on-merge.yaml` — the workflow.
- `docs/sprints/INFRA_AUTOMATION_HARDENING_2026Q2.md` — sprint where
  this followup was tracked.
- `docs/infra/RENDER_INVENTORY.md` — F-3 (`VERCEL_API_TOKEN` vs
  `VERCEL_TOKEN` env-var consolidation on Render).
