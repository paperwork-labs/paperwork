# Repo Move Pre-Flight Snapshot

> Captured **2026-04-23** for the planned move of `sankalp404/axiomfolio` →
> `paperwork-labs/axiomfolio`. Companion to `00-repo-move.md`. Use this
> document as the audit record: every section here has a matching
> "post-move verification" step that should diff or re-check the same
> data.

## TL;DR — what's about to move

| Surface | Count | Risk after transfer |
|---|---|---|
| Repo webhooks | **0** | None — nothing manual to re-add |
| Repo deploy keys | **0** | None |
| Self-hosted runners | **0** | None |
| Dependabot secrets | **0** | None |
| Actions secrets (repo-level) | **3** | Must be re-created at new owner OR migrated to org-level secrets |
| Actions variables | **0** | None |
| GitHub Environments | **7** | Auto-managed by Render integration; verify post-move |
| Active rulesets on `main` | **2** | Preserved on transfer per GitHub docs; verify post-move |
| Render services bound to repo | **7** (4 active + 3 suspended) | Render auto-follows GitHub redirect; verify a deploy fires after first push |
| In-flight CI runs | **0** at snapshot time | Safe to transfer immediately |
| Hardcoded `sankalp404/axiomfolio` references in tree | **1 runtime + 7 docs/test/UA** | All listed below |

**Net assessment:** low-friction move. Nothing in production will break
on the GitHub side because there are no manual webhooks, no deploy keys,
and no self-hosted runners. The only **runtime** code reference is
`backend/config.py` `RENDER_REPO_URL`, which is informational (used for
Render schedule sync).

---

## Branch protection — important nuance

The runbook's `gh api repos/.../branches/main/protection` call **404s**
because classic branch protection is **not** enabled on this repo. The
default branch is instead protected by **two active rulesets** (the
modern GitHub mechanism), captured below.

Per [GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository):

> "Repository rulesets are preserved when a repository is transferred."

Verify after move with:

```bash
gh api repos/paperwork-labs/axiomfolio/rulesets
# Expect: 2 entries with ids 11622822 (PR Merge Rule) and 11709753 (PR Review Rule)
```

### Ruleset 11622822 — "PR Merge Rule"

- **Target:** default branch (`~DEFAULT_BRANCH`)
- **Enforcement:** active
- **Rules:**
  - `non_fast_forward` (no force-push to main)
  - `required_status_checks` (strict)
    - `Backend (pytest in docker)` (integration_id 15368 = GitHub Actions)
    - `Frontend (lint/typecheck/test)` (integration_id 15368)
  - `required_linear_history`
  - `deletion` (block branch deletion)
  - `copilot_code_review` (review_on_push: true, review_draft_pull_requests: true)

### Ruleset 11709753 — "PR Review Rule"

- **Target:** default branch (`~DEFAULT_BRANCH`)
- **Enforcement:** active
- **Rules:**
  - `pull_request`
    - `required_approving_review_count: 0`
    - `dismiss_stale_reviews_on_push: true`
    - `require_code_owner_review: true`
    - `require_last_push_approval: false`
    - `required_review_thread_resolution: false`
    - `allowed_merge_methods: [merge, squash, rebase]`

The full JSON dumps live in this branch under
`docs/plans/agent-automation/preflight-data/` (see end of file).

---

## GitHub Actions secrets (repo-level, names only)

| Secret | Last updated |
|---|---|
| `DATABASE_URL_PRODUCTION` | 2026-02-12 |
| `PROD_HEALTH_TOKEN` | 2026-04-21 |
| `PROD_HEALTH_URL` | 2026-04-21 |

**Migration plan:** these are read by the `Pre-merge Deploy Gate`
workflow only. Two reasonable options post-move:

1. **Re-create at the repo level** under `paperwork-labs/axiomfolio`
   (same names; `gh secret set <NAME> --repo paperwork-labs/axiomfolio`).
2. **Promote to org-level** under `paperwork-labs` with
   `--visibility selected --repos axiomfolio` so future Paperwork-Labs
   repos can share them.

Recommend option 2 only for `PROD_HEALTH_*` (since multiple repos may
eventually share the same prod-health prober). `DATABASE_URL_PRODUCTION`
is AxiomFolio-specific — keep it repo-scoped.

## GitHub Environments

These are all auto-created by the Render GitHub integration when a
service deploys, plus `copilot` (Copilot reviewer) and `github-pages`
(present even though we don't use Pages):

```
copilot
github-pages
main - axiomfolio-worker-heavy
render_prod - axiomfolio-api
render_prod - axiomfolio-db
render_prod - axiomfolio-frontend
render_prod - axiomfolio-worker
```

The `render_prod - *` and `main - *` environments are recreated
automatically by Render the first time it deploys a given service after
the transfer. No manual action needed; verify by listing:

```bash
gh api repos/paperwork-labs/axiomfolio/environments | jq '.environments[].name'
```

## Render services bound to the repo

Captured via Render MCP (`list_services`):

| Type | Name | Render ID | Status | Auto-deploy |
|---|---|---|---|---|
| `web_service` | axiomfolio-api | `srv-d64mkqi4d50c73eite20` | active | yes (commit) |
| `background_worker` | axiomfolio-worker | `srv-d64mkqi4d50c73eite10` | active | yes (commit) |
| `background_worker` | axiomfolio-worker-heavy | `srv-d7hpo2v7f7vs738o9p80` | active | yes (commit) |
| `static_site` | axiomfolio-frontend | `srv-d64mkhi4d50c73eit7ng` | active | yes (commit) |
| `cron_job` | admin_coverage_backfill | `crn-d64pouogjchc739tpi8g` | suspended | yes |
| `cron_job` | admin_retention_enforce | `crn-d64mkqi4d50c73eite2g` | suspended | yes |
| `cron_job` | ibkr-daily-flex-sync | `crn-d64mkqi4d50c73eite0g` | suspended | yes |

All 7 currently point to `https://github.com/sankalp404/axiomfolio`.
Render's GitHub App follows the redirect transparently, so post-move
verification is simply: push a no-op commit and confirm the four active
services start a new deploy in the Render dashboard.

The 3 suspended crons are not touched by the move.

## Hardcoded `sankalp404/axiomfolio` references

### Runtime / production code (must be updated)

| File | Line | Type | Action |
|---|---|---|---|
| `backend/config.py` | 306 | `RENDER_REPO_URL` default | Update to `https://github.com/paperwork-labs/axiomfolio.git` |
| `app/services/market/index_universe_service.py` | 21 | Wikipedia HTTP `User-Agent` string | Update for hygiene; non-blocking — Wikipedia accepts the redirect |

### Frontend / docs (cosmetic — links redirect, but worth scrubbing)

| File | Line(s) | Notes |
|---|---|---|
| `frontend/src/components/admin/AnomalyExplanationDrawer.tsx` | 37 | Hard-coded GitHub URL to `MARKET_DATA_RUNBOOK.md`. Will continue to work via redirect. |
| `docs/KNOWLEDGE.md` | 13 (D56) | Mentions "sankalp404/axiomfolio" in the Copilot reviewer note. Update or annotate. |
| `docs/TASKS.md` | 268 | Same D56 note repeated in tasks table. |
| `docs/plans/agent-automation/00-repo-move.md` | many | The runbook itself; intentionally references the old URL throughout (it's documenting the move). Leave as-is. |
| `docs/plans/agent-automation/HANDOFF.md` | many | Same — historical record of the work. Leave as-is. |
| `docs/plans/agent-automation/01-axiomfolio-side.md` | several | Same — leave as-is. |
| `docs/plans/agent-automation/README.md` | 14 | Index entry referencing the old name; update to "(now `paperwork-labs/axiomfolio`)" once moved. |

**Suggested follow-up PR after the move lands:**
`chore: update post-move repo references` — touches 4 files
(`backend/config.py`, `index_universe_service.py`,
`AnomalyExplanationDrawer.tsx`, `docs/plans/agent-automation/README.md`).
The plan-doc historical references stay as-is.

## In-flight work check

Snapshot taken with **0** runs in `in_progress` or `queued` state on
`sankalp404/axiomfolio`. Safe to transfer immediately.

Re-run before the actual transfer:

```bash
gh run list --repo sankalp404/axiomfolio --limit 10 --json status \
  | jq '[.[] | select(.status == "in_progress" or .status == "queued")] | length'
# expect: 0
```

## Local dev machine (this workstation)

- Path: `/Users/axiomfolio/development/axiomfolio`
- Current `origin`: `https://github.com/sankalp404/axiomfolio.git`
- Action after move:

```bash
cd /Users/axiomfolio/development/axiomfolio
git remote set-url origin https://github.com/paperwork-labs/axiomfolio.git
git remote -v  # verify
```

Worktrees on this machine that also need the same update if they
outlive the move (they do not at snapshot time — both transient
worktrees from earlier today's PR work were already cleaned up):

```bash
ls /tmp/axf-worktrees/ 2>/dev/null  # should be empty
```

## Snapshot artifacts

The raw JSON dumps from the inventory commands are committed alongside
this doc under `docs/plans/agent-automation/preflight-data/` so the
post-move diff step can produce empty output:

```bash
# Post-move comparison (after transfer completes)
gh api repos/paperwork-labs/axiomfolio/hooks > /tmp/hooks-post-move.json
diff <(jq -S . docs/plans/agent-automation/preflight-data/hooks-pre-move.json) \
     <(jq -S . /tmp/hooks-post-move.json)
# expect: empty diff

gh api repos/paperwork-labs/axiomfolio/rulesets > /tmp/rulesets-post-move.json
diff <(jq -S '[.[] | {id, name, enforcement, target}]' docs/plans/agent-automation/preflight-data/rulesets-pre-move.json) \
     <(jq -S '[.[] | {id, name, enforcement, target}]' /tmp/rulesets-post-move.json)
# expect: empty diff
```

## Decision points before pulling the trigger

These are the only open questions; everything else is mechanical:

1. **Org-level secrets vs per-repo?** Recommend org-level for
   `PROD_HEALTH_*`, repo-level for `DATABASE_URL_PRODUCTION`.
   _Owner: founder._
2. **Move during the week or weekend?** Render auto-deploy is on for
   all 4 active services; first push after the transfer fires 4 deploys
   in parallel. Pick a low-traffic window if you want to roll back
   without user impact.
   _Owner: founder._
3. **Update Brain `GITHUB_REPO` env BEFORE or AFTER the move?** AFTER —
   Brain's GitHub App calls will follow the redirect for read ops, but
   tools that build URLs from `GITHUB_REPO` (e.g., the planned PR
   automation) would emit broken `paperwork-labs/...` URLs if updated
   prematurely.
   _Owner: this PR's reviewer._

## What this PR does NOT do

This PR is **just the snapshot**. It does not:

- Pause Render auto-deploy (manual step in Render dashboard)
- Transfer the repo (manual step in GitHub UI Settings → Danger Zone)
- Update any references — keeping the snapshot diff clean as a record
- Touch `00-repo-move.md` itself (the runbook stays canonical)

When you're ready to actually transfer, follow `00-repo-move.md` step by
step using this snapshot as the "before" reference.
