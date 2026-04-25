---
owner: agent-ops
last_reviewed: 2026-04-23
doc_kind: philosophy
domain: automation
status: active
---

# Automation Philosophy

Immutable rules for what Paperwork Labs automation (Brain, n8n workflows, GitHub Actions, cron) will and will not do. Edits require founder + `agent-ops` persona ack.

Companions: [`docs/DEPENDABOT.md`](../DEPENDABOT.md), [`docs/BRAIN_PR_REVIEW.md`](../BRAIN_PR_REVIEW.md) (mutable "how").

## 1. Auto-merge rules

A PR may auto-merge ONLY when ALL conditions hold:

1. **Author** is `dependabot[bot]`, `renovate[bot]`, or a Paperwork agent persona
2. **Diff size** is small: ≤ 50 lines changed AND ≤ 5 files
3. **Risk class** is patch or minor (semver-aware classifier in `apis/brain/app/services/dependabot_classifier.py`)
4. **All required CI checks are green** (no skipped, no neutral, no failures)
5. **No code-owner files touched** (i.e. no changes to `apps/*`, `apis/*/app/`, `infra/`, `.github/workflows/`, `docs/philosophy/**`)
6. **No env / secret / config drift** (lockfile-only changes preferred)

Major version bumps NEVER auto-merge. Brain triages them and posts a summary to `#dependabot` with a recommended action.

## 2. When automation MUST stop

The following events freeze all auto-merge and disable the n8n cron schedules:

| Trigger | What happens |
|---|---|
| Production incident open in `#infra` (P0/P1) | All auto-merge paused |
| Founder posts `:freeze:` in any infra channel | All auto-merge + cron paused |
| Brain itself reports degraded status (cb open > 5 min) | Brain-side automation paused; raw n8n still runs |
| AxiomFolio market-hours window (9:30–16:00 ET, M–F) | Trading-related auto-merge paused; rest continues |
| Vendor-wide outage (Render / GitHub / Anthropic) reported in `#infra` | All auto-merge paused until "all clear" posted |

Resume requires an explicit `agent-ops` persona Slack post with a reason.

## 3. Human-merge requirements

These categories of PRs always require a human merge (no auto, no Brain-side auto):

- Database schema migrations (alembic chain changes)
- Changes to `docs/philosophy/**` (CODEOWNERS-locked)
- Changes to persona specs (`apis/brain/personas/*.yaml`)
- Changes to `render.yaml`, `infra/**`, `.github/workflows/**`
- Changes that touch any cost-related code (`PersonaSpec.max_cost_usd`, billing endpoints, cost dashboards)
- Anything tagged `manual-review-required` by the Brain PR reviewer

## 4. No silent merges

Every merge — auto or human — emits a Slack post to the relevant channel:

| Channel | When |
|---|---|
| `#dependabot` | dependency PRs (auto or manual) |
| `#brain-dev` | `apis/brain/**` PRs |
| `#axiomfolio-dev` | `apis/axiomfolio/**` and `apps/axiomfolio*/**` PRs |
| `#infra` | infra/, render.yaml, workflow PRs |
| `#qa` | weekly digest of all merges with cost & golden-suite stats |

A merge with no Slack post = an audit-failure event. The post is written by the Brain `engineering` persona on PR-merged webhook.

## 5. Cron rules

n8n cron schedules and GitHub Actions cron run ONLY in production. Dev / preview environments never run cron — they would step on the founder's local DB or Slack.

Every cron job:

- Has an owner persona declared in the workflow file (`x-owner-persona` annotation in n8n, `# owner: <persona>` comment in `.github/workflows/`)
- Logs to `ops.cron_run_log` with start, end, status, error
- Has a Slack escalation when 3 consecutive runs fail OR a single run exceeds 2x median runtime
- Idempotent — a re-run of the same cron with the same window MUST be a no-op or rebuild the same outputs

## 6. Brain-as-reviewer rules

When Brain reviews a PR (via `apis/brain/app/services/pr_review.py`):

- Review is **advisory by default**. Brain comments and labels but does not auto-approve.
- Brain auto-approves only PRs that pass auto-merge §1 above AND a "diff understood" check (Brain summarizes the diff and confidence ≥ 0.85)
- Brain's review NEVER overrides a human reviewer's request-changes
- Brain explicitly NOTES when a PR touches a domain it doesn't have a persona for (e.g. legal, partnerships) and routes a `for-your-review` ping to the right persona owner

## 7. What we will NOT do

- We will **not** auto-merge PRs from external (non-org) contributors. Ever.
- We will **not** use `gh pr merge --admin` to bypass branch protections in automation. If the protection is in the way, fix the protection.
- We will **not** silently retry a failed cron more than 3 times. After 3 the job MUST surface an alert.
- We will **not** ship an n8n workflow that does heavy LLM work directly. n8n is wiring; Brain does the LLM. (See `docs/INFRA.md` and `docs/BRAIN_ARCHITECTURE.md`.)
- We will **not** auto-deploy on Friday after 12:00 PT without an explicit `:friday-deploy:` ack from the founder in the merge thread.

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. Append-only.

### Amendments

_None yet._
