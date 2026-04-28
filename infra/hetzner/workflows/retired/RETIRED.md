# Retired n8n Workflows

These workflows have been replaced by Brain APScheduler jobs (or, for the PR-summary webhook, by in-process PR review on the same Brain service).

They are kept here for historical reference only and are **not** loaded by n8n from the main deploy glob (`infra/hetzner/workflows/*.json` — see [deploy-n8n workflow](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/deploy-n8n.yaml)).

| Retired workflow | Brain replacement | Notes | PR |
| --- | --- | --- | --- |
| `brain-daily-trigger.json` | `apis/brain/app/schedulers/brain_daily_briefing.py` (`brain_daily_briefing`) | Brain-first when `BRAIN_SCHEDULER_ENABLED` (cutover flags retired) | [#160](https://github.com/paperwork-labs/paperwork/pull/160) |
| `brain-weekly-trigger.json` | `apis/brain/app/schedulers/brain_weekly_briefing.py` (`brain_weekly_briefing`) | _(same)_ | [#199](https://github.com/paperwork-labs/paperwork/pull/199) |
| `weekly-strategy-checkin.json` | `apis/brain/app/schedulers/weekly_strategy.py` (`brain_weekly_strategy`) | _(same)_ | [#200](https://github.com/paperwork-labs/paperwork/pull/200) |
| `infra-heartbeat.json` | `apis/brain/app/schedulers/infra_heartbeat.py` (`brain_infra_heartbeat`) | _(same)_ | [#166](https://github.com/paperwork-labs/paperwork/pull/166) |
| `credential-expiry-check.json` | `apis/brain/app/schedulers/credential_expiry.py` (`brain_credential_expiry`) | _(same)_ | [#170](https://github.com/paperwork-labs/paperwork/pull/170) |
| `infra-health-check.json` | `apis/brain/app/schedulers/infra_health.py` (`brain_infra_health`) | _(same)_ | [#201](https://github.com/paperwork-labs/paperwork/pull/201) |
| `brain-pr-summary.json` | `apis/brain/app/schedulers/pr_sweep.py` (`pr_sweep`) + `sweep_open_prs` / PR review (not an n8n **mirror** row) | — (see [#131](https://github.com/paperwork-labs/paperwork/pull/131)) | [#131](https://github.com/paperwork-labs/paperwork/pull/131) |
| `data-annual-update.json` | `apis/brain/app/schedulers/data_annual_update.py` (`brain_data_annual_update`) | Annual October checklist → `#engineering` | WS-23-trackf1-n8n-retire |
| `data-deep-validator.json` | `apis/brain/app/schedulers/data_deep_validator.py` (`brain_data_deep_validator`) | Monthly DOR/sample validation digest → Slack | WS-23-trackf1-n8n-retire |
| `data-source-monitor.json` | `apis/brain/app/schedulers/data_source_monitor.py` (`brain_data_source_monitor`) | Weekly external source hash monitor → Slack | WS-23-trackf1-n8n-retire |
| `decision-logger.json` | _(none — WS-19)_ | Slack Events webhook flow; replacement is a future Brain HTTP handler, not APScheduler. | WS-19 |
| `growth-content-writer.json` | `apis/brain/app/schedulers/growth_content_writer.py` (`growth_content_writer`) | Weekly cron (export was webhook-only). | WS-19 |
| `qa-security-scan.json` | `apis/brain/app/schedulers/qa_security_scan.py` (`qa_security_scan`) | Weekly Brain `persona_pin=qa` (export was webhook-only). | WS-19 |
| `social-content-generator.json` | `apis/brain/app/schedulers/social_content_generator.py` (`social_content_generator`) | Weekly cron (export was webhook-only). | WS-19 |
| `sprint-close.json` | `apis/brain/app/schedulers/sprint_close.py` (`brain_sprint_close`) | Fri 21:00 UTC cron; Brain posts + KNOWLEDGE.md append | WS-23-trackf1-n8n-retire |
| `sprint-kickoff.json` | `apis/brain/app/schedulers/sprint_kickoff.py` (`brain_sprint_kickoff`) | Mon 07:00 UTC cron; Brain posts `#sprints` + `#all-paperwork-labs` | WS-23-trackf1-n8n-retire |

## Follow-up

- **Founder / ops:** keep retired workflows disabled in the n8n UI on Hetzner so they do not double-fire with Brain.

## How to fully delete

Once all replacements have run for 30 days without incident:

1. Disable the workflow in the n8n UI (founder action).
2. Delete the JSON and this row via `git rm` (or remove the `brain-pr-summary` GitHub webhook if that workflow is the only consumer).
