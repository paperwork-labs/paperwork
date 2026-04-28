# Paperwork Labs — Agent instructions

Canonical playbook for humans and AI agents working this repo. **Detail lives in linked files** — do not duplicate long policy here.

## Repo layout (short)

- `apps/*` — product frontends (Next.js is standard; legacy Vite apps are being retired)
- `apis/*` — FastAPI backends (`apis/brain` = shared orchestration)
- `packages/*` — shared libraries (`ui`, `auth-clerk`, analytics, data, …)
- `docs/*` — cross-cutting runbooks (infra, brand, secrets)
- Full stack notes: [.cursorrules](.cursorrules), [.cursor/rules/engineering.mdc](.cursor/rules/engineering.mdc)
- **Vercel apps**: Run `pnpm vercel:link` once per machine so every app under `apps/` has a local `.vercel` link (env pull, deploy, secrets sync). See [docs/infra/VERCEL_LINKING.md](docs/infra/VERCEL_LINKING.md).

---

## 1. Agent dispatch model

### Model / cost tier (hardware)

- **Default:** fast / cheap models (e.g. `composer-2-fast`, delegated `Task` with `model: "fast"`) for mechanical work — refactors, tests, docs, wide search, shell/explore subagents. Target **~90%** of volume here.
- **Escalate to Opus / principal tier only for:** brand palette ratification and parent-mark decisions, **RED**-class incidents or compliance escalations, architecture trade-offs with long-lived blast radius, security-sensitive auth/crypto/PII paths, tax/compliance logic accuracy — see [.cursor/rules/delegation.mdc](.cursor/rules/delegation.mdc) and [.cursor/rules/agent-ops.mdc](.cursor/rules/agent-ops.mdc).
- **Parallelism:** use **`git worktree`** when multiple agents touch the same repo so branches do not stomp each other.
- **Cadence:** prefer **~1-day sprints**, **2–3 per day**, decomposed from founder asks into small PR-sized units.
- **Execution:** run agent jobs **in the background** when the founder is not blocked waiting on the result.

---

## 2. PR & merge discipline

**Automation map:** [docs/infra/PR_PIPELINE_AUTOMATION.md](docs/infra/PR_PIPELINE_AUTOMATION.md)

### Triage labels (`pr-triage.yaml`)

| Label | Meaning | Agent action |
| --- | --- | --- |
| **GREEN** (`green-mergeable`) | Checks complete, mergeable, no hard failures (subject to Vercel soft-fail rules) | Let auto-merge paths run; do not slap `do-not-merge` without cause |
| **YELLOW** (`yellow-needs-fix`) | Mergeable but a check failed | **Fix in-branch** until green — **no bandaids** and no “merge now + follow-up issue” |
| **RED** (`red-blocked`) | Not mergeable (e.g. conflicts) | **Request changes** — rebase/fix, then re-review |

### Auto-merge (when eligible)

- **Dependabot / allowlisted sweeps:** [.github/workflows/auto-merge-sweep.yaml](.github/workflows/auto-merge-sweep.yaml)
- **Agent-output PRs (heuristics + gates):** [.github/workflows/auto-merge-agent-prs.yaml](.github/workflows/auto-merge-agent-prs.yaml)
- **Human-approved path:** [.github/workflows/auto-merge.yaml](.github/workflows/auto-merge.yaml)
- **Blockers:** labels such as `do-not-merge`, `wip`, `needs-review`, `needs-founder-review`, draft PRs, `CHANGES_REQUESTED`, 🔴 markers — see runbook

### Rebase vs `main`

- When **`main` moves**, bring feature branches up to date (rebase or merge per team norm).
- **Repo note:** always-on “auto-rebase every open PR” automation is **deferred** (see PR pipeline doc); use [.github/workflows/rebase-pr.yaml](.github/workflows/rebase-pr.yaml) for **on-demand** rebases until a global workflow lands.

### Git hygiene

- Branch-based development, never push to `main` — [.cursor/rules/git-workflow.mdc](.cursor/rules/git-workflow.mdc)

### GitHub CLI (`gh`) — token vs keyring

`gh` **prefers the environment variable `GITHUB_TOKEN`** over the macOS keyring / `gh auth login` session. Cursor and other tools often inject a **narrow PAT** as `GITHUB_TOKEN`. That is fine for read-only API use but breaks **`gh pr create`** / **`gh pr merge`** with `Resource not accessible by personal access token`.

**Recommended (this repo):**

- For **interactive** PR operations, run GitHub CLI through the wrapper (unsets `GITHUB_TOKEN` for that process only — automation scripts under `scripts/pr-pipeline/` keep using `GITHUB_TOKEN` as today):

  ```bash
  ./scripts/gh-keyring.sh pr merge 123 --squash
  # or
  pnpm gh:keyring -- pr list
  ```

- Or one-off: `env -u GITHUB_TOKEN gh pr merge …`

- Ensure a **full-access** login exists: `gh auth login` (HTTPS + keyring) with **`repo`** scope, or a **fine-grained PAT** with **Contents** and **Pull requests** write, **SSO authorized** for `paperwork-labs` if required. Then `gh auth status` should show **keyring** as the account you use for merges.

- **`gh auth switch`** only affects the keyring account; it does not help until **`GITHUB_TOKEN` is unset** for that invocation (hence the wrapper).

- **Do not** put a read-only PAT in shell profile as `export GITHUB_TOKEN=…` if you use `gh` to merge; use a different name (e.g. `GH_READONLY_TOKEN`) for tools that only read.

---

## 3. Architecture rules

### Frontends

- **Next.js** is the standard for `apps/*`; **Vite** stacks are **legacy** and scheduled for decommission as apps migrate.
- **Design system canvas:** Storybook **8** for shared UI, production host **`design.paperworklabs.com`** — setup/status: [docs/infra/FOUNDER_ACTIONS.md](docs/infra/FOUNDER_ACTIONS.md), motion/component notes: [docs/brand/CANON.md](docs/brand/CANON.md) § Animation

### `packages/ui` (framework-agnostic)

- **No** `next/*` imports, **no** `"use server"`, **no** async React Server Component-style exports from package entrypoints — consumers may be Next, plain React, or tooling.
- Shared **primitives + themes** (Tailwind tokens / CSS) only; app-specific wiring stays in each `app/`.
- Utilities that touch dates should follow UTC-in / user-TZ-at-render patterns consistent with [docs/infra/TIMEZONE_STANDARDS.md](docs/infra/TIMEZONE_STANDARDS.md).

### Auth

- **`packages/auth`** (`@paperwork-labs/auth-clerk`) owns **Clerk** integration: `SignInShell`, `SignUpShell`, **`createClerkAppearance`**, presets — see [packages/auth/README.md](packages/auth/README.md).

### Time

- **UTC** in DB, APIs, logs, and server comparisons; **user timezone only at UI render** — [docs/infra/TIMEZONE_STANDARDS.md](docs/infra/TIMEZONE_STANDARDS.md)

---

## 4. Brain orchestration

- **Crons:** **APScheduler** in Brain with SQLAlchemy job store — canonical doc: [docs/infra/BRAIN_SCHEDULER.md](docs/infra/BRAIN_SCHEDULER.md). Former n8n scheduler crons now run first-party on Brain (Track K complete; transitional `BRAIN_OWNS_*` cutover flags removed). Do not add new long-lived n8n automation without explicit approval.
- **Memory:** episodic **`agent_episodes`** + hybrid retrieval — see `apis/brain/app/services/memory.py`, `apis/brain/app/models/episode.py`.
- **Personas:** Brain loads [.cursor/rules/*.mdc](.cursor/rules) from the image bundle — see `apis/brain/app/services/agent.py`.
- **Secrets awareness:** Brain calls Studio **`/api/secrets`** via `apis/brain/app/tools/vault.py`; scheduled **credential expiry** — `apis/brain/app/schedulers/credential_expiry.py`.
- **Founder asks → work:** break into **~1-day** tasks tracked in repo docs/trackers (e.g. `docs/TASKS.md`, sprint docs) — keep Brain + docs in sync when behavior changes.

---

## 5. Brand canon

- **Rule files:** [.cursor/rules/brand.mdc](.cursor/rules/brand.mdc)
- **Canon:** [docs/brand/CANON.md](docs/brand/CANON.md) — marks, Locked PNG renders (P1–P5), palettes, workflows, § Animation
- **Hub:** [docs/brand/README.md](docs/brand/README.md)
- **Product palettes:** per-product Tailwind / CSS tokens — **one continuous amber span** rule for the **parent** paperclip (not sub-product marks); see brand.mdc

---

## 6. Secrets handling

- **Never** paste production secrets into chat, tickets, or PRs — [.cursor/rules/secrets-ops.mdc](.cursor/rules/secrets-ops.mdc)
- **Studio Vault** is the **source of truth** (`paperworklabs.com/admin/secrets`, `POST /api/secrets`, `make secrets`, `./scripts/vault-get.sh`) — [docs/SECRETS.md](docs/SECRETS.md)
- **Brain:** runtime vault access and per-user `brain_user_vault` — same runbook, **Brain vault integration** section
- **Env drift:** `make env-check`, matrix in secrets-ops.mdc
- **Studio admin — secrets:** When `BRAIN_API_URL` and `BRAIN_INTERNAL_TOKEN` are set, `/admin/secrets` overlays **Brain** registry metadata (criticality, drift summary) and a small **Brain notes** popover (recent episodes) — [docs/infra/BRAIN_SECRETS_INTELLIGENCE.md](docs/infra/BRAIN_SECRETS_INTELLIGENCE.md)

---

## 7. Quick start (local)

- **Conventions:** [.cursorrules](.cursorrules)
- **Decisions log:** [docs/KNOWLEDGE.md](docs/KNOWLEDGE.md) (after material decisions)

---

## Per-skill / rule quick links (`.cursor/rules/*.mdc`)

| Rule file | Topic |
| --- | --- |
| [agent-ops.mdc](.cursor/rules/agent-ops.mdc) | Model routing, cost registry |
| [alpha-researcher.mdc](.cursor/rules/alpha-researcher.mdc) | Alpha research persona |
| [brain-mcp-sync.mdc](.cursor/rules/brain-mcp-sync.mdc) | Brain MCP sync |
| [brain-skill-engineer.mdc](.cursor/rules/brain-skill-engineer.mdc) | Brain skills |
| [brand.mdc](.cursor/rules/brand.mdc) | Brand identity |
| [capital-allocator.mdc](.cursor/rules/capital-allocator.mdc) | Capital allocation |
| [code-quality-guardian.mdc](.cursor/rules/code-quality-guardian.mdc) | Code quality bar |
| [cpa.mdc](.cursor/rules/cpa.mdc) | CPA / advisory |
| [cfo.mdc](.cursor/rules/cfo.mdc) | Unit economics, spend |
| [delegation.mdc](.cursor/rules/delegation.mdc) | When to delegate vs escalate |
| [dep-freshness.mdc](.cursor/rules/dep-freshness.mdc) | Dependency freshness |
| [ea.mdc](.cursor/rules/ea.mdc) | Executive assistant |
| [education-sync.mdc](.cursor/rules/education-sync.mdc) | Education sync |
| [engineering.mdc](.cursor/rules/engineering.mdc) | Staff engineer / stack |
| [git-workflow.mdc](.cursor/rules/git-workflow.mdc) | Branches, PRs |
| [growth.mdc](.cursor/rules/growth.mdc) | Growth |
| [infra-ops.mdc](.cursor/rules/infra-ops.mdc) | Infra ops |
| [legal.mdc](.cursor/rules/legal.mdc) | Legal / compliance |
| [market-data-guardian.mdc](.cursor/rules/market-data-guardian.mdc) | Market data quality |
| [market-data-platform.mdc](.cursor/rules/market-data-platform.mdc) | Market data platform |
| [microstructure.mdc](.cursor/rules/microstructure.mdc) | Microstructure |
| [no-hallucinated-ui-labels.mdc](.cursor/rules/no-hallucinated-ui-labels.mdc) | UI copy discipline |
| [no-silent-fallback.mdc](.cursor/rules/no-silent-fallback.mdc) | No silent fallbacks |
| [ops-engineer.mdc](.cursor/rules/ops-engineer.mdc) | Operations engineering |
| [partnerships.mdc](.cursor/rules/partnerships.mdc) | Partnerships |
| [plan-mode-first.mdc](.cursor/rules/plan-mode-first.mdc) | Planning mode |
| [point-in-time-data.mdc](.cursor/rules/point-in-time-data.mdc) | Point-in-time data |
| [portfolio-manager.mdc](.cursor/rules/portfolio-manager.mdc) | Portfolio management |
| [prod-database.mdc](.cursor/rules/prod-database.mdc) | Production database |
| [production-verification.mdc](.cursor/rules/production-verification.mdc) | Production verification |
| [protected-regions.mdc](.cursor/rules/protected-regions.mdc) | Protected code regions |
| [qa.mdc](.cursor/rules/qa.mdc) | QA / validation |
| [quant-analyst.mdc](.cursor/rules/quant-analyst.mdc) | Quant analysis |
| [revenue-engineer.mdc](.cursor/rules/revenue-engineer.mdc) | Revenue engineering |
| [risk-manager.mdc](.cursor/rules/risk-manager.mdc) | Risk |
| [secrets-ops.mdc](.cursor/rules/secrets-ops.mdc) | Secrets / vault |
| [social.mdc](.cursor/rules/social.mdc) | Social |
| [strategy.mdc](.cursor/rules/strategy.mdc) | Strategy / chief of staff |
| [swing-trader.mdc](.cursor/rules/swing-trader.mdc) | Swing trading |
| [systematic-trader.mdc](.cursor/rules/systematic-trader.mdc) | Systematic trading |
| [tax-domain.mdc](.cursor/rules/tax-domain.mdc) | Tax domain |
| [token-efficiency.mdc](.cursor/rules/token-efficiency.mdc) | Token efficiency |
| [token-management.mdc](.cursor/rules/token-management.mdc) | Token management |
| [trading.mdc](.cursor/rules/trading.mdc) | Trading |
| [ux.mdc](.cursor/rules/ux.mdc) | UX / UI |
| [ux-lead.mdc](.cursor/rules/ux-lead.mdc) | UX lead |
| [validator-curator.mdc](.cursor/rules/validator-curator.mdc) | Validators |
| [workflows.mdc](.cursor/rules/workflows.mdc) | Company playbooks |

**Product-specific:** [apis/axiomfolio/AGENTS.md](apis/axiomfolio/AGENTS.md)

**Studio admin — secrets:** `/admin/secrets` lists the encrypted vault; when `BRAIN_API_URL` and `BRAIN_INTERNAL_TOKEN` are set, the page overlays **Brain** registry metadata (criticality, drift summary) and a small **Brain notes** popover (recent episodes) — see `docs/infra/BRAIN_SECRETS_INTELLIGENCE.md`.

**Key automation:**
- **Slack / Brain**: Brain Slack Adapter and optional on-demand webhooks; scheduled briefings and infra checks run on **Brain** when `BRAIN_SCHEDULER_ENABLED` is true
- **Decision Logger**: Captures decisions from #decisions and commits to KNOWLEDGE.md
