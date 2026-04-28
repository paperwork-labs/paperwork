# n8n Agent Workflows — Paperwork Labs

AI agent workflows run on the Hetzner VPS at `n8n.paperworklabs.com`.

**Architecture: n8n is a dumb shuttle.** Workflows forward events to the **Brain API** (`POST /api/v1/brain/process` on `brain.paperworklabs.com`) and post responses to Slack (or other channels). Prompting, personas, doc fetch, and PR diff review live in Brain—not in n8n.

- **Slack**: Event Subscriptions → Brain Slack Adapter webhook → thread fetch → Brain → `chat.postMessage`
- **Scheduled ops**: Cron schedules for sprint kickoff/close, data pipelines, infra checks, briefings, and related jobs run in **Brain APScheduler** (`apis/brain/app/schedulers/pr_sweep.py` → `start_scheduler`). Historical n8n JSON mirrors live under [retired/](retired/) — see [retired/RETIRED.md](retired/RETIRED.md).
- **PR summaries (legacy n8n path)**: Retired — Brain runs in-process `pr_sweep` + PR review; see [retired/brain-pr-summary.json](retired/brain-pr-summary.json).
- **Decision logging**: Separate deterministic workflow (GitHub commit to `KNOWLEDGE.md`) via `decision-logger.json`
- **Observability**: 5-layer stack below still applies

## Retired workflows (schedule superseded — not in deploy glob)

Exports under **`retired/`** are historical only (`scripts/deploy-n8n-workflows.sh` copies only top-level `*.json`). Full mapping (**n8n JSON → Brain job id / module**): [retired/RETIRED.md](retired/RETIRED.md).

| Retired JSON | Brain replacement (APScheduler job `id`) |
| --- | --- |
| `sprint-kickoff.json` | `brain_sprint_kickoff` (`sprint_kickoff.py`) |
| `sprint-close.json` | `brain_sprint_close` (`sprint_close.py`) |
| `data-annual-update.json` | `brain_data_annual_update` (`data_annual_update.py`) |
| `data-deep-validator.json` | `brain_data_deep_validator` (`data_deep_validator.py`) |
| `data-source-monitor.json` | `brain_data_source_monitor` (`data_source_monitor.py`) |

*(Plus briefing, infra, credentials, weekly strategy, and PR-summary mirrors — see RETIRED.md.)*

## Active workflows (authoritative for n8n — `*.json` in this directory root)

Still deployed from this folder and executed by n8n when active (Slack inbound, webhooks, or supporting flows):

| Workflow | File | Trigger |
| --- | --- | --- |
| Brain Slack Adapter | `brain-slack-adapter.json` | Webhook `brain-slack` |
| Decision Logger | `decision-logger.json` | Webhook `slack-decisions` |
| Social Content Generator | `social-content-generator.json` | POST `/social-content` |
| Growth Content Writer | `growth-content-writer.json` | POST `/growth-content` |
| QA Security Scan | `qa-security-scan.json` | POST `/qa-scan` (Track H: Brain `persona_pin=qa`, 2-node) |
| CPA Tax Review | `cpa-tax-review.json` | POST `/cpa-review` (Track H: Brain `persona_pin=cpa`, 2-node) |
| Partnership Outreach Drafter | `partnership-outreach-drafter.json` | POST `/partnership-outreach` |
| Infra Status / errors | `infra-status-slash.json`, `error-notification.json` | Slash / ancillary |

Cron times that mirror PT in legacy docs assume `GENERIC_TIMEZONE=America/Los_Angeles` in n8n when applicable.

### Active — no Brain APScheduler replacement (by design)

These are **webhook- or slash-driven** helpers. There is no one-to-one scheduled Brain job for each file; overlapping **cron** work (weekly QA digest, sprint cadence, data ops, infra) runs under Brain APScheduler as listed in [retired/RETIRED.md](retired/RETIRED.md) and `start_scheduler()` in `apis/brain/app/schedulers/pr_sweep.py` instead of duplicated n8n schedules.

### Deprecated / legacy (do not use for new installs)

| File | Replacement | Notes |
|------|-------------|--------|
| `agent-thread-handler.json` | `brain-slack-adapter.json` + Brain | Removed from core architecture; do not point new Slack subscriptions at `slack-events`. |
| `ea-daily.json` | Brain APScheduler `brain_daily_briefing` | Export in `archive/` / `retired/brain-daily-trigger.json`. |
| `ea-weekly.json` | Brain APScheduler `brain_weekly_briefing` | Same; export in `retired/brain-weekly-trigger.json`. |
| `pr-summary.json` / `brain-pr-summary.json` | Brain in-process PR sweep + review | Export in `retired/brain-pr-summary.json`. |

Other archived JSON under `archive/` remains for reference but is **not** part of the core shuttle + Brain model.

### Track H — 2-node Brain pattern (wave 1)

Wave 1 migrated `cpa-tax-review` and `qa-security-scan`
from the old "Webhook → GPT-4o → Format → Slack" 4–5 node pattern to a
thin 2-node shape:

1. **Webhook / Schedule** — triggers only, no prompt building.
2. **HTTP Request → Brain** — single call to `/api/v1/brain/process`
   with `persona_pin` (cpa/qa/strategy) and `slack_channel_id` set.
   Brain routes through the PersonaSpec (Sonnet for compliance/security
   work), stamps a `brain://episode/...` URI, and posts the response
   directly to Slack.

The old multi-node JSON is archived under
`infra/hetzner/workflows/archive/track-h-pre/` for reference. Add
further workflows to this pattern when they're purely Webhook → LLM →
Slack.

**Sprint kickoff / close**: scheduled runs are Brain-only (`brain_sprint_kickoff`,
`brain_sprint_close`). Historical n8n exports live in `retired/sprint-kickoff.json` and
`retired/sprint-close.json`.

## Observability Architecture (5 Layers)

Infrastructure monitoring uses 5 layers. Each catches what the layer above might miss.

| Layer | What | Runs On | Frequency | Alert Channel |
|---|---|---|---|---|
| 0: Native Integrations | GitHub for Slack, Vercel for Slack, Google Drive for Slack | Third-party (GitHub, Vercel, Google) | Real-time | #engineering |
| 1: Deploy Verification | Post-deploy active count + liveness check | deploy-n8n.yaml / deploy script | On deploy | #alerts (failure) / incoming webhook |
| 2: n8n Self-Health | Workflow count, liveness, dedup alerts | Brain `brain_infra_health` (replaces `retired/infra-health-check.json`) | Every 30 min | #alerts via Slack Bot Token |
| 3: External Canary | Ping n8n, check webhook deliveries | infra-health.yaml (GitHub Action) | Every 6 hours | #alerts via incoming webhook |
| 4: Daily Briefing | Infra health surfaced by Brain-driven briefing | Brain `brain_daily_briefing` (replaces `retired/brain-daily-trigger.json`) | 7am PT daily | #daily-briefing |

**Layer 0 setup** (one-time, in Slack):
- GitHub for Slack: `/github subscribe paperwork-labs/paperwork` in `#engineering`
- Vercel for Slack: Install from vercel.com/integrations/slack, configure for all apps
- Google Drive for Slack: Already installed (doc previews auto-unfurl)

## Credential Setup

**Brain shuttle workflows** use container env vars (not n8n UI credentials) for Brain and Slack:

- `BRAIN_API_URL` — Base URL (default `https://brain.paperworklabs.com` if unset).
- `BRAIN_API_SECRET` — Sent as header `X-Brain-Secret` on `POST .../api/v1/brain/process`.
- `SLACK_BOT_TOKEN` — `Bearer` token for `chat.postMessage` and Slack API nodes.
- `BRAIN_WEBHOOK_SECRET` — Optional; Brain Slack Adapter verifies `x-brain-webhook-secret` when set.

Go to `n8n.paperworklabs.com` > Settings > Credentials and add (for **legacy OpenAI-in-n8n** workflows only):

1. **OpenAI** — API key from platform.openai.com/api-keys.
2. **Slack Bot Token** — Header Auth: `Authorization` = `Bearer xoxb-...` (if a workflow uses credentials instead of `$env.SLACK_BOT_TOKEN`).
3. **GitHub PAT** — Header Auth: `Authorization` = `token ghp_...` for workflows that call GitHub from n8n.

After adding credentials, open each legacy workflow in the n8n editor, attach credentials on OpenAI / HTTP Request nodes, save, and activate.

## Deploying Updates

Use the deploy script (recommended; imports, publishes, verifies, and notifies):

```bash
./scripts/deploy-n8n-workflows.sh
```

Or with a custom host:

```bash
./scripts/deploy-n8n-workflows.sh root@your-server.example.com
```

The script runs: import → `publish:workflow` → restart n8n → verify all workflows are active → post result to Slack. If verification fails (not all workflows active), the script exits non-zero and posts a failure alert to `#alerts`.

**Manual deploy** (if you need to run steps separately): Copy JSON files, import via `n8n import:workflow`, publish via `n8n publish:workflow --id=<id>`, then restart the n8n container. Verify with `n8n list:workflow --active=true`.

**Note**: `n8n update:workflow` is deprecated in n8n 2.11+. Use `n8n publish:workflow --id=<id>` instead.

### Inactive workflows (Infra Health Check: “N/M active”)

The **Infra Health Check** workflow compares n8n’s REST API `active` flag on every workflow. If any workflow is inactive, it posts to `#alerts` with the names.

**Common reasons**

- Someone toggled a workflow off in the n8n UI while debugging (credentials, Slack duplicates, cost).
- **Brain Slack Adapter** is high-impact: if misconfigured it can spam threads or overload Brain, so it is sometimes left off until `BRAIN_API_SECRET` and Slack tokens are verified.
- **CPA Tax Review** is on-demand (POST webhook); it may be disabled when not in use.
- After `import:workflow`, duplicate workflow rows can appear; older copies may stay inactive while the new copy is active.

**Re-enable (API — from a machine with vault / env)**

The script auto-loads `N8N_HOST` or `N8N_API_URL` + `N8N_API_KEY` from repo-root `.env.local`, then `apps/studio/.env.local` if still missing (e.g. after `make env-pull` / Vercel sync).

```bash
make n8n-activate-inactive
```

Or manually:

```bash
export N8N_HOST="https://n8n.paperworklabs.com"
export N8N_API_KEY="..."   # same key used by Studio / n8n Settings → API
chmod +x scripts/n8n-activate-workflows.sh
./scripts/n8n-activate-workflows.sh "Brain Slack Adapter" "CPA Tax Review"
```

If the API returns **401**, regenerate the key in n8n **Settings → API** and update `apps/studio/.env.local` (or root `.env.local`).

Or run a full deploy (activates everything the CLI can publish): `./scripts/deploy-n8n-workflows.sh`.

If a **webhook** workflow still fails after API activate, open it in the n8n editor, **Save**, and toggle **Active** once so webhooks register (known n8n quirk in some versions).

## Daily Briefing Troubleshooting

If the 7am PT daily briefing did not post to #daily-briefing:

1. **Workflow inactive**: Check with `n8n list:workflow --active=true`. If inactive, run `./scripts/deploy-n8n-workflows.sh` for a full deploy.
2. **Brain API**: Confirm `BRAIN_API_SECRET` matches Brain service config; check Brain logs for `POST /api/v1/brain/process` errors or timeouts (workflow HTTP timeout is 120s).
3. **Slack**: Confirm `SLACK_BOT_TOKEN` is set in the n8n container and the bot is in `#daily-briefing`.
4. **Cron timezone**: Ensure `GENERIC_TIMEZONE=America/Los_Angeles` in the n8n environment.
5. **Execution history**: In n8n, check Executions for **Brain Daily Trigger** to see if it ran and whether Brain or Slack failed.

## Slack Event Subscriptions

Slack Event Subscriptions should use the **Brain Slack Adapter** webhook (path `brain-slack`). Copy the **Production URL** from that workflow’s Webhook node in n8n (often `https://n8n.paperworklabs.com/webhook/brain-slack`; exact path depends on n8n version).

**Decision Logger** (`decision-logger.json`, path `slack-decisions`) is a separate webhook. Slack allows only one Events Request URL per app—if both must receive events, use a second Slack app, an edge proxy that fans out, or trigger Decision Logger from Brain / another integration.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and select your Paperwork Labs app.
2. Navigate to **Event Subscriptions** and toggle "Enable Events" on.
3. Set the **Request URL** to the Brain Slack Adapter production webhook URL (see above—not the legacy `slack-events` path).
4. Under **Subscribe to bot events**, add:
   - `message.channels` — messages in public channels
   - `message.groups` — messages in private channels
   - `message.im` — direct messages to the bot
   - `message.mpim` — group DMs with the bot
   - `app_mention` — @mentions of the bot
5. Click **Save Changes**.
6. Ensure the bot is invited to all channels where it should listen (`#decisions`, `#daily-briefing`, `#engineering`, `#all-paperwork-labs`, `#general`, `#alerts`).

**Note:** `reaction_added` and emoji-merge automation previously lived in `agent-thread-handler.json`, which is **deprecated**. Reintroduce merge-on-reaction via Brain when product-ready.

## GitHub webhooks (PR summaries)

**Retired n8n path:** `retired/brain-pr-summary.json` (webhook `github-pr-brain`). PR review and sweep run in **Brain** (`pr_sweep` on `brain-api`); do not point new GitHub webhooks at n8n for this. Remove or disable the old n8n workflow in the Hetzner UI if it is still active.

## Slack reaction merge (deprecated)

Emoji-driven merge / Copilot re-review flows previously ran in **`agent-thread-handler.json`**, which is **deprecated** in favor of Brain. Do not rely on n8n for reaction-based merges until an equivalent Brain tool or workflow exists. Use GitHub’s UI or `gh` CLI for merges in the interim.

## Model configuration

**Brain core (1–4):** Models and prompts are configured in the **Brain** service, not in n8n.

**Legacy / optional n8n OpenAI workflows:** OpenAI nodes use the model dropdown in the n8n UI.

| Workflow | Typical model | Env var (if used) | Notes |
|---|---|---|---|
| brain-slack-adapter | N/A | N/A | Brain API |
| _(retired)_ sprint-kickoff / sprint-close | N/A | — | **Brain cron** — mirrors in `retired/` |
| social-content-generator | gpt-4o | SOCIAL_CONTENT_MODEL | Optional |
| growth-content-writer | gpt-4o | GROWTH_CONTENT_MODEL | Optional |
| partnership-outreach-drafter | gpt-4o | PARTNERSHIP_MODEL | Optional |
| cpa-tax-review | gpt-4o | CPA_REVIEW_MODEL | Optional |
| qa-security-scan | gpt-4o | QA_SCAN_MODEL | Optional |
| decision-logger | N/A | N/A | Deterministic |
| _(retired)_ infra-health-check | N/A | N/A | Was deterministic; see `retired/` |

### Required n8n environment variables

| Variable | Purpose | Required by |
|---|---|---|
| `BRAIN_API_SECRET` | Authenticates n8n → Brain (`X-Brain-Secret`) | Brain shuttle workflows |
| `BRAIN_API_URL` | Brain base URL (optional; defaults in JSON) | Brain shuttle workflows |
| `SLACK_BOT_TOKEN` | Slack `chat.postMessage` / API | Brain shuttle workflows, Brain `brain_infra_health` |
| `BRAIN_WEBHOOK_SECRET` | Verifies inbound Slack → n8n (adapter) | brain-slack-adapter (optional) |
| `GITHUB_TOKEN` | GitHub API (legacy n8n workflows, merges, doc fetch) | sprint/legacy workflows, scripts |
| `SLACK_ALERTS_WEBHOOK_URL` | Incoming webhook for #alerts | deploy scripts, compose |

Set these in the Hetzner `.env` file and in `infra/hetzner/compose.yaml` environment block.

### Changing Models

Edit the workflow in the n8n UI, select the OpenAI node, and change the model dropdown.

**Note:** CPA Tax Review and QA Security Scan are candidates for Claude migration when Anthropic API access is set up. See AI_MODEL_REGISTRY.md for the activation roadmap.

## Security Notes

- Slack signature verification and timestamp replay protection are required for production hardening (Brain Slack Adapter uses optional shared secret `BRAIN_WEBHOOK_SECRET` on inbound requests).
- If you still run legacy GitHub → n8n webhooks, enforce signature verification (`X-Hub-Signature-256`); the PR-summary path in `retired/` should not be used for new installs.
- Current workflows run in a trusted internal environment; add these checks before wider exposure.

## Sprint Operations

- Sprint execution is agent-first in `#sprints`.
- Monday kickoff and Friday close are generated and posted by **Brain APScheduler** (`brain_sprint_kickoff` / `brain_sprint_close`); n8n mirrors are archived under `retired/`.
- Updates, blockers, and decisions should be posted as thread replies under the kickoff post.
