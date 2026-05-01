---
last_reviewed: 2026-05-01
---

# GitHub Actions quota audit (2026 Q2)

Founder switched `paperwork-labs/paperwork` to **public** after exhausting GitHub Actions minutes on **private** repos (public OSS repos currently receive **effectively unlimited** Actions minutes under GitHub Free for standard hosted runners).

This document is **read-only**: workflows were not edited. Commands below produced the numbers cited.

---

## Data collection commands (verbatim)

Inventory of registered workflows:

```bash
gh api 'repos/paperwork-labs/paperwork/actions/workflows?per_page=100' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);
print('total_count=', d.get('total_count'))
for w in d['workflows']:
    print(w['id'], '|', w['name'], '|', w['state'], '|', w['path'])"
```

Global run count in the date window (see **Window** below):

```bash
gh api 'repos/paperwork-labs/paperwork/actions/runs?per_page=1&created=%3E%3D2026-03-29T00%3A00%3A00Z' --jq '.total_count'
# → 5638
```

Cache usage (separate line item from billable minutes; affects speed and storage billing):

```bash
gh api 'repos/paperwork-labs/paperwork/actions/cache/usage'
# → active_caches_size_in_bytes=10868044825 (~10.1 GiB), active_caches_count=99
```

Per-workflow totals (full pagination of `GET /repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs?created=>=2026-03-29T00:00:00Z`) were aggregated with a local Python helper that:

- iterated `page=` until `<100` runs returned;
- summed wall-clock \( \textit{updated\_at} - \textit{run\_started\_at} \) for `status=="completed"` runs only (workflow-level heuristic, not billing meter).

Sampling **billable minutes** via:

```bash
gh api repos/paperwork-labs/paperwork/actions/runs/$(gh api repos/paperwork-labs/paperwork/actions/runs --jq '.workflow_runs[] | select(.name=="CI" and .conclusion=="success") | .id' | head -1)/timing
```

returned **`total_ms`: 0** under UBUNTU for the sample run (`run_duration_ms` still non-zero → wall time exists, OSS/public billing is \$0).

Org billing Actions endpoint (optional for future Brain job):

```bash
gh api 'orgs/paperwork-labs/settings/billing/actions'
# → HTTP 404 (not exposed to this `gh auth` token; typically needs org billing/admin scope)
```

**Window:** `created >= 2026-03-29T00:00:00Z` (≈30 calendar days ending audit date 2026-04-28). Aggregates are **not** annualized unless noted.

---

## 1. Workflows we have — full inventory

### 1.1 Workflows defined in `.github/workflows/` (32 files)

| Name | File | State | Trigger summary | `runs-on` | Timeout | Path / filter at `on:` | Purpose |
|------|------|-------|-----------------|-----------|---------|-------------------------|---------|
| Agent sprint runner (Track Z) | `agent-sprint-runner.yml` | active | `workflow_dispatch` only | `ubuntu-latest` | 10 min | N/A (manual) | Opens `[ticket]` PRs for Brain workstreams |
| Auto-merge GREEN agent PRs | `auto-merge-agent-prs.yaml` | active | `schedule` */30m; PR events; `workflow_dispatch` | `ubuntu-latest` | 15 min | No `paths` on PR (broad) | Sweeps agent-style PRs for merge |
| Auto-merge dependabot sweep | `auto-merge-sweep.yaml` | active | `schedule` */15m; `workflow_dispatch` | `ubuntu-latest` | 10–15 min (jobs differ) | No | Sweeps Dependabot / allowlisted merges (+ extra jobs later in file) |
| Auto-merge on approval | `auto-merge.yaml` | active | `pull_request_review`; `check_suite`; `workflow_dispatch` | `ubuntu-latest` | 5 min | Event-driven | Merges when approved + checks green |
| Auto-rebase open PRs on main | `auto-rebase-on-main.yaml` | active | `push` main; `workflow_run` Post-main indexes | `ubuntu-latest` | 45 min | No path filter | Rebases compatible PRs after main moves |
| AxiomFolio CI | `axiomfolio-ci.yml` | active | PR + push (`paths`), `workflow_dispatch`; concurrency cancel | `ubuntu-latest` | 3–30 min per job | **Yes** (apps/apis paths) | Axiom slice CI matrix |
| Brain golden suite | `brain-golden-suite.yaml` | active | PR/push **`paths`**; **`schedule` 06:15 UTC**; `workflow_dispatch` | `ubuntu-latest` | 10 min (golden); summary untimed | Yes | Regression matrix + nightly Slack to #qa |
| brain-personas-doc | `brain-personas-doc.yaml` | active | PR + push **`paths`**; `workflow_dispatch` | `ubuntu-latest` | (per job; not all set) | Yes | Persona / Axiom / n8n doc drift checks |
| Chromatic visual regression | `chromatic.yaml` | active | `push` main (no path filter); PR with `paths` | `ubuntu-latest` | See file (large Storybook) | **PR yes; push no** | Chromatic build + VRT |
| CI | `ci.yaml` | active | PR + push **`main`**; concurrency cancel | `ubuntu-latest` (many jobs) | Per-job defaults / varies | **`on:` no paths** — uses `paths-filter` job internally | Primary monorepo CI |
| Code quality | `code-quality.yaml` | active | PR + push **`main`**; concurrency cancel | `ubuntu-latest` | 10 min (lockfile job) | **No** | Structural + frozen lockfile |
| Dependabot weekly rollup | `dependabot-roll-up.yaml` | active | `schedule` Mon 09:00 UTC; `workflow_dispatch` | `ubuntu-latest` | 60 min | N/A scheduled | Rolls Dependabot PRs by ecosystem |
| Docs freshness | `docs-freshness.yaml` | active | PR `paths`; **`schedule` Mon 14:00 UTC** | `ubuntu-latest` | 10 min | Yes (PR) | `last_reviewed` hygiene |
| Docs index drift | `docs-index.yaml` | active | PR + push with **`paths`**; concurrency cancel | `ubuntu-latest` | 3 min | Yes | Validates generated docs indexes |
| Deploy n8n workflows | `deploy-n8n.yaml` | active | Push `infra/hetzner/workflows/*.json`; `workflow_dispatch` | `ubuntu-latest` | default | Yes | Deploy n8n JSON to Hetzner |
| Infrastructure health check | `infra-health.yaml` | active | **`schedule` every 6h** (`0 */6 * * *`); `workflow_dispatch` | `ubuntu-latest` | default | N/A scheduled | curls n8n + webhook deliveries |
| Medallion lint (all backends) | `medallion-lint.yaml` | active | PR + push with **`paths`** | `ubuntu-latest` | 4 min × matrix | Yes | Matrix SQL/medallion checks |
| persona-vocabulary | `persona-vocab.yaml` | active | PR with **`paths`**; `workflow_dispatch` | `ubuntu-latest` | default | Yes | Persona slug alignment |
| Post-main regenerate indexes | `post-main-regen-indexes.yaml` | active | Push main **`paths`**; `workflow_dispatch` | `ubuntu-latest` | 20 min | Yes | Regen docs/tracker JSON on main |
| PR pipeline — agent auto-merge | `pr-pipeline-auto-merge.yaml` | active | **`schedule` */10m**; `check_suite`; `workflow_dispatch` | `ubuntu-latest` | 15 min | No | Agent PR merge helper |
| PR pipeline — auto-rebase on main | `pr-pipeline-auto-rebase-on-main.yaml` | active | Push main; `workflow_dispatch` | `ubuntu-latest` | 45 min | No | Auto-rebase labeled agent PRs |
| PR pipeline — escalate stuck PRs | `pr-pipeline-escalate.yaml` | active | **`schedule` hourly :15**; `workflow_dispatch` | `ubuntu-latest` | 15 min | N/A | @founder escalation comments |
| PR pipeline health report | `pr-pipeline-health.yaml` | active | **`schedule` daily 06:00 UTC**; `workflow_dispatch` | `ubuntu-latest` | 10 min | N/A | Open PR health metrics |
| PR triage labels | `pr-triage.yaml` | active | **`schedule` daily 06:30 UTC**; `workflow_dispatch` | `ubuntu-latest` | 20 min | N/A | Staleness / merge labels |
| Rebase PR onto main | `rebase-pr.yaml` | active | `workflow_dispatch` | `ubuntu-latest` | 30 min | manual | One-off rebase helper |
| Runbook template | `runbook-template.yaml` | active | PR `paths`; **`schedule` Mon 14:00 UTC** | `ubuntu-latest` | 5 min | Yes (PR) | Runbook template structure |
| Brain ingests sprint lessons on merge | `sprint-lessons-ingest.yaml` | active | Push main **`paths`**; `workflow_dispatch` | `ubuntu-latest` | 5 min | Yes | Lesson ingest hooks |
| Sprint status reconciliation (daily) | `sprint-status-daily.yaml` | active | **`schedule` daily 06:20 UTC**; `workflow_dispatch` | `ubuntu-latest` | 5 min | N/A | Sprint JSON vs TS audit (`workflow created 2026-04-27` — sparse history yet) |
| System graph | `system-graph.yaml` | active | PR + push with **`paths`** | `ubuntu-latest` | 2 min | Yes | `system-graph.json` drift |
| Timezone discipline (Ruff DTZ) | `timezone-discipline.yaml` | active | PR + push **`main`**; concurrency cancel | `ubuntu-latest` (×5 matrix) | default | **No** | Ruff `DTZ` across backends |
| Tracker index drift | `tracker-index.yaml` | active | PR + push with **`paths`**; concurrency cancel | `ubuntu-latest` | 3 min | Yes | Tracker index parity |
| Vercel auto-promote on merge | `vercel-promote-on-merge.yaml` | active | **`pull_request` closed on main** (+ matrix); `workflow_dispatch` | `ubuntu-latest` | 20 min | Event filter (merge path) | Promotes READY previews to prod (no rebuild) |

### 1.2 GitHub-managed / dynamic workflows (API; not YAML in repo)

| Name | Path / id | Notes |
|------|-------------|--------|
| Copilot code review | `dynamic/copilot-pull-request-reviewer/...` — id `243446685` | Small run count locally; billed like other workflows |
| Dependabot Updates | `dynamic/dependabot/dependabot-updates` — id `265718282` | **High aggregate time** (~273.6 min in window below) |
| Dependency Graph update | `dynamic/dependabot/update-graph` — id `265718261` | Supporting Dependabot infra |
| CodeQL | `dynamic/github-code-scanning/codeql` — id `266765052` | **Large aggregate time**; display title often mirrors PR `#` |

All reported **`state: active`** at audit time (`gh api …/actions/workflows`).

---

## 2. What burns minutes today

Interpretation note: **`/timing` showed `billable … total_ms: 0` for OSS/public** (`gh api …/actions/runs/<id>/timing`). “Minutes below” use **summed workflow wall durations** derived from timestamps (Section *Data collection*). For a **hypothetical return to private**, treat these as proportional **risk proxies** alongside GitHub’s native billing meters.

### Top 5 workflows — by run count (windowed API aggregate)

_Approximate rankings from per-workflow pagination (same window):_

1. **CI** — **778** runs (`workflow_id` `244302574`)
2. **Auto-merge on approval** — **772** runs (`247837020`)
3. **CodeQL** (dynamic title, e.g. `PR #…`) — **421** runs (`266765052`)
4. **brain-personas-doc** — **385** runs (`266083790`)
5. **Docs index drift** — **382** runs (`266083788`)

### Top 5 workflows — by aggregate wall duration (minutes, same window)

1. **CI** — **~1530** min — `244302574`
2. **CodeQL** — **~756** min — `266765052`
3. **Vercel auto-promote on merge** — **~564** min — `266192927`
4. **AxiomFolio CI** — **~361** min — `265667753`
5. **Dependabot Updates** (dynamic) — **~274** min — `265718282`

### Workflows that run on every push to `main` without a top-level `paths:` guard

These are the largest **“always pay the dispatch tax”** risks on a busy default branch (even when jobs later skip, the workflow run still exists unless `paths` is at `on:` level):

- **CI** (`ci.yaml`) — primary matrix; internal `paths-filter` only after checkout.
- **Code quality** (`code-quality.yaml`)
- **Timezone discipline** (`timezone-discipline.yaml`) — 5× matrix legs.
- **Chromatic** (`chromatic.yaml`) — **`push` to `main` has no `paths:`** (PR side is path-filtered).
- **Auto-rebase open PRs on main** (`auto-rebase-on-main.yaml`) — every main push + post-main completion.
- **PR pipeline — auto-rebase on main** (`pr-pipeline-auto-rebase-on-main.yaml`) — every main push.
- **Auto-merge on approval / PR pipelines** (`auto-merge.yaml`, `pr-pipeline-auto-merge.yaml`) trigger on suites / rapid schedules rather than literal “push”; they still generate **dense run volume** correlated with churn on main.

Workflows intentionally **path-gated at `on:`** (examples): `medallion-lint.yaml`, `docs-index.yaml`, `brain-golden-suite.yaml` (brain paths), `post-main-regen-indexes.yaml`, `system-graph.yaml`, `tracker-index.yaml`, `deploy-n8n.yaml`, etc.

### Scheduled (cron) workflows — cadence snapshot

| Workflow | Cron / cadence |
|----------|------------------|
| `auto-merge-sweep.yaml` | `*/15 * * * *` (every 15 minutes) |
| `auto-merge-agent-prs.yaml` | `*/30 * * * *` |
| `pr-pipeline-auto-merge.yaml` | `*/10 * * * *` |
| `pr-pipeline-escalate.yaml` | `15 */1 * * *` (hourly at :15) |
| `pr-pipeline-health.yaml` | `0 6 * * *` (daily 06:00 UTC) |
| `pr-triage.yaml` | `30 6 * * *` (daily 06:30 UTC) |
| `dependabot-roll-up.yaml` | `0 9 * * 1` (Mondays 09:00 UTC) |
| `docs-freshness.yaml` | `0 14 * * 1` (Mondays 14:00 UTC) |
| `runbook-template.yaml` | `0 14 * * 1` |
| `infra-health.yaml` | `0 */6 * * *` (every 6 hours) |
| `sprint-status-daily.yaml` | `20 6 * * *` |
| `brain-golden-suite.yaml` | `15 6 * * *` (**also** triggers on qualifying paths) |

**Density warning:** `auto-merge-sweep` + `pr-pipeline-auto-merge` + `auto-merge-agent-prs` together create **continuous** scheduled pressure even when the repo is idle.

---

## 3. Workflow audit — keep / tighten / move to Brain / cut

| Workflow | Verdict | Notes |
|----------|---------|--------|
| **CI** | **TIGHTEN** | Load-bearing. Consider **workflow-level `paths:`** for `push` (with explicit allowlist for root lockfile / shared packages) and/or relying on `paths-filter` output **before** heavy jobs (already partially done). **Concurrency** already `cancel-in-progress`. |
| **Code quality** | **TIGHTEN** | Split triggers: structural checks can be path-narrow; lockfile gate needs root `package.json` / `pnpm-lock.yaml` only — consider two workflows or `paths` on `push` to avoid double runs on docs-only commits. |
| **Timezone discipline** | **TIGHTEN** | Add `paths:` for `**/*.py` (and config) on `push` / PR to cut matrix runs on frontend-only changes. |
| **Chromatic** | **TIGHTEN** | Add **`paths:` on `push` to `main`** mirroring PR filters (big win: push currently unfiltered). |
| **CodeQL** | **KEEP** | Security signal; cost is inherent. Tune **when** analysis runs (schedule vs every PR) only with security review — mark **INVESTIGATE** if Customization needed. |
| **Dependabot dynamic workflows** | **KEEP** | Managed by GitHub; cannot delete from YAML. |
| **Vercel auto-promote** | **KEEP** | Small number of runs vs minutes — high value for prod correctness; **INVESTIGATE** idempotency/skip if already promoted. |
| **AxiomFolio CI** | **KEEP** | Already path-gated; infrequent relative to monolith CI. |
| **Auto-merge on approval** | **KEEP** | Core merge path for GitHub Free (no native auto-merge). |
| **PR pipeline — agent auto-merge** | **TIGHTEN** | Overlaps conceptually with `auto-merge-agent-prs` / **Brain** PR sweep. **INVESTIGATE** single authority; **TIGHTEN** `schedule` from `*/10` if retention rules allow. |
| **Auto-merge dependabot sweep** | **MOVE TO BRAIN / CUT (conditional)** | `apis/brain/app/schedulers/pr_sweep.py` documents replacing this file with in-process sweep. **INVESTIGATE** production parity, then **CUT** or reduce cron if Brain owns merges. |
| **Auto-merge GREEN agent PRs** | **INVESTIGATE** vs Brain sweep | Similar surface as sweep + PR pipeline — consolidate after confirming **which** automation is authoritative. |
| **Auto-rebase on main** + **PR pipeline auto-rebase** | **INVESTIGATE** | Two rebase paths; may be complementary (general vs agent-labeled). Keep until documented merge. |
| **Medallion / docs / tracker / system-graph / persona** | **KEEP** | Path-gated; purpose clear. |
| **Brain golden suite** | **KEEP** | Path-gated + nightly schedule is intentional. |
| **Sprint status daily** | **MOVE TO BRAIN (optional)** | Pure audit script — candidate for `apis/brain/app/schedulers/` (e.g. co-locate with other daily audits) under `BRAIN_SCHEDULER_ENABLED`. |
| **Infra-health** | **MOVE TO BRAIN (optional)** | Similar to existing `infra_health` scheduler modules in Brain — **INVESTIGATE** overlap with `apis/brain/app/schedulers/infra_health.py` before moving. |
| **PR triage / PR pipeline health / escalate** | **KEEP** (or **TIGHTEN** frequency) | Ops visibility; **TIGHTEN** by lowering cadence if alerts remain timely. |
| **Dependabot weekly rollup** | **KEEP** | Weekly; low run count in window (API `total_count` = `1` for `266899880` over the date filter — still load-bearing when it runs). |
| **Deploy n8n** | **KEEP** | Infrequent, path gated. |
| **Agent sprint runner** | **KEEP** | Manual only (`workflow_dispatch`); `0` runs in window. |
| **rebase-pr** | **KEEP** | Manual; low volume. |
| **Copilot code review** | **INVESTIGATE** | Third-party; cost visible but low run count in window. |

**Unclear without product decision:** exact overlap between **GitHub auto-merge family** vs **`merge_ready_prs` in Brain** — resolve by comparing run logs + “which merge actually happened” for one week.

---

## 4. What we would lose if we went private again

- **Billable minutes return** for self-hosted standard runners: public OSS **unlimited** minutes mask true **private** burn. The windowed aggregate for **CI alone (~1530 workflow-wall minutes)** is already **~76%** of GitHub Free’s **2000 min/month/private** quota for the org/repo bucket — **before** counting CodeQL (~756 min), Chromatic (~52 min listed earlier in partial global sample; Vercel ~564 min), Dependabot infra (~274 min), docs/personas matrices, etc. **Rough order-of-magnitude:** current velocity could **overshoot 2000 min/month on private Free** unless throttled — this aligns with anecdotal exhaustion pre-public flip.
- **Dependabot PR automation** consumes non-trivial time (`Dependabot Updates` ~274 aggregated minutes in-window) → still needed, but pricey on private quotas.
- **Vercel** preview/prod deployments are **outside** GitHub Actions minutes, but **`vercel-promote-on-merge` still consumes GitHub runner minutes** (~564 aggregated) when it invokes `gh`/`curl`/matrix steps — do not confuse Vercel build quota with GH Actions quota.
- **Cache storage** (~10.1 GiB `active_caches_size_in_bytes`) is not “minutes”, but noisy caches slow CI → more wall clock → larger private-meter risk if parallelism drops.

Historical **private-era** totals are **not** available via the token used here (billing endpoint 404).

---

## 5. Brain integration plan (spec — do not implement)

### Job: `github_actions_quota_monitor`

- **Scheduler:** APScheduler **`CronTrigger` daily 06:00 UTC** (`0 6 * * *`), `max_instances=1`, `coalesce=true`.
- **Registration:** New module **github_actions_quota.py** under the Brain schedulers package, exporting `install(scheduler)` — wire into the existing `start_scheduler()` installer (same pattern as `infra_heartbeat.install`, `cost_dashboard.install`, etc.) so it runs whenever **`BRAIN_SCHEDULER_ENABLED`** is true.
- **HTTP client:** Use a **classic PAT** or fine-grained token with scopes: `actions:read`, **`repo` read**, and for optional billing: **`read:org`** / org billing as allowed (`GET /orgs/{org}/billing/actions` or equivalent Billing API surfaces — **implementer must validate** GitHub Billing API GA vs preview). **Secrets:** store as `GITHUB_ACTIONS_MONITOR_TOKEN` (name TBD) in Brain env — **never** log raw token.

**Calls:**

1. `GET https://api.github.com/repos/paperwork-labs/paperwork` → capture `private` (flip detector) + `visibility`.
2. `GET https://api.github.com/repos/paperwork-labs/paperwork/actions/cache/usage`.
3. For **each tracked `workflow_id`**,  
   `GET /repos/paperwork-labs/paperwork/actions/workflows/{id}/runs?per_page=100&created=>={24h_ago_ISO}`  
   (paginate until empty). Sum (**completed** runs only):

   \[
     \textit{minutes} \approx \sum \frac{\max(0, \textit{updated\_at} - \textit{run\_started\_at})}{60\,\text{s}}
   \]

   Optionally cross-check a sample with `GET /repos/.../actions/runs/{run_id}/timing` for `billable` when visibility is private.

4. Optionally `GET /orgs/paperwork-labs/settings/billing/actions` (may 403/404) → stash reason in **`extra_json`**.

Persist **daily snapshot** row via SQLAlchemy (design only):

### Table: `GitHubActionsQuotaSnapshot` (design — not implemented)

| Column | Type | Description |
|--------|------|-------------|
| `id` | `uuid` PK (or `bigint` identity) | Surrogate |
| `recorded_at` | `timestamptz` NOT NULL | UTC snapshot time (job completion) |
| `repo` | `text` NOT NULL | e.g. `paperwork-labs/paperwork` |
| `is_public` | `boolean` NOT NULL | `not private` from `GET /repos/{owner}/{repo}` |
| `total_runs_24h` | `integer` NOT NULL | All workflow runs in rolling 24h window (or prior UTC day if you choose fixed windows — document in migration) |
| `total_minutes_24h` | `double precision` NOT NULL | Sum of per-run wall minutes (heuristic) or billable minutes from `/timing` when private |
| `cache_size_bytes` | `bigint` NULL | `active_caches_size_in_bytes` from cache usage endpoint |
| `top_3_workflows_by_minutes` | `jsonb` NOT NULL | e.g. `[{"workflow_id":244302574,"name":"CI","minutes":121.5},…]` |
| `extra_json` | `jsonb` NULL | Billing GET failures, PAT scope errors, sampled `timing` payloads |
| `billable_ms_24h_total` _(optional)_ | `bigint` NULL | Rolled‑up **`/runs/{id}/timing`** when metering matters |

### Alarms / side effects

| Condition | Action |
|-----------|--------|
| `total_minutes_24h > 200` _(tunable)_ | Create issue **`[infra] GH Actions burn rate elevated`** with labels **`infra-alert`**, **`gh-actions`**; body includes snapshot + link to Actions usage. Rate-limit duplicates (e.g., one issue / 7 days / same signature). |
| `is_public == false` **AND** `total_minutes_24h` exceeds a **lower** private threshold (e.g. **150**) | Separate issue **`[infra] GH Actions quota risk (private repo)`** — distinguishes visibility regression. |

**Studio / admin API:**

- **`GET /api/v1/admin/gh-actions-quota`** — last **30** `GitHubActionsQuotaSnapshot` rows (service role auth only).

**Studio UI:**

- **`/admin/infrastructure`** — sparkline (`total_minutes_24h` vs day) + tooltip on top‑3 workflows from JSONB column.

*(No routers, migrations, or models are implemented by this audit.)*

---

## 6. Concrete next 3 PRs after this audit

| PR | Scope | Outcome |
|----|-------|---------|
| **A** — Tighten top minute hogs | Apply **`paths:` on Chromatic push-to-main**, add **narrow `paths` / split jobs** on **Timezone** + optionally **Code quality** `push` triggers | Drops redundant matrix/Storybook work on unrelated commits (**order-of-magnitude tens of aggregated minutes/week** depending on churn — largest lever after CI/CodeQL policy) |
| **B** — Brain monitor | Implement §5 scheduler module + migrations + Studio endpoint + infra issue templates | Visible burn-rate **before** private quota regressions |
| **C** — Cut / consolidate automation | Pilot-disable or thin **`auto-merge-sweep`** cron if **`merge_ready_prs`** parity proven; reconcile **`pr-pipeline-auto-merge`** schedule vs **`auto-merge-agent-prs`** | Removes duplicate scheduled merge sweeps (**high theoretical savings** — verify with Ops first) |

Each is scoped for a **cheap subagent (~1 engineer-day)** excluding security review gates on CodeQL/merge paths.

### Approximate savings if all **TIGHTEN** items were applied

Using the **same ~30‑day window** aggregates for the three clearest UI wins (Section 3):

| Workflow | Window aggregate (wall min) | If unnecessary dispatches cut ~50% |
|----------|----------------------------|-------------------------------------|
| Timezone discipline | ~37.6 | ~**19** |
| Chromatic | ~51.8 | ~**26** |
| Code quality | ~18.9 | ~**9** |

Rough **combined upside ~50 ± 15 aggregated minutes per ~30‑day epoch** from these alone (more if **CI**‑level workflow `paths:` can skip the heavy matrix on docs‑only merges — requires careful allowlisting). Scale **approximately linearly** with PR/main churn.

---

## Appendix — historical note

When private, **heavy PR + push traffic** (~6000 tracked runs over ~30 days) plus large CI matrices likely dominated spend; **`/timing`** confirms **public OSS = \$0 billed** despite non-zero **`run_duration_ms`**. Returning to **private** without thinning triggers would likely **reproduce quota exhaustion** unless GitHub Teams/Enterprise metering or selective workflow disablement is adopted.
