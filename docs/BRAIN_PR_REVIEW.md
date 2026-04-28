---
owner: agent-ops
last_reviewed: 2026-04-24
doc_kind: reference
domain: automation
status: active
---
# Brain PR Review

Brain is Paperwork Labs' executive reviewer. Brain drives the review itself —
no external webhook, no cron. Brain has its own memory, its own GitHub tools,
and its own agent loop; reviewing a PR is just another thing it can do when
asked (or when it decides it's time).

Dependabot PRs go through the cheap Haiku triage pipeline instead — see
[`DEPENDABOT.md`](./DEPENDABOT.md). Brain stays out of bot-authored PRs by
default.

## How it works

```
              ┌──────────────────────────────────────────────────┐
              │                    Brain                         │
              │                                                  │
              │  ┌────────────┐       ┌────────────────────┐     │
              │  │  MCP tool  │       │  agent loop (chat) │     │
              │  │ brain_*    │──┐ ┌──┤  e.g. "review PRs" │     │
              │  └────────────┘  │ │  └────────────────────┘     │
              │                  ▼ ▼                             │
              │            ┌───────────────┐                     │
              │            │ sweep_open_prs│                     │
              │            └───────┬───────┘                     │
              │                    │                             │
              │   list open PRs   ─┤                             │
              │   skip bots + labeled ones                       │
              │   for each, check memory: reviewed @ head SHA?   │
              │   if new: run review_pr() pipeline ──┐           │
              │                                      ▼           │
              │              ┌─────────────────────────────┐     │
              │              │  review_pr (per PR)         │     │
              │              │   1. get_github_pr          │     │
              │              │   2. get_github_pr_diff     │     │
              │              │   3. memory.search_episodes │     │
              │              │   4. _choose_model          │     │
              │              │   5. Anthropic call         │     │
              │              │   6. review_github_pr       │     │
              │              │   7. memory.store_episode   │     │
              │              └─────────────────────────────┘     │
              └──────────────────────────────────────────────────┘
```

Memory is the source of truth for "already reviewed?" — episodes are keyed
by `source_ref=<pr_number>` with `metadata.head_sha=<sha>`. If the PR gets
new commits, the SHA changes, and Brain reviews again.

## How to trigger it

Brain decides when it runs. There are four entry points:

| Trigger | When to use |
|---|---|
| **Chat with Brain** ("review open PRs") | Interactive / ad-hoc. Agent loop picks up the intent, calls `brain_sweep_open_prs`. |
| **MCP tool** `brain_sweep_open_prs` | Any MCP client (Cursor, external script, another agent). |
| **MCP tool** `brain_review_pr(pr_number)` | Force a full review on one specific PR. |
| **Admin endpoint** `POST /api/v1/admin/pr-sweep` | Automation (cron on Render, curl from CI, etc.). Auth: `X-Brain-Secret`. |

No GitHub Action pings Brain. The old `brain-pr-review.yaml` workflow + HMAC
webhook was removed — it was a dumb RPC on top of an agent that already has
repo access.

If you want periodic autonomous sweeps, add a Render cron job that hits
`/api/v1/admin/pr-sweep` (one curl, auth header). Don't rebuild the webhook.

## MCP tools (in `apis/brain/app/mcp_server.py`)

| Tool | Purpose |
|---|---|
| `list_github_prs` | Find open PRs. |
| `get_github_pr` | Metadata + file list for one PR. |
| `get_github_pr_diff` | Unified diff (≤60k chars). |
| `review_github_pr` | Post a review (raw — body + inline comments). Tier 2 write. |
| `brain_review_pr` | Full pipeline on one PR (fetch → analyze → post → remember). Tier 2 write. |
| `brain_sweep_open_prs` | Full pipeline on every unreviewed open non-bot PR. Tier 2 write. |

## Admin endpoints (in `apis/brain/app/routers/admin.py`)

Auth header: `X-Brain-Secret: <BRAIN_API_SECRET>`.

| Endpoint | Body | Effect |
|---|---|---|
| `POST /api/v1/admin/pr-sweep` | `{organization_id, limit, force}` | Queue sweep in background, return 202. |
| `POST /api/v1/admin/pr-review` | `{pr_number, organization_id}` | Review one PR in background, return 202. |

## Escalation

Critical paths auto-escalate to Sonnet. Defined in
[`apis/brain/app/services/pr_review.py::_CRITICAL_PATHS`](../apis/brain/app/services/pr_review.py):

- `apis/axiomfolio/app/services/execution/` — real money
- `apis/axiomfolio/app/services/gold/risk/` — risk gates
- `alembic/versions/` — schema migrations
- `apis/brain/app/services/llm.py` — Brain's model router
- `apis/brain/app/routers/admin.py` — admin surface
- `infra/` — Docker, compose, deploy config
- `scripts/medallion/` — data-layer enforcement

Override per-deploy via `BRAIN_PR_REVIEW_MODEL` env var on Brain.

## Opt-out

Brain's sweep skips a PR if **any** of these apply:

- Author is a bot (`dependabot[bot]`, `renovate[bot]`, `dependabot-preview[bot]`, `github-actions[bot]`)
- Label: `skip-brain-review`, `deps:major`, `dependencies`, or `do-not-merge`
- Draft PR
- An episode already exists for the PR at its current head SHA (idempotency)

## Cost

Typical PR (Haiku 4.5, ~15k input tokens, 1k output): **~$0.01–0.03**.
Critical PR (Sonnet 4, ~30k input, 2k output): **~$0.15–0.30**.
Sweep on an empty backlog: **~$0** (memory skip fires before any LLM call).

## Required env vars on Brain

| Var | Purpose |
|---|---|
| `GITHUB_TOKEN` | Brain's existing GitHub PAT (already set). |
| `GITHUB_REPO` | `owner/repo` (already set). |
| `ANTHROPIC_API_KEY` | Existing Brain key; also powers the reviewer. |
| `BRAIN_API_SECRET` | Gate for admin endpoints (`X-Brain-Secret`). |
| `BRAIN_PR_REVIEW_MODEL` | (Optional) Model override. Empty = auto-select. |

No repo-level GitHub secrets are needed anymore — `BRAIN_WEBHOOK_URL` and
`BRAIN_GITHUB_WEBHOOK_SECRET` were decommissioned along with the webhook.

## Future: sprint + quarterly review

Same [`apis/brain/app/services/pr_review.py`](../apis/brain/app/services/pr_review.py) pattern — memory + GitHub + Claude — extends to:

- **Sprint planning** — weekly tool call: "given last week's merged PRs, open
  issues, and Linear state, what should we ship next?"
- **Quarterly OKR review** — monthly tool call: "given this quarter's work
  vs stated OKRs, what's drifting?"
- **Executive decisions** — ad-hoc Slack tool call asking Brain to weigh in
  with full repo context + historical memory.

These live outside this doc for now — the seed is the same.
