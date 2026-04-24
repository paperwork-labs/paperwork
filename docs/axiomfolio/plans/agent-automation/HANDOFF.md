# Handoff Summary — Agent-Driven PR Automation

> **Purpose**: Single document that lets any human or agent (on a fresh machine, in a fresh chat) pick up exactly where this work was left. Written 2026-04-22 at the moment of opening PR [#484](https://github.com/sankalp404/axiomfolio/pull/484) and tracking issues [#485](https://github.com/sankalp404/axiomfolio/issues/485) (axiomfolio) + [paperwork#79](https://github.com/paperwork-labs/paperwork/issues/79) (Brain).
>
> If something below is stale, the canonical sources are: `docs/KNOWLEDGE.md` (decisions), `docs/TASKS.md` (sprint), `docs/plans/MASTER_PLAN_2026.md` (roadmap), and the linked tracking issues.

---

## TL;DR

We are building **Phase 1 of "Brain as Dev OS"**: a hands-off PR review/fix/merge loop where Paperwork Brain (`brain.paperworklabs.com`) orchestrates Cursor Background Agents and posts back to GitHub + Slack. AxiomFolio's role is the *trigger* layer (thin GHA workflows, agent prompt templates, GitHub App install). Brain's role is the *orchestrator* layer (webhook intake, dispatcher, write tools, state).

This is **not a new feature** — it fills `draft_pr` / `merge_pr` / `update_doc` rows in [`paperwork/docs/BRAIN_ARCHITECTURE.md` D17 (Tool execution guardrails)](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md) that were specced but never built. It also realigns AxiomFolio to its declared position in BRAIN_ARCHITECTURE line 7: *"axiomfolio is a skill/capability within Brain"*.

**Strategic prerequisite**: move `sankalp404/axiomfolio` -> `paperwork-labs/axiomfolio` (Phase 0).

---

## How this came up

Sequence of intent shifts during the originating chat:

1. **Started as v1 wrap-up**: review/merge the four Wave F live-broker PRs (#480 E*TRADE, #481 Schwab, #482 TastyTrade, #483 Tradier).
2. **Copilot was rate-limiting** the founder, so we ran a parallel Copilot-style review across all four PRs using cheap subagents.
3. Founder asked for **a real automated workflow**, not one-off subagent calls. Requirements crystallized:
   - Holistic fixes only — no band-aids ever
   - Separate security agent that proactively opens its own PRs
   - Iterative back-and-forth (review → fix → re-review → merge)
   - Strict cost discipline ("never close to $10/day"; GHA minutes were the reason the repo went public)
   - Use Cursor Ultra plan compute (cheap models like `composer-2-fast`) instead of OpenAI/Anthropic API spend
4. Founder asked whether **Paperwork Brain** should orchestrate this (link: https://github.com/paperwork-labs/paperwork) since "the goal was always for Paperwork to help me dev work".
5. After surveying the Paperwork repo, we discovered Brain already has ~70% of the primitives needed (webhook intake pattern, GitHub READ tools, MCP server, memory, n8n Slack adapter). The remaining ~30% are exactly the unbuilt D17 rows. **Path 2 selected**: Brain orchestrates, GHA = thin trigger.
6. Founder also asked to **move the repo from `sankalp404` to `paperwork-labs`** to align org boundaries with the meta-product positioning.
7. Founder asked to **publish all of this to GitHub** so the work survives any local machine and can be picked up from anywhere — that produced the PR #484 + issues #485 / paperwork#79 you're reading from now.

---

## Where things stand right now (2026-04-22 snapshot)

### AxiomFolio repo (this one)

- **Branch**: `docs/agent-pr-automation-plans` -> PR [#484](https://github.com/sankalp404/axiomfolio/pull/484) (open, docs-only).
- **Last main commit**: `cd27cf9d feat(execution): Wave F F2 — E*TRADE live executor (#480)`.
- **Active PRs**:
  - [#484](https://github.com/sankalp404/axiomfolio/pull/484) — this plan set (open, docs-only)
  - [#482](https://github.com/sankalp404/axiomfolio/pull/482) — Wave F F4 TastyTrade live executor; CI green but **CONFLICTING** with main (needs rebase, same `broker_router.py` line 79–82 conflict pattern as #480/#481/#483)
  - [#476](https://github.com/sankalp404/axiomfolio/pull/476) — McKinsey review docs (open, low priority)
- **Recently merged Wave F set** (live broker executors landed today, 2026-04-22): #483 Tradier, #481 Schwab, #480 E*TRADE. Foundation #479 landed first.
- **Open issues**:
  - [#485](https://github.com/sankalp404/axiomfolio/issues/485) — this epic (AxiomFolio side)
  - [#419](https://github.com/sankalp404/axiomfolio/issues/419) — unrelated (admin tab pages refactor)
- **Known DANGER ZONE files** that the agent must never modify without human approval — see [`.cursor/rules/protected-regions.mdc`](../../../.cursor/rules/protected-regions.mdc).

### Paperwork repo (`paperwork-labs/paperwork`)

- **Last reviewed HEAD**: `c892ece` (per the plan; verify before starting Brain-side work).
- **Active issue**: [paperwork#79](https://github.com/paperwork-labs/paperwork/issues/79) — Brain-side epic.
- **Existing primitives we're building on** (verified during planning):
  - Webhook intake pattern: `apis/brain/app/routers/webhooks.py` (AxiomFolio events, HMAC-SHA256, Pydantic models)
  - GitHub READ tools: `apis/brain/app/tools/github.py` (`read_github_file`, `search_github_code`, `list_prs`)
  - MCP server with auth: `/mcp` (23 tools)
  - Memory layer: `apis/brain/app/services/memory.py`
  - Slack adapter: n8n workflow `infra/hetzner/workflows/brain-slack-adapter.json` (Hetzner-hosted)
  - AxiomFolio client: `apis/brain/app/tools/axiomfolio.py` (`scan_market`, `get_portfolio`, `preview_trade`, `approve_trade`, `reject_trade`, `execute_trade`)
  - Settings already plumbed for: `AXIOMFOLIO_*`, `GITHUB_TOKEN`, `LANGFUSE_*`
  - Render deployment: `brain-api` service in `render.yaml`
  - 16 personas already cached (D13 in BRAIN_ARCHITECTURE), including `engineering.mdc`, `qa.mdc`, `agent-ops.mdc`

---

## Plan documents (in this PR)

| File | Audience | Estimate |
|---|---|---|
| [`README.md`](./README.md) | Index, decisions log, scope boundary | — |
| [`HANDOFF.md`](./HANDOFF.md) | This document — full context dump | — |
| [`00-repo-move.md`](./00-repo-move.md) | Repo admin — move runbook | 30–80 min |
| [`01-axiomfolio-side.md`](./01-axiomfolio-side.md) | This repo's owners | ~2 days |
| [`02-paperwork-brain-side.md`](./02-paperwork-brain-side.md) | Paperwork Brain owners | ~5 days |

---

## Confirmed decisions (do NOT relitigate without re-asking founder)

| # | Decision | Value | Source |
|---|---|---|---|
| 1 | **Path** | Path 2 — Brain orchestrates, GHA = thin trigger | Founder, after Path 1 (laptop-only Cursor) was scoped and rejected |
| 2 | **Repo destination** | `paperwork-labs/axiomfolio` | Founder ("thinking of moving this repo") |
| 3 | **Bot identity** | GitHub App `paperwork-agent` | Founder ("can you do this for me. B") |
| 4 | **Default model** | `composer-2-fast` (Cursor Ultra plan, included usage) | Founder ("if you use composer, you could do 100s of PRs for cheap") |
| 5 | **Escalation model** | `gpt-5.4-medium` ONLY for: Fixer iter ≥2, DANGER ZONE reviews, Security findings | Cost discipline |
| 6 | **Daily spend cap** | $10/day hard kill, $5/day soft alert | Founder ("never get close to 10 a day") |
| 7 | **Per-PR cap** | $2 default; $0.50 with `agent-budget-low` label | Cost discipline |
| 8 | **Iteration cap** | 3 fixer iterations -> apply `human-review-needed` label, halt | Anti-runaway |
| 9 | **Holistic fixes** | Enforced in `reviewer.md` and `fixer.md` prompts; reviewer's verdict format requires explicit root-cause + scope-of-related-files analysis | Founder ("definitely need it to be holistic"; "no bandaids ever") |
| 10 | **Slack UX** | Existing `brain-slack-adapter` n8n workflow; in-thread approve/reject buttons | Don't rebuild what exists |
| 11 | **Migration story** | None — Path 2 is the destination, no v1->v2 rewrite later | Founder ("we have a server and stuff?") |
| 12 | **Kill switch** | `agent-pause` label on PR; every workflow checks for label, exits early if present | Recovery mechanism |
| 13 | **Reviewer skip-list** | Dependabot PRs, Draft PRs, fork PRs (matches existing `request-copilot-review.yml` skip rules) | Cost discipline + safety |

### Decisions explicitly out of scope right now

- **Not** modifying `app/services/agent/brain.py` — that's portfolio-ops AgentBrain, wrong layer.
- **Not** building cross-repo automation in v1 — only `paperwork-labs/axiomfolio`. Other paperwork-labs repos can opt in later.
- **Not** auto-merging DANGER ZONE PRs — `danger_zone_check.py` always escalates to human.

---

## Phase plan (across both repos, in execution order)

### Phase 0 — Repo move (~30–80 min admin)

Owner: founder. Runbook: [`00-repo-move.md`](./00-repo-move.md).

- Pre-flight: list active PRs, branch protection, secrets, integrations
- Transfer `sankalp404/axiomfolio` -> `paperwork-labs/axiomfolio` (GitHub Settings -> Danger Zone)
- Verify webhooks, branch protection, CI history, secrets
- Update local clones: `git remote set-url origin git@github.com:paperwork-labs/axiomfolio.git`
- Update Render auto-deploy source URL
- Update hardcoded references (`sankalp404/axiomfolio` -> `paperwork-labs/axiomfolio`) in `AGENTS.md`, `docs/PR_AUTOMATION.md`, etc.

**Why first**: Phase 1 of the AxiomFolio side installs a GitHub App at the org level. Easier to install on `paperwork-labs` from day 1 than to migrate the install later.

### Phase 1A (Brain) — Webhook intake (~0.5 day)

Owner: Brain. Plan: [`02-paperwork-brain-side.md`](./02-paperwork-brain-side.md) Phase 1.

- `apis/brain/app/routers/github_webhooks.py` -> `POST /api/v1/webhooks/github`
- HMAC-SHA256 verification using `GITHUB_WEBHOOK_SECRET`
- Pydantic models for `pull_request`, `pull_request_review_comment`, `issue_comment`, `check_run`
- Reuse pattern from existing `webhooks.py` (AxiomFolio events)
- Persist to `brain_github_events` table for audit/replay

**Why first**: AxiomFolio side can't send anywhere if Brain isn't listening.

### Phase 1B (AxiomFolio) — GitHub App + secrets (~20 min)

Owner: founder + repo admin. Plan: [`01-axiomfolio-side.md`](./01-axiomfolio-side.md) Phase 1.

- Create GitHub App `paperwork-agent` under `paperwork-labs` org
  - Permissions: contents (RW), pull requests (RW), issues (RW), checks (R), metadata (R)
  - Events: `pull_request`, `pull_request_review_comment`, `issue_comment`, `push`, `check_run`
- Install on `paperwork-labs/axiomfolio`
- Add repo secrets: `AGENT_APP_ID`, `AGENT_APP_PRIVATE_KEY`, `BRAIN_WEBHOOK_URL`, `BRAIN_WEBHOOK_SECRET`

### Phase 2 (Brain) — Cursor BG agent dispatcher (~1 day)

- `apis/brain/app/services/cursor_dispatcher.py`
- POST to Cursor Background Agents API with prompt template + repo context
- Poll for completion, capture stdout/diff/comments
- Track spend per dispatch in `brain_agent_runs` table
- Daily cap enforcement ($10 hard, $5 soft alert via Slack)
- Per-PR cap enforcement ($2 default, $0.50 if `agent-budget-low` label)
- Model selection logic (default `composer-2-fast`, escalate `gpt-5.4-medium` per rules)

### Phase 3 (Brain) — GitHub PR write tools (~1 day)

- Extend `apis/brain/app/tools/github.py` with: `post_pr_comment`, `post_pr_review`, `request_changes`, `approve_pr`, `merge_pr`, `add_label`, `remove_label`
- Use `paperwork-agent` GitHub App private key for short-lived installation tokens
- Token caching with TTL = 50 min (App tokens valid 60 min)
- All writes gated by D17 tier check before execution

### Phase 4 (Brain) — Iteration state (~0.5 day)

- Migration: `brain_pr_iterations` table (`pr_url`, `iteration`, `last_action`, `spend_total`, `status`)
- Service layer: `apis/brain/app/services/pr_state.py`
- Status transitions: `reviewing -> awaiting_fix -> fixing -> awaiting_review -> approved -> merged | halted`

### Phase 5A (AxiomFolio) — Trigger workflows (~1 day)

- `.github/workflows/agent-pr-review.yml` — fires on `pull_request` opened/synchronize
- `.github/workflows/agent-pr-fixer.yml` — fires on review comment containing `/agent-fix`
- `.github/workflows/agent-auto-merge.yml` — extends existing `agent-merge-after-ci.yml`, honors `/agent-approve` from `paperwork-agent[bot]`
- `.github/workflows/agent-security-sweep.yml` — `workflow_dispatch` initially, flip to nightly cron after 2 weeks
- `.github/scripts/danger_zone_check.py` — flags PRs touching files listed in `.cursor/rules/protected-regions.mdc`; forces escalation
- `.github/scripts/iteration_counter.py` — reads PR labels (`agent-iteration-1/2/3`), increments, applies `human-review-needed` at iter 3

### Phase 5B (AxiomFolio) — Agent prompt templates (~0.5 day)

- `.github/agent-prompts/reviewer.md` — Copilot-style review, holistic-fix doctrine reminder, references `KNOWLEDGE.md` `R##`/`D##` schemas
- `.github/agent-prompts/fixer.md` — uses `babysit` skill, no bandaids
- `.github/agent-prompts/security.md` — OWASP Top 10, secret scan, dependency audit; can open its own PRs

### Phase 5C (Brain) — Slack wiring (~0.5 day)

- Extend `infra/hetzner/workflows/brain-slack-adapter.json` n8n flow
- PR events: review posted, fix opened, merge done, halted-for-human
- Interactive buttons: Approve / Reject / Pause-agent / Take-over
- Daily spend digest in `#dev-agents` at 9am

### Phase 6 (Brain) — Orchestrator loop (~1 day)

- `apis/brain/app/services/pr_orchestrator.py`
- State machine: webhook -> dispatcher -> write tool -> state update -> next-action decision
- Handles: review-completed, fix-needed, fix-completed, ci-result, human-takeover, `agent-pause` label
- Idempotency keys per (`pr_url`, `action`) to handle webhook retries

### Phase 7 (AxiomFolio) — Cleanup + docs (~0.5 day)

- Delete `.github/workflows/request-copilot-review.yml` (replaced by reviewer agent)
- Update `docs/PR_AUTOMATION.md` with new flow diagram
- Add `D###` entry to `docs/KNOWLEDGE.md`
- Document `agent-pause` kill switch + recovery for stuck states

### Phase 8 — Validation & rollout

- Phase 5A–5B validated on **5 small PRs** (label only, no merge yet — Reviewer comments only)
- Phase 6 validated on **3–5 PRs with intentional issues** (force fixer iterations, validate halt at iter 3)
- After **2 weeks of green operation**: flip security sweep from `workflow_dispatch` to nightly cron
- After **4 weeks of green operation**: enable auto-merge (Phase 5A `agent-auto-merge.yml`)

---

## v2–v7 dev-OS roadmap (deferred; out of scope right now)

Each subsequent phase reuses the v1 primitives, so estimates are small. See [`02-paperwork-brain-side.md`](./02-paperwork-brain-side.md) for full detail.

| Phase | Capability | Builds on | Estimate |
|---|---|---|---|
| v2 | Decision Logger expansion (Brain auto-drafts `D###` entries to `KNOWLEDGE.md`) | v1 dispatcher + `update_doc` tool | 1.5d |
| v3 | Daily Dev Briefing (24h shipped + in-flight + blocked) | v1 GitHub read tools + memory recall | 1d |
| v4 | Cross-repo Sprint Sync (`TASKS.md` ↔ Brain memory ↔ `TASKS.md`) | memory entity graph (D5 in BRAIN_ARCHITECTURE) | 2d |
| v5 | Engineering Persona Dispatch (right `.mdc` per PR type) | persona system already cached (D13) | 0.5d |
| v6 | Doc Drift Detection (code-vs-doc gap -> drafts updates) | v2 + memory diff | 1.5d |
| v7 | Incident Response (production health drop -> triage agent -> Slack diagnosis -> fix PR draft) | v1 dispatcher + existing AxiomFolio tools | 2d |

---

## Risks, gotchas, and known unknowns

### High-impact risks

1. **DANGER ZONE bypass**. If `danger_zone_check.py` has a path-matching bug, the agent could merge a risk-gate change. **Mitigation**: every agent merge passes through this check + the GitHub App's branch protection respects required reviews; the App should NOT be granted "bypass branch protection".
2. **Cost runaway**. `composer-2-fast` is cheap but not free; a webhook storm (e.g., a force-push that fires 50 `synchronize` events) could rack up 50 dispatches. **Mitigation**: Phase 2 dispatcher must dedupe by `(pr_url, head_sha)` within a 60s window before dispatching. Daily $10 hard kill is the backstop.
3. **Multi-tenancy drift**. AxiomFolio enforces `current_user.id` scoping per [D88](../../KNOWLEDGE.md). Brain's PR automation runs as `paperwork-agent[bot]`, NOT as a user — be explicit that PR automation does not touch user data; all writes are GitHub-scoped.
4. **Repo move clobbers in-flight PRs**. PR #482 (Wave F4 TastyTrade) is open and conflicting; ideally rebase/merge or close it BEFORE the repo move. Otherwise resolve conflicts post-move.
5. **`paperwork-agent` private key handling**. Private key stored as a GitHub Actions secret on AxiomFolio (`AGENT_APP_PRIVATE_KEY`) **and** as a Render env var on Brain. Two copies = two rotation surfaces. **Mitigation**: rotate quarterly; both stores updated together.

### Known unknowns

1. **Cursor Background Agents API rate limits / pricing**. Plan documents assume Ultra plan covers usage. If Cursor changes terms, re-evaluate model selection.
2. **n8n workflow versioning**. The Slack adapter n8n JSON is hand-maintained on Hetzner. There is no CI/CD for it. Brain Phase 5 should at minimum commit the JSON to the paperwork repo; ideally add a small deploy script.
3. **PR conflict handling by the Fixer**. If the agent rebases a PR onto main and hits a non-trivial conflict, current plan halts to human. Consider whether iter ≥2 should attempt a more aggressive merge strategy.
4. **GitHub App org-level permissions**. Installing on `paperwork-labs` org gives the App access to all org repos. Phase 1B should document the install scope (single-repo only, not org-wide) until ready to expand.

---

## Tech stack reference (won't change)

Per [AGENTS.md](../../../AGENTS.md):

| Layer | Stack |
|---|---|
| Backend | Python 3.11, FastAPI, Celery, PostgreSQL 18 (dev), SQLAlchemy 2.0, Alembic |
| Frontend | React 19, TypeScript 5, Vite, Radix UI, Tailwind CSS, shadcn/ui-style, TanStack Query, Recharts, lightweight-charts |
| Infra | Docker Compose (dev), Render (prod), Cloudflare (DNS/CDN), GitHub Actions (CI) |
| Brokers | IBKR (FlexQuery + Gateway), TastyTrade (SDK), Schwab (OAuth), Tradier, E*TRADE |

Brain stack: same Python/FastAPI/Postgres on Render; n8n on Hetzner for Slack adapter.

---

## Source links

### GitHub

- AxiomFolio repo: https://github.com/sankalp404/axiomfolio
- AxiomFolio plan PR: https://github.com/sankalp404/axiomfolio/pull/484
- AxiomFolio epic: https://github.com/sankalp404/axiomfolio/issues/485
- Paperwork repo: https://github.com/paperwork-labs/paperwork
- Paperwork epic: https://github.com/paperwork-labs/paperwork/issues/79
- BRAIN_ARCHITECTURE.md: https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md

### Local files (paths assume founder's workstation; adjust for other machines)

- Plan files (this PR): `docs/plans/agent-automation/`
- AxiomFolio cursor rules: `.cursor/rules/` (especially `engineering.mdc`, `protected-regions.mdc`, `delegation.mdc`, `git-workflow.mdc`, `production-verification.mdc`, `no-silent-fallback.mdc`)
- AxiomFolio decision log: `docs/KNOWLEDGE.md`
- AxiomFolio sprint plan: `docs/TASKS.md`
- AxiomFolio master plan: `docs/plans/MASTER_PLAN_2026.md`
- AxiomFolio existing PR automation: `docs/PR_AUTOMATION.md`
- Paperwork integration doc: `~/development/paperwork/docs/AXIOMFOLIO_INTEGRATION.md`
- Paperwork handoff doc: `~/development/paperwork/docs/AXIOMFOLIO_HANDOFF.md`
- Paperwork Brain webhook router: `~/development/paperwork/apis/brain/app/routers/webhooks.py`
- Paperwork Brain GitHub tool: `~/development/paperwork/apis/brain/app/tools/github.py`
- Paperwork Slack adapter (n8n): `~/development/paperwork/infra/hetzner/workflows/brain-slack-adapter.json`
- Paperwork Render deployment: `~/development/paperwork/render.yaml`

---

## How to resume this work in a fresh chat

Suggested prompt:

```
Continue agent-driven PR automation work tracked at:
- AxiomFolio: https://github.com/sankalp404/axiomfolio/issues/485
- Brain:      https://github.com/paperwork-labs/paperwork/issues/79
- Plans:      docs/plans/agent-automation/ (HANDOFF.md is the entry point)

Last state: PR #484 [open / merged] with all four plan files. No code yet.

Next phase per HANDOFF.md is: [Phase 0 repo move | Phase 1A Brain webhook | Phase 1B GitHub App | ...].

Cost discipline: composer-2-fast default, $10/day hard cap.
Holistic fixes only: see reviewer.md / fixer.md prompts when written.
Don't relitigate decisions in HANDOFF.md "Confirmed decisions" table.
```

If anything in the plans contradicts founder's actual preference at resume time, update the plan first (PR), then act. Plans are the source of truth, not chat history.
