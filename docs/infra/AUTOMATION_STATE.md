---
owner: infra-ops
last_reviewed: 2026-04-26
doc_kind: runbook
domain: infra
status: active
---

# Automation state (single source of truth)

> **How to read this page:** every scheduled or event-driven automation in the monorepo is listed with **one owner** (where you flip a switch) and a **status** that reflects defaults in code today. `BRAIN_OWNS_*` flags default to **false** in production until the founder sets them in Render `brain-api`.

## Founder action: flip these flags (recommended order)

1. **Foundation (low-risk monitoring):** `BRAIN_OWNS_INFRA_HEARTBEAT`, `BRAIN_OWNS_INFRA_HEALTH`, `BRAIN_OWNS_CREDENTIAL_EXPIRY`
2. **Reporting (notification-only):** `BRAIN_OWNS_DAILY_BRIEFING`, `BRAIN_OWNS_BRAIN_WEEKLY`, `BRAIN_OWNS_WEEKLY_STRATEGY`
3. **Decision-making:** `BRAIN_OWNS_SPRINT_KICKOFF`, `BRAIN_OWNS_SPRINT_CLOSE` (when Brain job exists), `BRAIN_OWNS_SPRINT_AUTO_LOGGER`, `BRAIN_OWNS_SPRINT_PLANNER`
4. **Heavy lifters (gated until quality verified):** rely on in-process `cfo_friday_digest`, `qa_weekly_report` (no extra env flag; watch Slack quality first), then expand.

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
| [brain_daily_briefing](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/brain_daily_briefing.py) | Brain APScheduler | `0 7 * * *` UTC | Brain / Render | 🟡 Gated (default `false`) | Daily briefing via `agent.process` | `BRAIN_OWNS_DAILY_BRIEFING` | [n8n mirror](/admin/n8n-mirror) |
| [brain_weekly_briefing](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/brain_weekly_briefing.py) | Brain APScheduler | `0 18 * * 0` UTC | Brain / Render | 🟡 Gated (default `false`) | Sunday weekly to `#all-paperwork-labs` | `BRAIN_OWNS_BRAIN_WEEKLY` | [n8n mirror](/admin/n8n-mirror) |
| [brain_weekly_strategy](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/weekly_strategy.py) | Brain APScheduler | `0 9 * * 1` UTC Mon | Brain / Render | 🟡 Gated (default `false`) | Monday strategy check-in | `BRAIN_OWNS_WEEKLY_STRATEGY` | [n8n mirror](/admin/n8n-mirror) |
| [brain_sprint_kickoff](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_kickoff.py) | Brain APScheduler | `0 7 * * 1` UTC Mon | Brain / Render | 🟡 Gated (default `false`) | Sprint kickoff to `#sprints` + `#all-paperwork-labs` | `BRAIN_OWNS_SPRINT_KICKOFF` | [n8n mirror](/admin/n8n-mirror) |
| [Sprint Close (n8n)](https://github.com/paperwork-labs/paperwork/blob/main/infra/hetzner/workflows/) | n8n production cron | `0 21 * * 5` UTC (n8n) | n8n / Hetzner | 🔴 Brain cutover TBD (no first-party job yet) | Friday sprint close; mirror only in Brain | Future `BRAIN_OWNS_SPRINT_CLOSE` (Track K) | [Architecture](/admin/architecture) |
| [sprint_auto_logger](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_auto_logger.py) | Brain APScheduler | `*/15 * * * *` UTC | Brain / Render | 🟡 Gated (default `false`) | Bot PRs to log merged sprint PRs in `docs/sprints` | `BRAIN_OWNS_SPRINT_AUTO_LOGGER` | [Sprints](/admin/sprints) |
| [brain_sprint_planner](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/sprint_planner.py) | Brain APScheduler | `0 14 * * 1` **America/Los_Angeles** Mon | Brain / Render | 🟡 Gated (default `false`) | Weekly planning prompt → `#strategy` (+ optional `KNOWLEDGE.md` append) | `BRAIN_OWNS_SPRINT_PLANNER` | [Automation](/admin/automation) |
| [brain_infra_heartbeat](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/infra_heartbeat.py) | Brain APScheduler | `0 8 * * *` UTC | Brain / Render | 🟡 Gated (default `false`) | n8n-shaped infra heartbeat to Slack | `BRAIN_OWNS_INFRA_HEARTBEAT` | [n8n mirror](/admin/n8n-mirror) |
| [brain_credential_expiry](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/credential_expiry.py) | Brain APScheduler | `0 8 * * *` UTC | Brain / Render | 🟡 Gated (default `false`) | Vault / expiry report to `#alerts` | `BRAIN_OWNS_CREDENTIAL_EXPIRY` | [n8n mirror](/admin/n8n-mirror) |
| [brain_infra_health](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/infra_health.py) | Brain APScheduler | 30m `IntervalTrigger` | Brain / Render | 🟡 Gated (default `false`) | n8n+infra fingerprint alerts | `BRAIN_OWNS_INFRA_HEALTH` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_brain_daily](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow (Brain APScheduler) | `0 7 * * *` UTC | Brain / Render | 🔵 | Posts `#engineering-cron-shadow` canary; **off** unless `SCHEDULER_N8N_MIRROR_*` opt-in | `SCHEDULER_N8N_MIRROR_*`; suppressed when `BRAIN_OWNS_DAILY_BRIEFING` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_brain_weekly](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 18 * * 0` UTC | Brain / Render | 🔵 | Weekly mirror; **off** until mirror opt-in | Suppressed when `BRAIN_OWNS_BRAIN_WEEKLY` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_sprint_kickoff](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 7 * * 1` UTC | Brain / Render | 🔵 | Kickoff canary; **off** until mirror opt-in | Suppressed when `BRAIN_OWNS_SPRINT_KICKOFF` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_sprint_close](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 21 * * 5` UTC | Brain / Render | 🔵 | Close canary (no `BRAIN_OWNS_*` yet) | `SCHEDULER_N8N_MIRROR_*` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_weekly_strategy](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 9 * * 1` UTC | Brain / Render | 🔵 | Strategy mirror; **off** until mirror opt-in | Suppressed when `BRAIN_OWNS_WEEKLY_STRATEGY` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_infra_heartbeat](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 8 * * *` UTC | Brain / Render | 🔵 | Infra HB mirror; **off** until mirror opt-in | Suppressed when `BRAIN_OWNS_INFRA_HEARTBEAT` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_data_source_monitor](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 6 * * 1` UTC | Brain / Render | 🔵 | Data monitor canary (LA n8n caveat in runbook) | `SCHEDULER_N8N_MIRROR_*` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_data_deep_validator](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 3 1 * *` UTC | Brain / Render | 🔵 | Monthly data validator mirror | `SCHEDULER_N8N_MIRROR_*` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_annual_data](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 9 1 10 *` UTC | Brain / Render | 🔵 | Annual data checklist mirror | `SCHEDULER_N8N_MIRROR_*` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_infra_health](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | 30m interval | Brain / Render | 🔵 | Infra health mirror; **off** until mirror opt-in | Suppressed when `BRAIN_OWNS_INFRA_HEALTH` | [n8n mirror](/admin/n8n-mirror) |
| [n8n_shadow_credential_expiry](https://github.com/paperwork-labs/paperwork/blob/main/apis/brain/app/schedulers/n8n_mirror.py) | n8n shadow | `0 8 * * *` UTC | Brain / Render | 🔵 | Credential expiry mirror; **off** until mirror opt-in | Suppressed when `BRAIN_OWNS_CREDENTIAL_EXPIRY` | [n8n mirror](/admin/n8n-mirror) |
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

**Tally (Status column emojis, exact for this table revision):** ✅ **22** (live) · 🟡 **9** (gated `BRAIN_OWNS_*` / default-off first-party) · 🔵 **11** (n8n `n8n_shadow_*` mirror family; default-off unless mirror opt-in) · 🔴 **1** (Sprint Close: n8n live, no Brain first-party + no shadow suppression flag yet)

**Notes:** Vercel **preview/production builds** and Render **deploy hooks** are not cron schedules; they appear under each platform’s dashboard. n8n **user-facing** crons not mirrored here remain in Hetzner until cutover (see [BRAIN_SCHEDULER.md](BRAIN_SCHEDULER.md)). Track J/K reference: [SSO + convergence plan (`.cursor/plans`)](https://github.com/paperwork-labs/paperwork) — `sso_customer_unification_2026q2` (*founder’s local plan file, not in repo root*).

## Related

- [BRAIN_SCHEDULER.md](BRAIN_SCHEDULER.md) — env vars, n8n cutover, SQLAlchemy job store
- [STREAMLINE_SSO_DAGS_2026Q2.md](../sprints/STREAMLINE_SSO_DAGS_2026Q2.md) — sprint T1 / Track K
- [RENDER_INVENTORY](RENDER_INVENTORY.md) — where `brain-api` runs
