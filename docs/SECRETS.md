---
owner: infra-ops
last_reviewed: 2026-04-23
doc_kind: runbook
domain: infra
status: active
---
# Secrets & Environment Management

## Architecture

```
Studio Vault (paperworklabs.com/admin/secrets)
    │ AES-256-GCM encrypted in Neon DB
    │
    ├── sync-secrets.sh (Bearer $SECRETS_API_KEY)
    │       ↓
    │   .env.secrets (gitignored, auto-generated)
    │
    ├── Brain reads at runtime (vault.py → HTTP API)
    │
    └── CI/CD reads via vault API directly
```

**One key to rule them all**: Your `.env.local` contains only `SECRETS_API_KEY`.
Everything else flows from the vault.

## Quick Start (New Developer)

1. Clone the repo
2. Get `SECRETS_API_KEY` from an admin (Slack DM or 1Password)
3. Create your key file:
   ```bash
   echo "SECRETS_API_KEY=<key>" > .env.local
   ```
4. Sync secrets from the vault:
   ```bash
   make secrets
   ```
5. Start development:
   ```bash
   make dev
   ```

## Day-to-Day Commands

| Command | What it does |
|---|---|
| `make secrets` | Sync all vault secrets → `.env.secrets` |
| `make dev` | Start Docker Compose (reads `env.dev.defaults` + `.env.secrets`) |
| `./scripts/vault-get.sh SECRET_NAME` | Get a single secret by name |
| `make env-check` | Validate env consistency across environments |

## Adding a New Secret

1. Add to the vault: UI at `paperworklabs.com/admin/secrets` or `POST /api/secrets`
2. Run `make secrets` to sync locally
3. If needed in production: add to Render Dashboard / Vercel Dashboard
4. If needed by Docker dev: it's already in `.env.secrets`, picked up automatically
5. Update `render.yaml` if the service needs it declared

## File Reference

| File | Tracked | Contains Secrets | Purpose |
|---|---|---|---|
| `.env.local` | No | Yes (1 key) | Your `SECRETS_API_KEY` only |
| `.env.secrets` | No | Yes (all) | Auto-generated vault export |
| `infra/env.dev.defaults` | Yes | No | Docker networking defaults |
| `apps/*/.env.development` | Yes | No | Next.js dev public URLs |
| `apps/*/.env.production` | Yes | No | Next.js prod public URLs |
| `apps/*/.env.example` | Yes | No | Templates for app-specific vars |
| `render.yaml` | Yes | No | Production env var declarations |

## What NOT to Do

- Never paste secrets into git-tracked files
- Never create manual `.env` files with real API keys
- Never share `.env.secrets` — each dev syncs their own
- Never hardcode secrets in scripts (use vault API)
- The vault is the source of truth. Always.

## Brain Vault Integration

Brain reads infrastructure secrets at runtime via `apis/brain/app/tools/vault.py`,
calling the same Studio `/api/secrets` API. Brain also has a per-user vault
(`brain_user_vault` table) for personal OAuth tokens and API keys.

## Environment Matrix

| Environment | Secrets Source | Config Source |
|---|---|---|
| Local Docker | `.env.secrets` + `env.dev.defaults` | `infra/compose.dev.yaml` |
| Local non-Docker | `source .env.secrets` | App `.env.development` files |
| Render (production) | Render env vars (set in dashboard) | `render.yaml` |
| Vercel (production) | Vercel env vars (set in dashboard) | Git deploy |
| Hetzner (ops) | `/opt/paperwork-ops/.env` | `infra/hetzner/compose.yaml` |
| n8n | Inherits from Hetzner compose | Hetzner `.env` |
| Brain (runtime) | Studio Vault API | `apis/brain/app/config.py` |
