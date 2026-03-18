# n8n Agent Workflows — Paperwork Labs

AI agent workflows run on the Hetzner VPS at `n8n.paperworklabs.com`.

Architecture is **Slack-first**:
- One Slack Event Subscriptions endpoint (`slack-events`) handled by `agent-thread-handler.json`
- Persona-routed thread responses in Slack
- Scheduled briefings, sprint kickoff/close, and operational alerts posted to Slack channels
- Decision logging routed from the thread handler to the decision workflow

## Workflows

| Workflow | File | Trigger | AI Model | Output |
|---|---|---|---|---|
| Agent Thread Handler | `agent-thread-handler.json` | Slack event (thread/mention) | GPT-4o | Reply in Slack thread |
| EA Daily Briefing | `ea-daily.json` | Cron 7am PT | GPT-4o | #daily-briefing |
| EA Weekly Plan | `ea-weekly.json` | Cron Sunday 6pm PT | GPT-4o | #all-paperwork-labs |
| PR Summary | `pr-summary.json` | GitHub webhook (PR opened) | GPT-4o-mini | #engineering |
| Decision Logger | `decision-logger.json` | Triggered by thread handler (`log this` / `decided:` in #decisions) | deterministic formatter | KNOWLEDGE.md + thread confirm |
| Social Content Generator | `social-content-generator.json` | POST /social-content | GPT-4o-mini | #general |
| Growth Content Writer | `growth-content-writer.json` | POST /growth-content | GPT-4o-mini | #general |
| Weekly Strategy Check-in | `weekly-strategy-checkin.json` | Cron Monday 9am | GPT-4o | #all-paperwork-labs |
| QA Security Scan | `qa-security-scan.json` | POST /qa-scan | GPT-4o | #engineering + GitHub Issue |
| Partnership Outreach | `partnership-outreach-drafter.json` | POST /partnership-outreach | GPT-4o | #general |
| CPA Tax Review | `cpa-tax-review.json` | POST /cpa-review | GPT-4o | #general |
| Sprint Kickoff | `sprint-kickoff.json` | Cron Mon 7am PT | GPT-4o | #sprints + #all-paperwork-labs |
| Sprint Close | `sprint-close.json` | Cron Fri 9pm PT | GPT-4o | #sprints + KNOWLEDGE.md |

## Credential Setup

Go to `n8n.paperworklabs.com` > Settings > Credentials and add:

1. **OpenAI** — API key from platform.openai.com/api-keys.
2. **Slack Bot Token** — Create as a "Header Auth" credential with header name `Authorization` and value `Bearer xoxb-...` (the Bot User OAuth Token from api.slack.com > Your App > OAuth & Permissions).
3. **GitHub PAT** — Create as a "Header Auth" credential with header name `Authorization` and value `token ghp_...` (personal access token with `repo` scope from github.com/settings/tokens).

After adding credentials, open each workflow in the n8n editor, select the correct credential on every OpenAI / HTTP Request node, save, and activate.

## Deploying Updates

```bash
# Copy workflow files to server
scp infra/hetzner/workflows/*.json root@204.168.147.100:/tmp/paperwork-workflows/

# Import each workflow from inside container filesystem
ssh root@204.168.147.100 'for f in /tmp/paperwork-workflows/*.json; do
  docker cp "$f" paperwork-ops-n8n-1:/tmp/$(basename "$f")
  docker exec paperwork-ops-n8n-1 n8n import:workflow --input="/tmp/$(basename "$f")"
done'

# Publish all imported workflows (required for production webhooks)
ssh root@204.168.147.100 'ids=$(docker exec paperwork-ops-postgres-1 psql -U filefree_ops -d n8n -At -c "SELECT id FROM workflow_entity;"); for id in $ids; do docker exec paperwork-ops-n8n-1 n8n publish:workflow --id=$id >/dev/null; done'
```

**Important**: `n8n import:workflow` **deactivates** workflows. After deploy, go to `n8n.paperworklabs.com` and reactivate any schedule-based workflows (EA Daily Briefing, EA Weekly Plan, Sprint Kickoff, Sprint Close, Weekly Strategy Check-in). The bot will not run until they are active.

## Daily Briefing Troubleshooting

If the 7am PT daily briefing did not post to #daily-briefing:

1. **Workflow inactive**: After any `n8n import:workflow` deploy, EA Daily Briefing is deactivated. Open the workflow in n8n and toggle it active.
2. **OpenAI quota**: The briefing uses GPT-4o. If OpenAI returns "insufficient_quota", top up billing at platform.openai.com and ensure the API key in n8n credentials has access.
3. **Cron timezone**: The workflow runs at 7:00 in the timezone set by `GENERIC_TIMEZONE` (see `infra/hetzner/compose.yaml`). Ensure production has `GENERIC_TIMEZONE=America/Los_Angeles` so 7am is Pacific.
4. **Execution history**: In n8n, check Executions for "EA Daily Briefing" to see if it ran and whether it failed (e.g. credential error, HTTP error).

## Slack Event Subscriptions

Slack Event Subscriptions must point to a **single** request URL (thread handler webhook):

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and select your Paperwork Labs app.
2. Navigate to **Event Subscriptions** and toggle "Enable Events" on.
3. Set the **Request URL** to:
   `https://n8n.paperworklabs.com/webhook/a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d/webhook/slack-events`
   Slack sends a `url_verification` challenge; this workflow returns the `challenge` payload automatically.
4. Under **Subscribe to bot events**, add:
   - `message.channels` — messages in public channels (thread replies and #decisions triggers)
   - `app_mention` — @mentions of the bot (for Agent Thread Handler)
   - `message.groups` — messages in private channels (if the bot is invited to any)
5. Click **Save Changes**. Slack will start delivering events to n8n immediately.
6. Ensure the bot is invited to all channels where it should listen (`#decisions`, `#daily-briefing`, `#engineering`, `#all-paperwork-labs`, `#general`).

## PR Thread Persona Routing

- PR Summary posts are sent to `#engineering` and include a thread router hint.
- Reply in the PR thread with persona cues like `legal`, `growth`, `social`, `qa`, `strategy`, `engineering`, `cpa`, `partnerships`, or `ea`.
- `agent-thread-handler.json` uses cue-based override routing so requested personas reply in the same thread.

## Security Notes

- Slack signature verification and timestamp replay protection are required for production hardening.
- GitHub webhook signature verification (`X-Hub-Signature-256`) is required for `pr-summary.json`.
- Current workflows run in a trusted internal environment; add these checks in Phase 2 before wider exposure.

## Sprint Operations

- Sprint execution is agent-first in `#sprints`.
- Monday kickoff and Friday close are generated and posted by n8n workflows.
- Updates, blockers, and decisions should be posted as high-signal thread replies under the kickoff post.
