---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
---

# Automation state (single source of truth)

> **How to read this page:** every scheduled or event-driven automation in the monorepo is listed with **one owner** (where you flip a switch) and a **status** that reflects defaults in code today. Former n8n cron replacements register when `BRAIN_SCHEDULER_ENABLED=true` (transitional `BRAIN_OWNS_*` cutover flags **retired** — see [BRAIN_SCHEDULER.md](BRAIN_SCHEDULER.md)).

## Founder action: optional gates (still default-off)

1. **Sprint automation:** `BRAIN_OWNS_SPRINT_AUTO_LOGGER`, `BRAIN_OWNS_SPRINT_PLANNER`, `BRAIN_OWNS_AGENT_SPRINT_SCHEDULER` — validate GitHub tokens and workflows before enabling.
2. **PR triage:** `BRAIN_OWNS_PR_TRIAGE` — classifiers on the PR sweep tick.
3. **Secrets jobs:** `BRAIN_OWNS_SECRETS_*` — default on; set `false` to disable individual secrets audit cadences.

---

## Index

| Name | Type | Schedule (TZ) | Owner | Status | What it does | Flag / note | Studio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [pr_sweep](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/pr_sweep.py) | Brain APScheduler | `*/N` min interval (`SCHEDULER_PR_SWEEP_MINUTES`, default 30) UTC | Brain / Render | ✅ Live when `BRAIN_SCHEDULER_ENABLED` | Reviews open PRs and merges when policy allows | `BRAIN_SCHEDULER_ENABLED` | — |
| [proactive_cadence](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/proactive_cadence.py) | Brain APScheduler | Hourly on the hour `0 * * * *` UTC | Brain / Render | ✅ Live | Persona self-briefs to owner channels on cadence | — | — |
| [cfo_cost_dashboard](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/cost_dashboard.py) | Brain APScheduler | `30 15 * * *` UTC daily | Brain / Render | ✅ Live | Zero-LLM Redis cost table to `#cfo` | `SLACK_CFO_CHANNEL_ID` | — |
| [qa_weekly_report](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/qa_weekly_report.py) | Brain APScheduler | `0 17 * * 0` Sun 17:00 UTC | Brain / Render | ✅ Live | QA guardrail + drift baseline digest to `#qa` | `SLACK_QA_CHANNEL_ID` | — |
| [cfo_friday_digest](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/cfo_friday_digest.py) | Brain APScheduler | `0 18 * * 5` Fri 18:00 UTC | Brain / Render | ✅ Live | CFO persona digest from tracker + spend | — | — |
| [sprint_lessons_ingest](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_lessons.py) | Brain APScheduler | `SCHEDULER_SPRINT_LESSONS_HOURS` (default 6h) | Brain / Render | ✅ Live | Lifts `## What we learned` from sprint docs to memory | — | — |
| [merged_prs_ingest](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/merged_prs_ingest.py) | Brain APScheduler | `SCHEDULER_MERGED_PRS_HOURS` (default 6h) | Brain / Render | ✅ Live | Merged-PR memory episodes from GitHub | `GITHUB_TOKEN` | — |
| [ingest_decisions_daily](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/ingest_decisions_cadence.py) | Brain APScheduler | `0 3 * * *` daily 03:00 UTC | Brain / Render | ✅ Live | ADR / decision docs → memory | — | — |
| [ingest_postmortems_daily](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/ingest_postmortems_cadence.py) | Brain APScheduler | `30 3 * * *` daily 03:30 UTC | Brain / Render | ✅ Live | Postmortems + incidents → memory | — | — |
| [brain_daily_briefing](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/brain_daily_briefing.py) | Brain APScheduler | `0 7 * * *` UTC | Brain / Render | ✅ Live when `BRAIN_SCHEDULER_ENABLED` | Daily briefing via `agent.process` | — | [Architecture](/admin/architecture) |
| [brain_weekly_briefing](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/brain_weekly_briefing.py) | Brain APScheduler | `0 18 * * 0` UTC | Brain / Render | ✅ Live | Sunday weekly to `#all-paperwork-labs` | — | [Architecture](/admin/architecture) |
| [brain_weekly_strategy](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/weekly_strategy.py) | Brain APScheduler | `0 9 * * 1` UTC Mon | Brain / Render | ✅ Live | Monday strategy check-in | — | [Architecture](/admin/architecture) |
| [brain_sprint_kickoff](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_kickoff.py) | Brain APScheduler | `0 7 * * 1` UTC Mon | Brain / Render | ✅ Live | Sprint kickoff to `#sprints` + `#all-paperwork-labs` | — | [Architecture](/admin/architecture) |
| [brain_sprint_close](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_close.py) | Brain APScheduler | `0 21 * * 5` UTC | Brain / Render | ✅ Live | Friday sprint close + `KNOWLEDGE.md` append | — | [Architecture](/admin/architecture) |
| [sprint_auto_logger](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_auto_logger.py) | Brain APScheduler | `*/15 * * * *` UTC | Brain / Render | 🟡 Gated (default `false`) | Bot PRs to log merged sprint PRs in `docs/sprints` | `BRAIN_OWNS_SPRINT_AUTO_LOGGER` | [Sprints](/admin/sprints) |
| [brain_sprint_planner](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_planner.py) | Brain APScheduler | `0 14 * * 1` **America/Los_Angeles** Mon | Brain / Render | 🟡 Gated (default `false`) | Weekly planning prompt → `#strategy` (+ optional `KNOWLEDGE.md` append) | `BRAIN_OWNS_SPRINT_PLANNER` | [Automation](/admin/automation) |
| [brain_infra_heartbeat](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/infra_heartbeat.py) | Brain APScheduler | `0 8 * * *` UTC | Brain / Render | ✅ Live | n8n-shaped infra heartbeat to Slack | — | [Architecture](/admin/architecture) |
| [brain_credential_expiry](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/credential_expiry.py) | Brain APScheduler | `0 8 * * *` UTC | Brain / Render | ✅ Live | Vault / expiry report to `#alerts` | — | [Architecture](/admin/architecture) |
| [brain_infra_health](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/infra_health.py) | Brain APScheduler | 30m `IntervalTrigger` | Brain / Render | ✅ Live | n8n+infra fingerprint alerts | — | [Architecture](/admin/architecture) |
| [brain_data_source_monitor](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/data_source_monitor.py) | Brain APScheduler | `0 6 * * 1` America/Los_Angeles | Brain / Render | ✅ Live | External tax source hash monitor | — | [Architecture](/admin/architecture) |
| [brain_data_deep_validator](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/data_deep_validator.py) | Brain APScheduler | `0 3 1 * *` America/Los_Angeles | Brain / Render | ✅ Live | Monthly sampled DOR vs repo check | — | [Architecture](/admin/architecture) |
| [brain_data_annual_update](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/data_annual_update.py) | Brain APScheduler | `0 9 1 10 *` America/Los_Angeles | Brain / Render | ✅ Live | October annual data checklist | — | [Architecture](/admin/architecture) |
| n8n `n8n_shadow_*` family | _(removed)_ | — | — | ⚫ Retired | APScheduler mirror module deleted (`chore/brain-delete-legacy-owns-flags`); admin endpoint returns `retired: true` | — | [n8n mirror](/admin/n8n-mirror) |
| [auto-merge-sweep](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/auto-merge-sweep.yaml) | GitHub Actions | `*/30 * * * *` UTC | GitHub | ✅ Live (legacy path) | Dependabot / merge sweeps in Actions | Replaced in intent by in-process `pr_sweep` | — |
| [auto-merge](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/auto-merge.yaml) | GitHub Actions | on review + check_suite | GitHub | ✅ Live | Merge approved PRs | — | — |
| [brain-golden-suite](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/brain-golden-suite.yaml) | GitHub Actions | `15 6 * * *` nightly UTC | GitHub | ✅ Live | Nightly golden suite | — | — |
| [docs-freshness](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/docs-freshness.yaml) | GitHub Actions | `0 14 * * 1` Mon 14:00 UTC | GitHub | ✅ Live | `last_reviewed` freshness (warn) | — | [Docs](/admin/docs) |
| [docs-index](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/docs-index.yaml) | GitHub Actions | on push/PR to docs | GitHub | ✅ Live | Drift on `docs/_index.yaml` | — | [Docs](/admin/docs) |
| [runbook-template](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/runbook-template.yaml) | GitHub Actions | `0 14 * * 1` | GitHub | ✅ Live | Runbook section checks (warn) | — | [Docs](/admin/docs) |
| [infra-health](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/infra-health.yaml) | GitHub Actions | `0 */6 * * *` | GitHub | ✅ Live | n8n + webhook smoke | — | [Infrastructure](/admin/infrastructure) |
| [tracker-index](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/tracker-index.yaml) | GitHub Actions | on push/PR | GitHub | ✅ Live | Tracker JSON ↔ sprints / tasks | — | [Sprints](/admin/sprints) |
| [system-graph](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/system-graph.yaml) | GitHub Actions | on push/PR | GitHub | ✅ Live | `system-graph.json` drift | — | [Architecture](/admin/architecture) |
| [sprint-lessons-ingest](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/sprint-lessons-ingest.yaml) | GitHub Actions | push `docs/sprints` | GitHub | ✅ Live | Triggers immediate Brain lesson ingest | — | — |
| [deploy-n8n](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/deploy-n8n.yaml) | GitHub Actions | on push to workflow JSON / manual | GitHub / Hetzner | ✅ Live | Deploy workflow JSON to n8n host | — | [Workflows](/admin/workflows) |
| [vercel-promote-on-merge](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/vercel-promote-on-merge.yaml) | GitHub Actions | on PR closed to `main` + manual | GitHub + Vercel | ✅ Live | Promote READY preview to production | `VERCEL_API_TOKEN` / `VERCEL_TOKEN` | — |
| [ci](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/ci.yaml) + [persona-vocab](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/persona-vocab.yaml) + [medallion-lint](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/medallion-lint.yaml) + [brain-personas-doc](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/brain-personas-doc.yaml) + [axiomfolio-ci](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/axiomfolio-ci.yml) | GitHub Actions | on push/PR paths | GitHub | ✅ Live | CI matrix / quality gates | — | — |

**Tally:** Prefer the Status column over this line — it drifts. Ex-n8n Brain crons are ✅ **live** when `BRAIN_SCHEDULER_ENABLED`. Optional 🟡 rows still use `BRAIN_OWNS_SPRINT_AUTO_LOGGER`, `BRAIN_OWNS_SPRINT_PLANNER`, `BRAIN_OWNS_AGENT_SPRINT_SCHEDULER`, or `BRAIN_OWNS_PR_TRIAGE`. The n8n shadow mirror family is ⚫ **retired** (module removed).

**Notes:** Vercel **preview/production builds** and Render **deploy hooks** are not cron schedules; they appear under each platform’s dashboard. Retired n8n workflow JSON lives under `infra/hetzner/workflows/retired/`. Track J/K reference: [SSO + convergence plan (`.cursor/plans`)](https://github.com/paperwork-labs/paperwork) — `sso_customer_unification_2026q2` (*founder’s local plan file, not in repo root*).

## Related

- [BRAIN_SCHEDULER.md](BRAIN_SCHEDULER.md) — env vars, SQLAlchemy job store, retired mirror
- [STREAMLINE_SSO_DAGS_2026Q2.md](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md) — sprint T1 / Track K
- [RENDER_INVENTORY](RENDER_INVENTORY.md) — where `brain-api` runs
