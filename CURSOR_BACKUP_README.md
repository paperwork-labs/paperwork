# Cursor Context Backup — Setup for New Machine

**Purpose**: This zip contains Cursor plans and agent transcripts from the previous development machine. Use it to restore context when picking up the project on a new machine (e.g., work laptop).

---

## What's in the Zip

- **plans/** — ~200 Cursor plan files (Distill brand, PRD regeneration, Phase 1 monorepo, etc.)
- **agent-transcripts/** — Chat transcripts with prior decisions and execution context

**Extract**: `unzip cursor-context-backup.zip`

---

## What's NOT in the Zip (Secrets)

Credentials are never stored in the repo or this backup. They live in:

| Where | What |
|-------|------|
| **Render dashboard** | API production: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `OPENAI_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, OAuth keys |
| **Vercel dashboard** | Frontend production: `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, etc. |
| **infra/env.dev** | Local dev (you create this from the example) |
| **web/.env.local** | Local frontend dev |
| **n8n UI** | n8n credential store (OpenAI, Notion, Postiz, GitHub) |

See [docs/CREDENTIALS.md](docs/CREDENTIALS.md) for the full registry and where each credential is configured.

---

## Setup Checklist (Ask the New Agent to Help)

1. **Clone the repo** (or pull latest)

2. **Create local env files** (gitignored):
   ```bash
   cp infra/env.dev.example infra/env.dev
   ```
   Edit `infra/env.dev` — for local dev you can leave OAuth/AI keys blank (mock mode). Add real keys when you need to test OCR or social login.

3. **Create frontend env** (if running web locally):
   ```bash
   cp web/.env.example web/.env.local   # or copy from web/.env.development
   ```

4. **MCP / Cursor** (optional):
   ```bash
   cp .cursor/mcp.json.example .cursor/mcp.json
   ```
   Add tokens for any MCP tools you use (e.g., Postiz).

5. **Production access**: Log into Render and Vercel dashboards to view/copy production env vars when needed. You may need to be added as a collaborator if this is a fresh account.

---

## After You're Set Up

**Delete the zip** from the repo and commit the removal (it was only for transfer):

```bash
rm cursor-context-backup.zip
rm -rf cursor-context-backup/
git add cursor-context-backup.zip cursor-context-backup/
git commit -m "chore: remove cursor backup zip after transfer"
```

---

## Prompt for the New Agent

> "I'm setting up fileFree on a new machine. I have cursor-context-backup.zip extracted. Please help me: (1) create infra/env.dev from the example, (2) confirm what I need from Render/Vercel vs what works in mock mode locally, (3) run `make dev` or equivalent to verify the stack starts."
