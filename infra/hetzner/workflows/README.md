# n8n Agent Workflows — Paperwork Labs

AI agent workflows deployed on the Hetzner VPS at `n8n.paperworklabs.com`. All workflows follow a **Slack-first architecture**: every agent posts its output to a Slack channel rather than writing to Notion or external systems. This keeps the team in one place, makes outputs immediately visible, and lets us react in threads.

The **Agent Thread Handler** is the backbone — it listens for Slack events (thread replies and @mentions) and routes them to GPT-4o for contextual responses. Other workflows run on cron schedules or webhook triggers and post their results to designated channels.

## Workflows

| Workflow | File | Trigger | AI Model | Output |
|---|---|---|---|---|
| Agent Thread Handler | `venture-agent-thread-handler.json` | Slack event (thread/mention) | GPT-4o | Reply in Slack thread |
| EA Daily Briefing | `venture-ea-daily.json` | Cron 7am PT | GPT-4o-mini | #daily-briefing |
| EA Weekly Plan | `venture-ea-weekly.json` | Cron Sunday 6pm PT | GPT-4o | #all-paperwork-labs |
| PR Summary | `venture-pr-summary.json` | GitHub webhook (PR opened) | GPT-4o-mini | #engineering |
| Decision Logger | `venture-decision-logger.json` | Slack event ("log this" in #decisions) | GPT-4o-mini | KNOWLEDGE.md + thread confirm |
| Social Content Generator | `social-content-generator.json` | POST /social-content | GPT-4o-mini | #general |
| Growth Content Writer | `growth-content-writer.json` | POST /growth-content | GPT-4o-mini | #general |
| Weekly Strategy Check-in | `weekly-strategy-checkin.json` | Cron Monday 9am | GPT-4o | #all-paperwork-labs |
| QA Security Scan | `qa-security-scan.json` | POST /qa-scan | GPT-4o | #engineering + GitHub Issue |
| Partnership Outreach | `partnership-outreach-drafter.json` | POST /partnership-outreach | GPT-4o | #general |
| CPA Tax Review | `cpa-tax-review.json` | POST /cpa-review | GPT-4o | #general |

## Credential Setup

Go to `n8n.paperworklabs.com` > Settings > Credentials and add:

1. **OpenAI** — API key from platform.openai.com/api-keys.
2. **Slack Bot Token** — Create as a "Header Auth" credential with header name `Authorization` and value `Bearer xoxb-...` (the Bot User OAuth Token from api.slack.com > Your App > OAuth & Permissions).
3. **GitHub PAT** — Create as a "Header Auth" credential with header name `Authorization` and value `token ghp_...` (personal access token with `repo` scope from github.com/settings/tokens).

After adding credentials, open each workflow in the n8n editor, select the correct credential on every OpenAI / HTTP Request node, save, and activate.

## Deploying Updates

```bash
for f in infra/hetzner/workflows/*.json; do
  scp "$f" root@204.168.147.100:/tmp/
done
ssh root@204.168.147.100 'cd /opt/paperwork-ops && for f in /tmp/*.json; do docker compose exec -T n8n n8n import:workflow --input="$f"; done'
```

## Slack Event Subscriptions

The **Agent Thread Handler** and **Decision Logger** workflows require Slack Event Subscriptions to receive real-time events.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and select your Paperwork Labs app.
2. Navigate to **Event Subscriptions** and toggle "Enable Events" on.
3. Set the **Request URL** to the n8n webhook URL for the Agent Thread Handler workflow (e.g., `https://n8n.paperworklabs.com/webhook/agent-thread-handler`). Slack will send a verification challenge — n8n handles this automatically.
4. Under **Subscribe to bot events**, add:
   - `message.channels` — messages in public channels (for Decision Logger listening in #decisions)
   - `app_mention` — @mentions of the bot (for Agent Thread Handler)
   - `message.groups` — messages in private channels (if the bot is invited to any)
5. Click **Save Changes**. Slack will start delivering events to n8n immediately.
6. Ensure the bot is invited to all channels where it should listen (`#decisions`, `#daily-briefing`, `#engineering`, `#all-paperwork-labs`, `#general`).
