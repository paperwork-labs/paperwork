---
owner: infra-ops
last_reviewed: 2026-04-27
doc_kind: runbook
domain: infra
status: active
---

# PR pipeline automation

> **Motivation:** “So there are open PRs for a while — should we fix the cause?” This runbook describes what we automated on `main` to shorten queue time and reduce index/conflict churn without turning off human review.

## Flow (high level)

```mermaid
flowchart LR
  A[Agent or human opens PR] --> B[CI checks]
  B --> C{Green + mergeable?}
  C -->|Approved path| D[auto-merge.yaml merges on approval]
  C -->|Dependabot| E[auto-merge-sweep / sweep job]
  C -->|Allowlisted bot or user| F[auto-merge-sweep / agent-pr-merge]
  D --> G[Merge to main]
  E --> G
  F --> G
  G --> H[post-main-regen-indexes]
  H --> I[Fresh tracker-index + docs index on main]
  I --> J[Vercel promote / Brain ingest]
```

| Workflow | Role |
| --- | --- |
| `auto-merge.yaml` | Event-driven: merges **human** PRs once there is an approving review and checks pass. |
| `auto-merge-sweep.yaml` | Scheduled (every 15 minutes): **Dependabot** sweep; **agent-pr-merge** for allowlisted authors (see below). |
| `post-main-regen-indexes.yaml` | On every push to `main`, regenerates `apps/studio/src/data/tracker-index.json` and `docs/_index.yaml` when needed; commit message includes `[skip ci]` to avoid CI thrash (other workflows can still run `workflow_run`). |
| `auto-rebase-on-main.yaml` | On push to `main` and when `Post-main regenerate indexes` completes successfully, rebases same-repo open PRs that are behind `main` (skips drafts, forks, opt-out label `no-auto-rebase`). Regen commits use `[skip ci]`; the `workflow_run` trigger catches rebase after indexes land. |
| `pr-pipeline-health.yaml` | Nightly (UTC) + manual: metrics in the workflow summary — open PR count, behind `main`, failing/pending checks (with Vercel soft rules), and a narrow “automation gap” count for sweep-eligible bot/allowlist PRs that are green + mergeable + up to date but still open. |
| `vercel-promote-on-merge.yaml` | (Existing) Deploy after merge. |

### Vercel rate limits

GitHub checks whose names look like **Vercel** and whose failure output indicates **rate limit**, **build limit exceeded**, or **deployment skipped** are treated as **soft failures** in:

- `auto-merge.yaml`
- both jobs in `auto-merge-sweep.yaml`

When that happens, the sweep may post a single informational comment on the PR (deduplicated) so reviewers know production deploy can follow via promote-after-merge.

### Auto-rebase on `main`

`auto-rebase-on-main.yaml` rebases **in-repo** branches (not forks) that are behind `main`, with a second trigger when **Post-main regenerate indexes** completes so PRs can follow `[skip ci]` index commits (push workflows do not run for those commits). Opt out with label **`no-auto-rebase`**. **Manual** rebases: `rebase-pr.yaml` and `.github/scripts/rebase_pr_branch.sh`.

### Drift checks (`tracker-index.yaml`, `docs-index.yaml`)

PR and `main` path-filtered checks keep `tracker-index.json` / `docs/_index.yaml` aligned with sources. They complement `post-main-regen-indexes` (which writes both files on `main` after merges).

## Founder runbook

### Disable auto-merge for one PR

Add label **`do-not-merge`** (also respected: `blocked`, `wip`, `hold`). The scheduled jobs skip labeled PRs.

### Who can be auto-merged without approval

Only authors listed in [`.github/auto-merge-allowlist.yaml`](../../.github/auto-merge-allowlist.yaml). The scheduled job also requires:

- No **`CHANGES_REQUESTED`** review (latest state per reviewer).
- No **`🔴`** in PR review or issue comments (Brain / QA “red” marker).
- Addition count **≤ 800** (sanity cap).
- PR age **≥ 5 minutes** (avoid racing the author right after push).
- At most **5** squash merges per workflow run (protects Vercel webhooks).

**Dependabot** PRs are handled only by the **sweep** job, not the agent job (even if a bot login appeared on the allowlist).

### Tuning the allowlist

Edit `.github/auto-merge-allowlist.yaml` in a normal PR. Prefer adding **bot** logins (`cursor-agent[bot]`, etc.) over broad human allowlists.

## Operational notes

- **Concurrency:** `auto-merge-sweep` uses a single concurrency group so scheduled runs do not overlap.
- **Markers:** Workflow summaries include `<!-- auto-merge-sweep:checked:YYYYMMDD-HHMM -->` (UTC) for traceability.
- **Indexes:** If `post-main-regen-indexes` cannot push (branch protection), fix token/permissions or run generators locally and PR.

## Related

- [Brain scheduler / cutover env](BRAIN_SCHEDULER.md)
- `.github/workflows/auto-merge-sweep.yaml`
- `.github/workflows/post-main-regen-indexes.yaml`
- `.github/workflows/auto-rebase-on-main.yaml`
- `.github/workflows/pr-pipeline-health.yaml`
