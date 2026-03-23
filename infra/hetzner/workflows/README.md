# n8n Agent Workflows — Paperwork Labs

AI agent workflows run on the Hetzner VPS at `n8n.paperworklabs.com`.

Architecture is **Slack-first**:
- One Slack Event Subscriptions endpoint (`slack-events`) handled by `agent-thread-handler.json`
- Persona-routed thread responses in Slack
- Scheduled briefings, sprint kickoff/close, and operational alerts posted to Slack channels
- Decision logging routed from the thread handler to the decision workflow
- 5-layer observability system ensures failures are caught within minutes (see below)

## Workflows

| Workflow | File | Trigger | AI Model | Output |
|---|---|---|---|---|
| Agent Thread Handler | `agent-thread-handler.json` | Slack event (thread/mention/reaction) | GPT-4o-mini | Reply in thread / merge PR |
| EA Daily Briefing | `ea-daily.json` | Cron 7am PT | GPT-4o-mini | #daily-briefing |
| EA Weekly Plan | `ea-weekly.json` | Cron Sunday 6pm PT | GPT-4o-mini | #weekly-plan |
| PR Summary | `pr-summary.json` | GitHub webhook (PR opened) | GPT-4o-mini | #engineering |
| Decision Logger | `decision-logger.json` | Triggered by thread handler (`log this` / `decided:` in #decisions) | N/A | KNOWLEDGE.md + thread confirm |
| Social Content Generator | `social-content-generator.json` | POST /social-content | GPT-4o | #general |
| Growth Content Writer | `growth-content-writer.json` | POST /growth-content | GPT-4o | #general |
| Weekly Strategy Check-in | `weekly-strategy-checkin.json` | Cron Monday 9am | GPT-4o | #all-paperwork-labs |
| QA Security Scan | `qa-security-scan.json` | POST /qa-scan | GPT-4o | #engineering + GitHub Issue |
| Partnership Outreach | `partnership-outreach-drafter.json` | POST /partnership-outreach | GPT-4o | #general |
| CPA Tax Review | `cpa-tax-review.json` | POST /cpa-review | GPT-4o | #general |
| Sprint Kickoff | `sprint-kickoff.json` | Cron Mon 7am PT | GPT-4o | #sprints + #all-paperwork-labs |
| Sprint Close | `sprint-close.json` | Cron Fri 9pm PT | GPT-4o | #sprints + KNOWLEDGE.md |
| **Infra Health Check** | `infra-health-check.json` | Cron every 30 min | N/A | #alerts (on failure only) |

## Observability Architecture (5 Layers)

Infrastructure monitoring uses 5 layers. Each catches what the layer above might miss.

| Layer | What | Runs On | Frequency | Alert Channel |
|---|---|---|---|---|
| 0: Native Integrations | GitHub for Slack, Vercel for Slack, Google Drive for Slack | Third-party (GitHub, Vercel, Google) | Real-time | #engineering |
| 1: Deploy Verification | Post-deploy active count + liveness check | deploy-n8n.yaml / deploy script | On deploy | #alerts (failure) / incoming webhook |
| 2: n8n Self-Health | Workflow count, liveness, dedup alerts | infra-health-check.json (n8n cron) | Every 30 min | #alerts via Slack Bot Token |
| 3: External Canary | Ping n8n, check webhook deliveries | infra-health.yaml (GitHub Action) | Every 6 hours | #alerts via incoming webhook |
| 4: Daily Briefing | Infra health section in EA briefing | ea-daily.json (n8n cron) | 7am PT daily | #daily-briefing |

**Layer 0 setup** (one-time, in Slack):
- GitHub for Slack: `/github subscribe paperwork-labs/paperwork` in `#engineering`
- Vercel for Slack: Install from vercel.com/integrations/slack, configure for all apps
- Google Drive for Slack: Already installed (doc previews auto-unfurl)

## Credential Setup

Go to `n8n.paperworklabs.com` > Settings > Credentials and add:

1. **OpenAI** — API key from platform.openai.com/api-keys.
2. **Slack Bot Token** — Create as a "Header Auth" credential with header name `Authorization` and value `Bearer xoxb-...` (the Bot User OAuth Token from api.slack.com > Your App > OAuth & Permissions).
3. **GitHub PAT** — Create as a "Header Auth" credential with header name `Authorization` and value `token ghp_...` (personal access token with `repo` scope from github.com/settings/tokens).

After adding credentials, open each workflow in the n8n editor, select the correct credential on every OpenAI / HTTP Request node, save, and activate.

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

### Inactive workflows (Infra Health Check: “14/16 active”)

The **Infra Health Check** workflow compares n8n’s REST API `active` flag on every workflow. If any workflow is inactive, it posts to `#alerts` with the names.

**Common reasons**

- Someone toggled a workflow off in the n8n UI while debugging (credentials, Slack duplicates, cost).
- **Agent Thread Handler** is high-impact: if misconfigured it can spam threads or hit OpenAI repeatedly, so it is sometimes left off until credentials are verified.
- **CPA Tax Review** is on-demand (POST webhook); it may be disabled when not in use.
- After `import:workflow`, duplicate workflow rows can appear; older copies may stay inactive while the new copy is active.

**Re-enable (API — from a machine with vault / env)**

```bash
export N8N_HOST="https://n8n.paperworklabs.com"
export N8N_API_KEY="..."   # same key used by Studio / n8n Settings → API
chmod +x scripts/n8n-activate-workflows.sh
./scripts/n8n-activate-workflows.sh "Agent Thread Handler" "CPA Tax Review"
```

Or run a full deploy (activates everything the CLI can publish): `./scripts/deploy-n8n-workflows.sh`.

If a **webhook** workflow still fails after API activate, open it in the n8n editor, **Save**, and toggle **Active** once so webhooks register (known n8n quirk in some versions).

## Daily Briefing Troubleshooting

If the 7am PT daily briefing did not post to #daily-briefing:

1. **Workflow inactive**: Check with `n8n list:workflow --active=true`. If inactive, run `./scripts/deploy-n8n-workflows.sh` for a full deploy.
2. **OpenAI quota**: The briefing uses GPT-4o-mini. If OpenAI returns "insufficient_quota", top up billing at platform.openai.com.
3. **Cron timezone**: Ensure `GENERIC_TIMEZONE=America/Los_Angeles` in the n8n environment.
4. **Execution history**: In n8n, check Executions for "EA Daily Briefing" to see if it ran and whether it failed.

## Slack Event Subscriptions

Slack Event Subscriptions must point to a **single** request URL (thread handler webhook):

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and select your Paperwork Labs app.
2. Navigate to **Event Subscriptions** and toggle "Enable Events" on.
3. Set the **Request URL** to:
   `https://n8n.paperworklabs.com/webhook/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d/webhook/slack-events`
4. Under **Subscribe to bot events**, add:
   - `message.channels` — messages in public channels
   - `message.groups` — messages in private channels
   - `message.im` — direct messages to the bot
   - `message.mpim` — group DMs with the bot
   - `app_mention` — @mentions of the bot
   - `reaction_added` — emoji reactions (powers the Slack reaction merge flow)
5. Click **Save Changes**.
6. Ensure the bot is invited to all channels where it should listen (`#decisions`, `#daily-briefing`, `#engineering`, `#all-paperwork-labs`, `#general`, `#alerts`).

## Slack Reaction Merge

React to a **PR Summary** message in `#engineering` with an emoji to trigger actions:

| Emoji | Action | Details |
|---|---|---|
| :white_check_mark: | Squash merge | CI must be green; posts confirmation or blocker list |
| :rocket: | Squash merge (alt) | Same as checkmark |
| :eyes: | Request Copilot re-review | Posts confirmation or failure reason in thread |
| :no_entry_sign: | Hold merge | Posts "merge held by founder" in thread |

**Flow**: Reaction → `agent-thread-handler.json` extracts PR number → checks CI status → merges or posts blockers.

**Requirements**: `GITHUB_TOKEN` and `SLACK_BOT_TOKEN` must be set in the n8n environment.

## Model Configuration

n8n OpenAI nodes use a dropdown for model selection. Model choices are configured per workflow in the n8n UI.

| Workflow | Current Model | Env Var | Notes |
|---|---|---|---|
| agent-thread-handler | gpt-4o-mini | THREAD_HANDLER_MODEL | Default for thread replies |
| ea-daily | gpt-4o-mini | EA_DAILY_MODEL | Briefings |
| ea-weekly | gpt-4o-mini | EA_WEEKLY_MODEL | Weekly plans |
| sprint-kickoff | gpt-4o | SPRINT_KICKOFF_MODEL | Sprint planning |
| sprint-close | gpt-4o | SPRINT_CLOSE_MODEL | Sprint retrospectives |
| pr-summary | gpt-4o-mini | PR_SUMMARY_MODEL | PR summaries |
| social-content-generator | gpt-4o | SOCIAL_CONTENT_MODEL | Brand voice |
| growth-content-writer | gpt-4o | GROWTH_CONTENT_MODEL | Brand voice |
| partnership-outreach-drafter | gpt-4o | PARTNERSHIP_MODEL | Professional outreach |
| cpa-tax-review | gpt-4o | CPA_REVIEW_MODEL | Tax accuracy (future: Claude) |
| qa-security-scan | gpt-4o | QA_SCAN_MODEL | Security (future: Claude) |
| weekly-strategy-checkin | gpt-4o | STRATEGY_MODEL | Strategic analysis |
| decision-logger | N/A | N/A | No AI — deterministic formatting |
| infra-health-check | N/A | N/A | No AI — deterministic checks |

### Required n8n Environment Variables

| Variable | Purpose | Required By |
|---|---|---|
| `GITHUB_TOKEN` | GitHub PAT for inline doc fetches (repo is private) | ea-daily, ea-weekly, agent-thread-handler |
| `SLACK_BOT_TOKEN` | Slack Bot Token for posting messages | agent-thread-handler, infra-health-check |
| `SLACK_ALERTS_WEBHOOK_URL` | Incoming webhook for #alerts channel | deploy scripts (external), compose.yaml passthrough |

Set these in the Hetzner `.env` file and in `infra/hetzner/compose.yaml` environment block.

### Changing Models

Edit the workflow in the n8n UI, select the OpenAI node, and change the model dropdown.

**Note:** CPA Tax Review and QA Security Scan are candidates for Claude migration when Anthropic API access is set up. See AI_MODEL_REGISTRY.md for the activation roadmap.

## Security Notes

- Slack signature verification and timestamp replay protection are required for production hardening.
- GitHub webhook signature verification (`X-Hub-Signature-256`) is required for `pr-summary.json`.
- Current workflows run in a trusted internal environment; add these checks before wider exposure.

## Sprint Operations

- Sprint execution is agent-first in `#sprints`.
- Monday kickoff and Friday close are generated and posted by n8n workflows.
- Updates, blockers, and decisions should be posted as thread replies under the kickoff post.
