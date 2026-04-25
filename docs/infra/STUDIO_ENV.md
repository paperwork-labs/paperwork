---
owner: infra-ops
last_reviewed: 2026-04-25
doc_kind: runbook
domain: infra
status: active
---

# Studio Vercel environment variables — setup runbook

[Studio](https://paperworklabs.com) `admin` routes probe n8n, Vercel, Render, Hetzner, GitHub, Slack, and the Paperwork Brain. Several optional integrations degrade gracefully when a secret is missing, but **production Studio on Vercel** still had gaps at last audit: the four variables below are the usual blockers for **live** Hetzner/Vercel/Brain status cards and Brain-backed admin actions. This runbook tells you how to set them safely and verify.

## Required environment variables (Vercel, Studio production)

| Variable | Purpose | Where to get the value | How Studio uses it |
| --- | --- | --- | --- |
| `BRAIN_API_URL` | Base URL for the Brain API | Production URL from [Render](https://dashboard.render.com) for the `brain-api` service (e.g. `https://brain-api.onrender.com` or the current custom host if configured) | `fetch` from admin routes to Brain; sprints/workflows pages that list or trigger Brain-backed actions |
| `BRAIN_API_SECRET` | Server-to-server auth to Brain **admin** GET/POST from Studio | [Studio secrets vault](https://paperworklabs.com/api/secrets) — key name **`BRAIN_API_SECRET`**. **Preferred:** `./scripts/vault-get.sh BRAIN_API_SECRET` from the monorepo root (requires `SECRETS_API_KEY` in `.env.local` per [Secrets ops](../../.cursor/rules/secrets-ops.mdc)) | Sent as header **`X-Brain-Secret`** (see `getBrainApiRoot` callers in `apps/studio/src/lib/command-center.ts` and admin API routes) — personas list, memory episodes, ops probes, and similar |
| `HETZNER_API_TOKEN` | Hetzner Cloud API (read is enough) | [Hetzner Cloud Console](https://console.hetzner.cloud) → project → **Security** → **API tokens** (create a read-scoped token for status) | `getInfrastructureStatus()` — Hetzner card on [`/admin/infrastructure`](https://paperworklabs.com/admin/infrastructure) with live server stats |
| `VERCEL_API_TOKEN` | Vercel platform API | [Vercel account tokens](https://vercel.com/account/tokens) (scope to this account/team) | Vercel probe on the infrastructure page; also supply the same value to **GitHub Actions** as a repo/organization secret for [auto-promote](VERCEL_AUTO_PROMOTE.md) (`.github/workflows/vercel-promote-on-merge.yaml`) |

## Setup commands (Vercel CLI)

Run `vercel` from the Studio app directory so the correct linked project is targeted (`apps/studio` in this monorepo). Install the Vercel CLI and `vercel link` if you have not already.

**Plain value (or echo pipe):**

```bash
cd apps/studio
echo "https://brain-api.onrender.com" | vercel env add BRAIN_API_URL production
```

Confirm the URL against the live Render service URL before pasting; custom domains for Brain, if any, should be used instead of a stale hostname.

**Vault-first for `BRAIN_API_SECRET`:** from the monorepo root, pipe into the project dir:

```bash
cd /path/to/paperwork
./scripts/vault-get.sh BRAIN_API_SECRET | (cd apps/studio && vercel env add BRAIN_API_SECRET production)
```

**Direct paste (when vault CLI is not available):** open the value from the Studio vault in the browser (never commit it), then:

```bash
cd apps/studio
vercel env add HETZNER_API_TOKEN production
# paste the Hetzner token at the prompt

vercel env add VERCEL_API_TOKEN production
# paste the Vercel token at the prompt
```

Redeploy Studio after **production** env changes ([Deployments](https://vercel.com) → project → **Redeploy**), or wait for the next production deployment.

## Vault-first reminder

Per [`.cursor/rules/secrets-ops.mdc`](../../.cursor/rules/secrets-ops.mdc): **add or rotate credentials in the Studio secrets vault first**, then mirror a copy to Vercel (or n8n/Hetzner) only when that runtime must hold it. The vault is authoritative; Vercel is a deployment mirror. Full process: [Secrets guide](../SECRETS.md).

## Verification

1. Trigger a new production deployment after the env add (or confirm the env variables appear under **Vercel → Project → Settings → Environment Variables** for `Production`).
2. Open `https://paperworklabs.com/admin/infrastructure` (authenticated).
3. **Hetzner** card: should show project/server rows without an error banner.
4. **Vercel** card: should list projects (not “not configured” / error).
5. **Sprints (or any Brain-tied admin page)**: should load remote lessons or Brain-backed data; network tab to Brain should be `2xx` (not connection refused to a wrong base URL).

## Related

- [Secrets: developer guide and matrix](../SECRETS.md) — which keys live in the vault vs platform envs
- [`.cursor/rules/secrets-ops.mdc`](../../.cursor/rules/secrets-ops.mdc) — agent checklist for `make secrets` / `vault-get`
- [Vercel auto-promote runbook](VERCEL_AUTO_PROMOTE.md) — `VERCEL_API_TOKEN` in GitHub Actions for `vercel promote`

### Internal links (Studio code)

- Infrastructure aggregation: `apps/studio/src/lib/command-center.ts` (Hetzner/Vercel/Render/… probes) — set envs here, not in this doc, when the variable names are extended.

---

**Owner:** `infra-ops` persona (Track 1 / Studio prod hygiene). **Related inventory:** [Render services](RENDER_INVENTORY.md) (where `brain-api` is hosted — cross-check `BRAIN_API_URL` if probes fail).
