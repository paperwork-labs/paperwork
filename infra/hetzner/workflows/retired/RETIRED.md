# Retired n8n Workflows

These workflows have been replaced by Brain APScheduler jobs (or, for the PR-summary webhook, by in-process PR review on the same Brain service).

They are kept here for historical reference only and are **not** loaded by n8n from the main deploy glob (`infra/hetzner/workflows/*.json` — see [deploy-n8n workflow](https://github.com/paperwork-labs/paperwork/blob/main/.github/workflows/deploy-n8n.yaml)).

| Retired workflow | Brain replacement | Suppression flag | PR |
| --- | --- | --- | --- |
| `brain-daily-trigger.json` | `apis/brain/app/schedulers/brain_daily_briefing.py` (`brain_daily_briefing`) | `BRAIN_OWNS_DAILY_BRIEFING` | [#160](https://github.com/paperwork-labs/paperwork/pull/160) |
| `brain-weekly-trigger.json` | `apis/brain/app/schedulers/brain_weekly_briefing.py` (`brain_weekly_briefing`) | `BRAIN_OWNS_BRAIN_WEEKLY` | [#199](https://github.com/paperwork-labs/paperwork/pull/199) |
| `weekly-strategy-checkin.json` | `apis/brain/app/schedulers/weekly_strategy.py` (`brain_weekly_strategy`) | `BRAIN_OWNS_WEEKLY_STRATEGY` | [#200](https://github.com/paperwork-labs/paperwork/pull/200) |
| `infra-heartbeat.json` | `apis/brain/app/schedulers/infra_heartbeat.py` (`brain_infra_heartbeat`) | `BRAIN_OWNS_INFRA_HEARTBEAT` | [#166](https://github.com/paperwork-labs/paperwork/pull/166) |
| `credential-expiry-check.json` | `apis/brain/app/schedulers/credential_expiry.py` (`brain_credential_expiry`) | `BRAIN_OWNS_CREDENTIAL_EXPIRY` | [#170](https://github.com/paperwork-labs/paperwork/pull/170) |
| `infra-health-check.json` | `apis/brain/app/schedulers/infra_health.py` (`brain_infra_health`) | `BRAIN_OWNS_INFRA_HEALTH` | [#201](https://github.com/paperwork-labs/paperwork/pull/201) |
| `brain-pr-summary.json` | `apis/brain/app/schedulers/pr_sweep.py` (`pr_sweep`) + `sweep_open_prs` / PR review (not an n8n **mirror** row) | — (see [#131](https://github.com/paperwork-labs/paperwork/pull/131)) | [#131](https://github.com/paperwork-labs/paperwork/pull/131) |

## Follow-up: not retired in this pass

- **`sprint-kickoff.json`** — still the thin n8n schedule → Brain path; `n8n_shadow_sprint_kickoff` has no `BRAIN_OWNS_*` cutover in `n8n_mirror.py` yet. Retire when a first-party job + flag exists.
- **Founder / ops:** disable the corresponding workflows in the n8n UI on Hetzner so they do not double-fire with Brain (for mirror-cutover JSONs, after Brain `BRAIN_OWNS_*` flags are `true` in production).

## How to fully delete

Once all replacements have run for 30 days without incident:

1. Disable the workflow in the n8n UI (founder action).
2. Delete the JSON and this row via `git rm` (or remove the `brain-pr-summary` GitHub webhook if that workflow is the only consumer).
