# n8n Persona Workflows

6 AI persona workflows deployed on the Hetzner VPS at `n8n.filefree.tax`.

## Workflows

| Workflow | Trigger | AI Model | Output |
|---|---|---|---|
| Social Content Generator | POST webhook `/social-content` | GPT-4o-mini | Notion (Content Calendar) |
| Growth Content Writer | POST webhook `/growth-content` | GPT-4o-mini | Notion (Content Calendar) |
| Weekly Strategy Check-in | Cron (Monday 9am) | GPT-4o | Notion (Decision Log) |
| QA Security Scan | POST webhook `/qa-scan` | GPT-4o | GitHub Issue (security label) |
| Partnership Outreach Drafter | POST webhook `/partnership-outreach` | GPT-4o | Notion (Partnership Pipeline) |
| CPA Tax Review | POST webhook `/cpa-review` | GPT-4o | Notion (CPA Reviews) |

## Credential Setup (n8n UI)

Go to `n8n.filefree.tax` > Settings > Credentials and add:

1. **OpenAI** — already configured
2. **Notion API** — Create an internal integration at https://www.notion.so/my-integrations, copy the token. Then share each target database with the integration.
3. **GitHub API** — Create a personal access token at https://github.com/settings/tokens with `repo` scope (for creating issues).
4. **Postiz API** (optional) — Generate an API key in the Postiz UI at `social.filefree.tax`.

After adding credentials, open each workflow in the n8n editor and:
1. Click the output node (Notion/GitHub)
2. Select the correct credential from the dropdown
3. For Notion nodes: select the target database from the dropdown
4. Save and activate the workflow

## Deploying Updates

```bash
# From repo root
scp infra/hetzner/workflows/*.json root@204.168.147.100:/tmp/
ssh root@204.168.147.100 '
for f in social-content-generator growth-content-writer weekly-strategy-checkin qa-security-scan partnership-outreach-drafter cpa-tax-review; do
  docker cp /tmp/${f}.json filefree-ops-n8n-1:/tmp/${f}.json
  docker exec filefree-ops-n8n-1 n8n import:workflow --input=/tmp/${f}.json
done'
```
