# Secret Rotation Backlog

**Status**: Active tracker of credentials exposed in chat during the Render migration (2026-04-23).
**Owner**: @sankalp
**Review cadence**: Weekly until cleared.

All secrets below were pasted into the Brain chat during the vault-unification + Render-migration sprint. They are currently the **live, working** credentials — do NOT rotate until the replacement flow is in place (otherwise you'll break prod).

Rotation order matters: do **P0 first** (highest blast radius + external dependencies), then work down. Each rotation = update vault → redeploy services that consume it → verify.

---

## P0 — Rotate within 48h of migration completion (Phase 5 done)

These have the largest blast radius and are actively exploited if leaked:

| Key in vault | What it protects | Rotation steps |
|---|---|---|
| `AXIOMFOLIO_IBKR_PASSWORD` | Founder's live IBKR trading account | 1. Log into IBKR Client Portal → change password  2. Update `AXIOMFOLIO_IBKR_PASSWORD` in vault  3. Redeploy `axiomfolio-worker` (IBC reads on boot)  4. Verify IB Gateway container reconnects |
| `AXIOMFOLIO_TASTYTRADE_REFRESH_TOKEN` | Founder's active Tastytrade OAuth (live trading) | 1. my.tastytrade.com → API Access → revoke token  2. Re-complete OAuth flow via AxiomFolio Settings → Brokerages  3. New token auto-lands in `broker_oauth_connections` (per-user, not vault)  4. Delete `AXIOMFOLIO_TASTYTRADE_REFRESH_TOKEN` from vault once per-user flow confirmed |
| `AXIOMFOLIO_TASTYTRADE_CLIENT_SECRET` | Product-level Tastytrade OAuth app | 1. my.tastytrade.com → regenerate client secret  2. Update vault  3. Redeploy `axiomfolio-api` + `axiomfolio-worker`  4. Existing user tokens keep working (refresh uses new secret on next cycle) |
| `AXIOMFOLIO_SCHWAB_CLIENT_SECRET` | Product-level Schwab OAuth app | 1. Schwab Developer Portal → rotate secret  2. Update vault + redeploy  3. Users re-consent on next login (Schwab tokens are short-lived anyway) |
| `AXIOMFOLIO_OPENAI_API_KEY` | OpenAI billing (LLM auto-ops agent) | 1. platform.openai.com → revoke key  2. Generate new key, same project  3. Update vault  4. Redeploy `axiomfolio-api` + `axiomfolio-worker` |

---

## P1 — Rotate within 2 weeks

Medium blast radius — third-party services with metered usage:

| Key in vault | What it protects | Notes |
|---|---|---|
| `AXIOMFOLIO_ADMIN_PASSWORD` | Prod admin seed login (`fuckyou!`) | **Currently weak AND exposed.** Generate a 32-char random password, update vault, run `alembic upgrade head` which picks up new seed on next deploy. Best done right after P0 completes. |
| `AXIOMFOLIO_BRAIN_API_KEY` | AxiomFolio → Brain integration (outbound calls) | 1. Regenerate via Brain admin UI  2. Update `AXIOMFOLIO_BRAIN_API_KEY` in vault + `AXIOMFOLIO_API_KEY` in Paperwork-side vault (paired)  3. Redeploy both |
| `AXIOMFOLIO_BRAIN_WEBHOOK_SECRET` | HMAC signature for Brain webhooks AxiomFolio calls | Must match the secret in Brain. Rotate both together. |
| `AXIOMFOLIO_GOOGLE_CLIENT_SECRET` | Google OAuth (user login) | Google Cloud Console → Credentials → regenerate. Existing sessions continue until token expiry. |
| `AXIOMFOLIO_RESEND_API_KEY` | Transactional email | resend.com → revoke + new key. No user impact. |
| `AXIOMFOLIO_CLOUDFLARE_API_TOKEN` | DNS mgmt for axiomfolio.com zone | Only used by migration scripts + tunnel. Rotate once migration Phase 5 closes. |

---

## P2 — Rotate within 30 days

Lower blast radius — read-only market data or nice-to-have observability:

| Key in vault | Service |
|---|---|
| `AXIOMFOLIO_ALPHA_VANTAGE_API_KEY` | Free tier, no billing |
| `AXIOMFOLIO_FINNHUB_API_KEY` | Free tier |
| `AXIOMFOLIO_TWELVE_DATA_API_KEY` | Paid — moderate spend |
| `AXIOMFOLIO_FMP_API_KEY` | Paid — moderate spend |
| `AXIOMFOLIO_POLYGON_API_KEY` | Paid — high spend if abused |
| `AXIOMFOLIO_NEW_RELIC_LICENSE_KEY` | Ingest-only, no write access |
| `AXIOMFOLIO_IBKR_FLEX_TOKEN` | Read-only flex query export |

All 5 Discord webhooks (`AXIOMFOLIO_DISCORD_WEBHOOK_*`): webhook URLs contain their secret in the path. Attacker could spam Discord channels but has no access to broader infra. Rotate if spam observed — otherwise deprioritize.

---

## Decommissioning checklist (old Render team)

These are **not rotations** — they get deleted when we decommission the old `AxiomFolio` Render team at end of Phase 5:

- [ ] Old `RENDER_API_KEY` = `rnd_SfuuwEBxo2peQ6AKOLjTqw3ksAlI` (used by migration scripts — invalidates itself when old team is deleted)
- [ ] Old Render team ID `tea-d64meenpm1nc738rhdsg` — delete team in dashboard
- [ ] Any scripts referencing the old team ID — already scoped to `AF_OLD_RENDER_KEY` env var, no hardcoded refs in repo

---

## Rotation SLA policy (going forward)

Once migration settles, **no secret should live unrotated for >90 days**. Add this to the Studio Vault service monthly CPA/CFO review.

- P0 keys (broker/trading, OpenAI): rotate every 60 days
- P1 keys (OAuth app secrets, webhooks): rotate every 90 days
- P2 keys (read-only / metered): rotate on vendor-recommended cadence or on anomaly only

Brain will eventually own this alarm — see `apis/brain/app/routers/vault.py` for the future `/api/v1/vault/expiring` endpoint.

---

## How to rotate a secret in the Studio Vault

```bash
# 1. Pull current value for reference
./scripts/vault-get.sh AXIOMFOLIO_OPENAI_API_KEY

# 2. Get new value from vendor dashboard, then update vault via admin API
curl -sS -u "$ADMIN_EMAIL:$ADMIN_PASS" \
  -X PUT https://paperworklabs.com/api/secrets/<secret-id> \
  -H "Content-Type: application/json" \
  -d '{"value":"<new-value>","last_rotated_at":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}'

# 3. Sync to Render services that consume it (once sync-vault-to-render.sh lands in axiomfolio repo)
./scripts/sync-vault-to-render.sh axiomfolio-api axiomfolio-worker axiomfolio-worker-heavy

# 4. Trigger rolling restart on those services (Render auto-deploys on env var change, but confirm)
```

Last updated: 2026-04-23 (migration day).
