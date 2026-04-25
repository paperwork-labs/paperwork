---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
severity_default: yellow
---
# Runbook: Secrets, Vault Sync, And Environment Drift

> One-line summary: Studio Vault, local `.env.secrets` sync, Render/Vercel/Hetzner env, or Brain `vault.py` access is wrong — developers or deploys see missing/invalid secrets or inconsistent env. Use this to classify and fix without pasting keys into git.

## When this fires

- `make env-check` or `make secrets` reports failure or non-zero exit
- `make dev` fails because expected vars are not present after a vault sync
- `.env.secrets` is missing, empty, or stale relative to the Studio Vault UI at `paperworklabs.com/admin/secrets`
- A service that reads `SECRETS_API_KEY` in `.env.local` cannot reach `/api/secrets` (e.g. `sync-secrets.sh` with Bearer `$SECRETS_API_KEY` fails)
- Brain infrastructure secrets or `brain_user_vault` (per-user OAuth/API keys) behave incorrectly at runtime (`apis/brain/app/tools/vault.py` → Studio `/api/secrets`)
- A new secret was added in the vault UI or via `POST /api/secrets` but apps or Docker still do not see it after a normal sync

## Triage (5 min)

```bash
# Local vault export and variable presence (same paths as day-to-day workflow).
make secrets
make env-check
```

```bash
# Single-secret lookup (name as known in vault).
./scripts/vault-get.sh SECRET_NAME
```

If `make secrets` fails or `.env.secrets` stays wrong after the UI shows the value → see **Appendix → Architecture** and **Adding a new secret** (Render / Vercel / `render.yaml`).

If only Brain is affected (personal tokens vs infra) → see **Appendix → Brain vault integration** and the `brain_user_vault` note.

## Verification

- `make env-check` completes successfully (per **Day-to-day commands** in Appendix).
- After `make secrets`, `.env.secrets` exists and matches expectations for the names your apps use (file reference in Appendix); then `make dev` starts with Docker Compose reading `env.dev.defaults` + `.env.secrets`.
- For a single name: `./scripts/vault-get.sh SECRET_NAME` returns the expected value (do not log raw secrets in tickets).
- If the change was for production: confirm the var exists in the right dashboard path (Render / Vercel) or `render.yaml` as documented in **Appendix → Adding a new secret** and **Environment matrix**.

## Rollback

- _TODO: document explicit rollback for mistaken vault write, wide API key rotation, or bad `render.yaml` env block._ — original doc describes forward paths only; keep incident notes until a standard rollback (re-key, revert deploy, restore env snapshot) is agreed.

## Escalation

- Obtain or rotate `SECRETS_API_KEY` via an admin: Slack DM or 1Password (as in **Quick start (new developer)** in Appendix).
- If Studio Vault or `/api/secrets` is down or consistently errors: treat as platform incident per your org’s channel (e.g. `#ops` or `#incidents`) — _TODO: name canonical Slack channel for vault/API outages if not `ops`._

## Post-incident

- If a new class of secret or env gotcha was discovered, update this runbook and bump `last_reviewed`.
- _TODO: add pointer to `docs/KNOWLEDGE.md` or sprint log if your process requires a post-incident row._ — not specified in the original `SECRETS.md` text.

## Appendix

### Architecture

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

### Quick start (new developer)

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

### Day-to-day commands

| Command | What it does |
|---|---|
| `make secrets` | Sync all vault secrets → `.env.secrets` |
| `make dev` | Start Docker Compose (reads `env.dev.defaults` + `.env.secrets`) |
| `./scripts/vault-get.sh SECRET_NAME` | Get a single secret by name |
| `make env-check` | Validate env consistency across environments |

### Adding a new secret

1. Add to the vault: UI at `paperworklabs.com/admin/secrets` or `POST /api/secrets`
2. Run `make secrets` to sync locally
3. If needed in production: add to Render Dashboard / Vercel Dashboard
4. If needed by Docker dev: it's already in `.env.secrets`, picked up automatically
5. Update `render.yaml` if the service needs it declared

### File reference

| File | Tracked | Contains Secrets | Purpose |
|---|---|---|---|
| `.env.local` | No | Yes (1 key) | Your `SECRETS_API_KEY` only |
| `.env.secrets` | No | Yes (all) | Auto-generated vault export |
| `infra/env.dev.defaults` | Yes | No | Docker networking defaults |
| `apps/*/.env.development` | Yes | No | Next.js dev public URLs |
| `apps/*/.env.production` | Yes | No | Next.js prod public URLs |
| `apps/*/.env.example` | Yes | No | Templates for app-specific vars |
| `render.yaml` | Yes | No | Production env var declarations |

### What NOT to do

- Never paste secrets into git-tracked files
- Never create manual `.env` files with real API keys
- Never share `.env.secrets` — each dev syncs their own
- Never hardcode secrets in scripts (use vault API)
- The vault is the source of truth. Always.

### Brain vault integration

Brain reads infrastructure secrets at runtime via `apis/brain/app/tools/vault.py`,
calling the same Studio `/api/secrets` API. Brain also has a per-user vault
(`brain_user_vault` table) for personal OAuth tokens and API keys.

### Environment matrix

| Environment | Secrets Source | Config Source |
|---|---|---|
| Local Docker | `.env.secrets` + `env.dev.defaults` | `infra/compose.dev.yaml` |
| Local non-Docker | `source .env.secrets` | App `.env.development` files |
| Render (production) | Render env vars (set in dashboard) | `render.yaml` |
| Vercel (production) | Vercel env vars (set in dashboard) | Git deploy |
| Hetzner (ops) | `/opt/paperwork-ops/.env` | `infra/hetzner/compose.yaml` |
| n8n | Inherits from Hetzner compose | Hetzner `.env` |
| Brain (runtime) | Studio Vault API | `apis/brain/app/config.py` |
