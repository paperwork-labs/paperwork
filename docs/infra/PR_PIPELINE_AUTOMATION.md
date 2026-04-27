---
owner: infra-ops
last_reviewed: 2026-04-27
doc_kind: runbook
domain: infra
status: active
---

# PR pipeline automation

> **Motivation:** “So there are open PRs for a while — should we fix the cause?” This runbook describes what we automated on `main` to shorten queue time and reduce index/conflict churn without turning off human review or branch protection.

## Flow (automation map)

```mermaid
flowchart TB
  subgraph triggers [Triggers]
    T1[PR opened / sync / labels]
    T2[Cron 15m — dependabot sweep]
    T3[Cron 30m — agent GREEN sweep]
    T4[Cron nightly — PR triage]
    T5[Human approval — auto-merge.yaml]
  end

  subgraph classify [Triage — pr-triage.yaml]
    C1{draft?}
    C2[stale-7d / stale-14d from updated_at]
    C3{mergeable?}
    C4{CI hard fail?}
    C5{checks pending?}
    Lg[label: green-mergeable]
    Ly[label: yellow-needs-fix]
    Lr[label: red-blocked]
  end

  T4 --> classify
  classify --> C1
  C1 -->|yes| C2
  C1 -->|no| C2
  C2 --> C3
  C3 -->|false| Lr
  C3 -->|unknown| C2
  C3 -->|true| C4
  C4 -->|yes| Ly
  C4 -->|no| C5
  C5 -->|yes| Lx[no primary / wait]
  C5 -->|no| Lg

  subgraph merge_paths [Merge paths]
    M1[auto-merge-sweep — dependabot]
    M2[auto-merge-sweep — agent-pr-merge allowlist]
    M3[auto-merge-sweep — allowlisted GREEN comment]
    M4[auto-merge-agent-prs — gh auto-merge]
    M5[auto-merge.yaml — review gate]
  end

  T2 --> M1
  T2 --> M2
  T2 --> M3
  T3 --> M4
  T1 --> M4
  T5 --> M5

  M1 --> G[Merge to default branch]
  M2 --> G
  M3 --> G
  M4 --> G
  M5 --> G
  G --> H[post-main-regen-indexes]
  H --> I[Fresh tracker-index + docs index]
  I --> J[Vercel promote / Brain ingest]
```

### Agent GREEN auto-merge (`auto-merge-agent-prs.yaml`)

```mermaid
flowchart LR
  A[Open PR] --> B{Eligible agent signal?}
  B -->|no| Z[Skip]
  B -->|yes| C{Forbidden branch segment?}
  C -->|revert / breaking / manual| Z
  C -->|no| D{Blocking labels?}
  D -->|do-not-merge / wip / draft label / needs-review / needs-founder-review / …| Z
  D -->|no| E{draft PR?}
  E -->|yes| Z
  E -->|no| F{mergeable + up to date with base?}
  F -->|no| Z
  F -->|yes| G{CHANGES_REQUESTED or 🔴 marker?}
  G -->|yes| Z
  G -->|no| H{CI green?}
  H -->|no| Z
  H -->|yes| I["gh pr merge --squash --auto --delete-branch"]
```

| Workflow | Role |
| --- | --- |
| `auto-merge.yaml` | Event-driven: merges **human** PRs once there is an approving review and checks pass. |
| `auto-merge-sweep.yaml` | Scheduled (every 15 minutes): **Dependabot** sweep; **agent-pr-merge** for allowlisted authors; **allowlisted-merge** for Copilot-style **🟢 GREEN** comment path. |
| `auto-merge-agent-prs.yaml` | Every **30** minutes and on **pull_request** (opened/sync/labels/ready): eligible **agent-output** PRs get **auto-merge** (squash, delete branch) when gates pass; respects **branch protection** (merge completes when GitHub allows). |
| `pr-triage.yaml` | Nightly: applies **green-mergeable** / **yellow-needs-fix** / **red-blocked** plus **stale-7d** / **stale-14d** (idempotent). |
| `post-main-regen-indexes.yaml` | On every push to `main`, regenerates `apps/studio/src/data/tracker-index.json` and `docs/_index.yaml` when needed; commit message includes `[skip ci]` to avoid loops. |
| `vercel-promote-on-merge.yaml` | (Existing) Deploy after merge. |

### Eligibility for `auto-merge-agent-prs.yaml`

A PR is considered for this workflow if **any** of:

1. Author login starts with `agent-`, or  
2. It has label **`agent-output`**, or  
3. Head branch matches `feat/`, `chore/`, `fix/`, or `docs/` **and** the author is a **GitHub App/bot** (`user.type === Bot`) **or** a login from [`.github/auto-merge-allowlist.yaml`](../../.github/auto-merge-allowlist.yaml) / known agent bots (Copilot, Cursor, Claude, Codex connectors).

**Never** auto-merged by this workflow when:

- Head ref contains **`revert/`**, **`breaking/`**, or **`manual/`** (substring match on branch name).  
- Labels include **`do-not-merge`**, **`wip`**, **`draft`**, **`needs-review`**, **`needs-founder-review`**, **`blocked`**, or **`hold`**.  
- PR is **draft**, **not mergeable**, **behind base**, has **CHANGES_REQUESTED**, or **🔴** in review/issue comments.

**Idempotency:** Re-running the workflow only re-attempts `gh pr merge --auto` where gates pass; already-enabled auto-merge or merged PRs may no-op with a logged error (safe to ignore if the PR is already queued or merged).

### Vercel rate limits

GitHub checks whose names look like **Vercel** and whose failure output indicates **rate limit**, **build limit exceeded**, or **deployment skipped** are treated as **soft failures** in:

- `auto-merge.yaml`
- `auto-merge-sweep.yaml` jobs
- `auto-merge-agent-prs.yaml`

When that happens, the sweep may post a single informational comment on the PR (deduplicated) so reviewers know production deploy can follow via promote-after-merge.

### Auto-rebase on `main` (deferred)

A workflow that rebases every open PR whenever `main` advances was **not** added here because [PR #241](https://github.com/paperwork-labs/paperwork/pull/241) already introduces a rebase helper and overlapping automation would race. Revisit after that PR merges or is withdrawn. Related: `rebase-pr.yaml` for manual/on-demand rebases.

## Founder runbook

### Disable auto-merge for one PR

Add label **`do-not-merge`** (also respected: `blocked`, `wip`, `hold`, `needs-review`, `needs-founder-review`). Scheduled and agent workflows skip labeled PRs.

### Who can be auto-merged without approval

- **Dependabot:** `auto-merge-sweep` sweep job.  
- **Allowlist + size/review rules:** `agent-pr-merge` in `auto-merge-sweep` — authors in [`.github/auto-merge-allowlist.yaml`](../../.github/auto-merge-allowlist.yaml), addition cap, no **CHANGES_REQUESTED**, no **🔴**, age ≥ 5 minutes, merge budget per run.  
- **Copilot-style GREEN comment:** `allowlisted-merge` job — see workflow.  
- **Agent-output GREEN path:** `auto-merge-agent-prs` — gates above; uses **GitHub auto-merge** so **required reviews and branch protection still apply**.

**Dependabot** PRs are handled by the **sweep** job, not the allowlisted agent job (even if a bot login appeared on the allowlist).

### Triage labels (automation-managed)

| Label | Meaning |
| --- | --- |
| `green-mergeable` | Checks complete, no hard failures (after Vercel soft rules), mergeable, not draft. |
| `yellow-needs-fix` | Mergeable but at least one non-ignored check failed. |
| `red-blocked` | Not mergeable (e.g. conflicts). |
| `stale-7d` / `stale-14d` | PR `updated_at` idle ≥ 7 or ≥ 14 days (mutually exclusive stale tier). |

### Tuning the allowlist

Edit `.github/auto-merge-allowlist.yaml` in a normal PR. Prefer adding **bot** logins (`cursor-agent[bot]`, etc.) over broad human allowlists.

## Operational notes

- **Concurrency:** `auto-merge-sweep` and `auto-merge-agent-prs` each use a dedicated concurrency group so scheduled runs do not overlap per workflow.  
- **Markers:** Workflow summaries include `<!-- auto-merge-sweep:checked:… -->`, `<!-- auto-merge-agent-prs:… -->`, `<!-- pr-triage:… -->` (UTC) for traceability.  
- **Indexes:** If `post-main-regen-indexes` cannot push (branch protection), fix token/permissions or run generators locally and PR.

## Related

- [Brain scheduler / cutover env](BRAIN_SCHEDULER.md)
- `.github/workflows/auto-merge-sweep.yaml`
- `.github/workflows/auto-merge-agent-prs.yaml`
- `.github/workflows/pr-triage.yaml`
- `.github/workflows/post-main-regen-indexes.yaml`
