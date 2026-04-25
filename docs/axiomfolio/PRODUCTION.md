---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: runbook
domain: infra
status: active
severity_default: red
---
# Runbook: AxiomFolio Production Operations

> One-line summary: Day-to-day and incident response for AxiomFolio on Render, Cloudflare, and GitHub — deploys, health, DNS, data, and scheduling. Use this when production is wrong or you need the authoritative production reference.

## When this fires

Recurring and incident signals. Open this runbook for:

- **User-visible outage or severe degradation** — `https://axiomfolio.com` or `https://api.axiomfolio.com` unreachable, HTTP 5xx, or app errors blocking core flows.
- **Provider / deploy red** — Render dashboard shows `axiomfolio-api`, `axiomfolio-worker`, or `axiomfolio-frontend` failing; GitHub Actions deploy or migration job red; image push or hook failure.
- **Health / smoke failure** — `https://api.axiomfolio.com/health` not `200` with expected body; post-deploy smoke that hits `/health` fails (see [CI/CD](#cicd-github-actions) in Appendix).
- **Data or migration cutover** — need DB rename/migrate, `DATABASE_URL` change, or `alembic` upgrade path blocked (see [Database migration](#database-migration-rename--preserve-data) in Appendix).
- **Celery / Beat / queue issues** — scheduled jobs not running, queue backing up, or worker service unhealthy (see [Scheduling](#scheduling-celery-beat) in Appendix).
- **DNS / TLS / CORS** — custom domain or certificate errors; `CORS_ORIGINS` misconfiguration (see [DNS, TLS, and Cloudflare](#dns-tls-and-cloudflare) and [Cors](#cors) in Appendix).
- **Reference lookup** — any time you need domains, env vars, Render service names, or tunnel/dev OAuth context (see Appendix).

| Item | Value |
|------|-------|
| **Domains** | Frontend: `https://axiomfolio.com`; API: `https://api.axiomfolio.com` |
| **Provider** | Render (API, worker, frontend, Postgres, Redis); DNS/TLS via Cloudflare |
| **Key env** | `DATABASE_URL`, `REDIS_URL`, `ENCRYPTION_KEY`, `CORS_ORIGINS`; optional Brain integration: `BRAIN_API_KEY`, `BRAIN_WEBHOOK_URL`, `BRAIN_WEBHOOK_SECRET`. Legacy (retained): `RENDER_API_KEY`, `RENDER_OWNER_ID` (for Render cron sync, if ever re-enabled) |

_TODO: document alert or dashboard tile names that page on-call (e.g. Studio `/admin/infrastructure` or Render notifications)._

## Triage (≤5 min)

```bash
# API liveness
curl -fsS "https://api.axiomfolio.com/health"

# Frontend (headers only)
curl -fsSI "https://axiomfolio.com"

# Optional: follow redirects and show final code
curl -fsSIL -o /dev/null -w "final_http=%{http_code}\n" "https://axiomfolio.com"
```

1. **Render** — [Render dashboard](https://dashboard.render.com) → services `axiomfolio-api`, `axiomfolio-worker`, `axiomfolio-frontend`, `axiomfolio-db`, `axiomfolio-redis` — check deploy status, logs, and recent deploys.
2. **CI** — GitHub Actions: latest deploy and migration job for the repo (image build, `alembic upgrade head`, smoke `/health`).

If API health fails and Render is green → [Path: app or config](#verification). If Render is red → [Path: deploy or provider](#rollback). If only frontend fails → CORS, static site, or Cloudflare (see [Appendix: DNS, TLS, and Cloudflare](#dns-tls-and-cloudflare)). If triage is inconclusive in 5 min → [Escalation](#escalation).

_TODO: document one log query (e.g. host + request id pattern) for 5xx on `axiomfolio-api`._

## Verification

- `curl` to `https://api.axiomfolio.com/health` returns `200` with the expected health payload (match service contract).
- `https://axiomfolio.com` returns `200` (or expected SPA behavior) and assets load; no cert errors in the browser.
- **Post-deploy (CI):** pipeline smoke test to `/health` passes (see [CI/CD (GitHub Actions)](#cicd-github-actions) in Appendix).
- **Render:** services show live/successful deploy; no error storm in the last few minutes in service logs.
- **Optional (DB):** if the incident touched migrations, confirm migration revision and app connectivity — _TODO: document read-only `alembic current` or SQL check for operators._

## Rollback

- **Deploy:** roll back by redeploying the previous image tag in Render (Service → **Deploys** → previous good deploy → **Redeploy**), or the equivalent in your release process.
- **Migrations:** if migrations are non-reversible, use guarded feature flags until data migrations complete; do not YOLO a second one-way migration without a plan.
- **Config:** if a bad env var change caused the issue, restore the prior value in Render and redeploy; for secrets, use the team’s secure rotation path (see [ENCRYPTION_KEY_ROTATION.md](ENCRYPTION_KEY_ROTATION.md) for vault key context).

## Escalation

- **Primary:** _TODO: name Slack channel (e.g. `#ops`)_ — on-call or owner `infra-ops` persona; include Render service link, commit SHA, and whether `/health` fails.
- **Provider:** [Render](https://dashboard.render.com) status or support; [Cloudflare](https://dash.cloudflare.com) if DNS/SSL; **Spaceship** registrar only if delegation/nameserver issues (see [Domain Registrar](#domain-registrar) in Appendix).
- **RED / production-impacting:** if customer-facing impact is ongoing and triage is stuck after ~15–30 min, _TODO: document PagerDuty or explicit phone tree_.

## Post-incident

- Add a row to `docs/KNOWLEDGE.md` (or the team’s incident log) under **Recent incidents** — what broke, what fixed it, and a pointer to this runbook + Appendix section.
- If a new guardrail is needed (e.g. CI check, env validation), file a follow-up in the engineering backlog and consider `.cursor/rules` or `validate_production_settings()` updates in the app repo.
- If this file was wrong or stale, **update the procedure** and bump `last_reviewed` in the frontmatter before closing the incident.
- _TODO: link Linear or sprint project if the team files incidents there._

## Appendix

**Reference and procedures preserved from the prior Production Operations Guide** (restructured only; not removed).

### Table of contents (appendix)

- [Goals](#goals)
- [Core Services](#core-services)
- [Required Env Vars (minimum)](#required-env-vars-minimum)
- [CI/CD (GitHub Actions)](#cicd-github-actions)
- [Domains](#domains)
- [DNS, TLS, and Cloudflare](#dns-tls-and-cloudflare)
- [Cloudflare Tunnel (Local Dev OAuth)](#cloudflare-tunnel-local-dev-oauth)
- [Request Path (Production)](#request-path-production)
- [Cors](#cors)
- [Database migration (rename + preserve data)](#database-migration-rename--preserve-data)
- [Scheduling (Celery Beat)](#scheduling-celery-beat)
- [Admin access bootstrap](#admin-access-bootstrap)
- [Backups](#backups)
- [Scaling](#scaling)
- [Pending rotations](#pending-rotations)

### Goals
- Provider-agnostic deployment (Render + Fly supported)
- Immutable Docker images
- Release-time DB migrations (no auto-migrate on app startup)
- Celery Beat scheduling (embedded in worker, catalog-driven from `job_catalog.py`)

### Core Services
- API (FastAPI web service)
- Worker (Celery)
- Celery Beat (embedded in worker, `--beat`; see `render.yaml` `dockerCommand`)
- Postgres (managed)
- Redis (managed)

### Required Env Vars (minimum)
- `ENVIRONMENT=production`
- `SECRET_KEY` (non-default)
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CORS_ORIGINS`
- `RATE_LIMIT_DEFAULT`

Credential vault:
- `ENCRYPTION_KEY` (Fernet key for credential vault; generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). Rotation procedure: [ENCRYPTION_KEY_ROTATION.md](ENCRYPTION_KEY_ROTATION.md).

**NEVER set these in production** (enforced by `validate_production_settings()` -- app will refuse to start):
- `IBKR_FLEX_TOKEN`, `IBKR_FLEX_QUERY_ID`, `TASTYTRADE_CLIENT_SECRET`, `TASTYTRADE_REFRESH_TOKEN`
- These are dev-only global fallbacks for seed accounts. In production, all broker credentials are per-user and stored encrypted in the `account_credentials` table via the credential vault.

Optional:
- `BRAIN_API_KEY` (authenticates Brain → AxiomFolio tool API; header `X-Brain-Api-Key`)
- `BRAIN_WEBHOOK_URL` (base URL for outbound webhooks to Brain)
- `BRAIN_WEBHOOK_SECRET` (HMAC signing secret shared with Brain for webhook payloads)
- `RENDER_API_KEY`, `RENDER_OWNER_ID` (legacy — Render cron schedule sync via `render_sync_service.py`; only if re-enabling platform crons)
- `RATE_LIMIT_STORAGE_URL` (Redis-backed limiter)
- `OTEL_EXPORTER_OTLP_ENDPOINT` + `OTEL_EXPORTER_OTLP_HEADERS` (optional; OTel replaces the dormant NR integration removed 2026-04-24)
- `ADMIN_SEED_ENABLED` (one-time admin bootstrap)
- `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (only if seeding)
- `CELERY_TASK_SOFT_TIME_LIMIT` (default 300s)
- `CELERY_TASK_TIME_LIMIT` (default 360s)

### CI/CD (GitHub Actions)
1. Build and push Docker images to GHCR.
2. Run DB migrations using backend image.
3. Trigger provider deploy hooks or run Fly deploys.
4. Smoke test `/health`.

#### Option A migration policy
- Keep `AUTO_MIGRATE_ON_STARTUP=false` in production runtimes.
- Require `DATABASE_URL_PRODUCTION` GitHub secret so the production workflow always runs:
  - `alembic -c app/alembic.ini upgrade head`
- Treat missing migration secret as a hard deploy failure.

### Domains

- Frontend (static): `https://axiomfolio.com`
- API: `https://api.axiomfolio.com`

### DNS, TLS, and Cloudflare

#### Domain Registrar

**Spaceship** is the domain registrar (owns `axiomfolio.com`). DNS is delegated to Cloudflare.

#### Cloudflare DNS

Nameservers (configured in Spaceship):

- `emely.ns.cloudflare.com`
- `kayden.ns.cloudflare.com`

DNS records (configured in Cloudflare dashboard):

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `api` | `axiomfolio-api.onrender.com` | Proxied (orange cloud) |
| CNAME | `@` (root) | Render frontend `.onrender.com` hostname | Proxied |
| CNAME | `www` | `axiomfolio.com` | Proxied |

#### Cloudflare SSL/TLS

Mode: **Full (strict)**. Both Cloudflare and Render terminate TLS. Cloudflare encrypts the connection to Render's origin, and Render provides its own certificate. Any other mode causes redirect loops.

#### Render Custom Domains

| Service | Custom Domain | Status |
|---------|--------------|--------|
| `axiomfolio-api` (web) | `api.axiomfolio.com` | Verified, certificate issued |
| `axiomfolio-frontend` (static) | `axiomfolio.com` | Verified |

Render subdomains remain enabled as fallbacks: `axiomfolio-api.onrender.com`.

#### Render Services

| Service | Type | Plan | Purpose |
|---------|------|------|----------|
| `axiomfolio-api` | Web (Docker) | Standard (1 CPU / 2 GB) | FastAPI backend |
| `axiomfolio-worker` | Worker (Docker) | Standard | Celery worker + embedded Beat (`--beat`) |
| `axiomfolio-frontend` | Static | Free | React SPA |
| `axiomfolio-db` | PostgreSQL | Basic 1 GB | Primary database |
| `axiomfolio-redis` | Key-Value | Starter | Cache + Celery broker |

**Legacy Render Cron Jobs (suspended):** Do not run these alongside embedded Beat — they would duplicate work. The following provider cron jobs are **SUSPENDED**: `admin_coverage_backfill`, `admin_retention_enforce`, `ibkr-daily-flex-sync`. The `axiomfolio-worker` service runs Celery with **`--beat` embedded**; periodic schedules are driven from `job_catalog.py` (and DB-backed schedule rows where the app uses them).

### Cloudflare Tunnel (Local Dev OAuth)

A Cloudflare Tunnel routes `api-dev.axiomfolio.com` traffic to your local machine for testing Schwab OAuth locally. The tunnel uses a **dedicated dev subdomain** (`api-dev`) so production (`api.axiomfolio.com`) is never affected.

#### Credentials in `infra/env.dev`

| Variable | Purpose |
|----------|---------|
| `CLOUDFLARED_TUNNEL_TOKEN` | Authenticates the cloudflared connector |
| `CLOUDFLARED_TUNNEL_ID` (optional) | Tunnel identifier (not used by the dev tunnel workflow; kept for reference) |

#### One-Time Setup

1. **Cloudflare Zero Trust > Networks > Tunnels** -- open the tunnel (`axiomfolio-dev`) and set the **Public Hostname** to:
   - Subdomain: `api-dev`, Domain: `axiomfolio.com`
   - Service Type: **HTTP**, URL: `backend:8000`
2. **Schwab Developer Portal** -- add `https://api-dev.axiomfolio.com/api/v1/aggregator/schwab/callback` as a registered redirect URI.
3. Set `SCHWAB_REDIRECT_URI=https://api-dev.axiomfolio.com/api/v1/aggregator/schwab/callback` in `infra/env.dev`.

#### Dev OAuth Testing Workflow

```bash
make tunnel-on     # Starts cloudflared container
                   # api-dev.axiomfolio.com → local backend:8000
                   # api.axiomfolio.com (prod) is NOT affected
make tunnel-logs   # Verify "Connection registered"

# Test OAuth at http://localhost:5173/settings/connections

make tunnel-off    # Stops cloudflared container
```

Production stays up the entire time. No DNS manipulation is needed.

#### How It Works

```
tunnel-on:
  1. docker compose up cloudflared (tunnel registers, claims api-dev.axiomfolio.com)
  2. Traffic: Schwab callback → Cloudflare → tunnel → local backend:8000

tunnel-off:
  1. docker compose stop cloudflared
  2. api-dev.axiomfolio.com becomes unreachable (no effect on prod)
```

#### Alternative

Complete the Schwab OAuth link from the production instance at `https://axiomfolio.com/settings/connections`. Tokens are stored in the production database. Both dev and prod share `OAUTH_STATE_SECRET`, so the JWT is valid on either side.

### Request Path (Production)

```
User -> Cloudflare CDN (TLS termination, DDoS, WAF)
     -> Render load balancer (TLS re-encryption)
     -> axiomfolio-api container (uvicorn :8000)
```

### Cors

Ensure `CORS_ORIGINS` includes the frontend domain. Current production value:

```
CORS_ORIGINS=https://axiomfolio.com,https://staging.axiomfolio.com
```

### Database migration (rename + preserve data)
If you are renaming the database (e.g., `old_db` → `axiomfolio`), migrate data before cutover:
1. Create the new database in the provider (empty).
2. Export from the old database: `pg_dump --format=custom --no-owner --no-acl "$OLD_DATABASE_URL" -f axiomfolio.dump`.
3. Import into the new database: `pg_restore --no-owner --no-acl --dbname "$NEW_DATABASE_URL" axiomfolio.dump`.
4. Validate row counts for key tables and keep a rollback snapshot of the old DB.
5. Point `DATABASE_URL` and related env vars at the new DB and run migrations via CI.

### Scheduling (Celery Beat)
Production uses **Celery Beat embedded in the worker** (`--beat` in `render.yaml`). Tasks and default crons are defined in `app/tasks/job_catalog.py`.

Representative Celery targets (see catalog for full list):

- `app.tasks.account_sync.sync_all_ibkr_accounts`
- `app.tasks.market.coverage.daily_bootstrap` (`admin_coverage_backfill`)
- `app.tasks.market.maintenance.prune_old_bars` (`admin_retention_enforce`)

**Default cron** values below are from `app/tasks/job_catalog.py` (`JobTemplate.id`, `display_name`, `group`, `default_cron`, `default_tz`). Production may override via DB-backed schedules; Beat is the runtime driver.

| Job ID | Display name | Group | Default cron | TZ |
|--------|--------------|-------|--------------|-----|
| `ibkr-daily-flex-sync` | IBKR Daily Sync | portfolio | `15 2 * * *` | UTC |
| `schwab-daily-sync` | Schwab Daily Sync | portfolio | `30 2 * * *` | UTC |
| `recover-stale-syncs` | Recover Stale Syncs | portfolio | `*/5 * * * *` | UTC |
| `admin_coverage_backfill` | Nightly Coverage Pipeline | market_data | `0 1 * * *` | UTC |
| `check_regime_alerts` | Regime Alert Monitor | market_data | `*/5 9-16 * * 1-5` | America/New_York |
| `monitor-open-orders` | Monitor Open Orders | portfolio | `* * * * *` | UTC |
| `ibkr-gateway-watchdog` | IBKR Gateway Watchdog | portfolio | `*/5 * * * *` | UTC |
| `reconcile-order-fills` | Reconcile Order Fills | portfolio | `*/10 * * * *` | UTC |
| `evaluate-strategy-entries` | Evaluate Strategy Entry Rules | strategy | `0 2 * * 1-5` | America/New_York |
| `evaluate-exit-cascade` | Evaluate Exit Cascade | strategy | `30 2 * * 1-5` | America/New_York |
| `admin_retention_enforce` | Data Retention Cleanup | maintenance | `30 4 * * *` | UTC |
| `admin_recover_stale_job_runs` | Recover Stale Job Runs | maintenance | `0 */6 * * *` | UTC |
| `generate_daily_digest` | Daily Intelligence Digest | intelligence | `30 1 * * 1-5` | America/New_York |
| `generate_weekly_brief` | Weekly Strategy Brief | intelligence | `0 7 * * 1` | America/New_York |
| `generate_monthly_review` | Monthly Review | intelligence | `0 8 1 * *` | America/New_York |
| `audit_quality_refresh` | Audit Quality Refresh | market_data | `0 */2 * * *` | UTC |
| `constituents_refresh` | Index Constituents Refresh | market_data | `30 0 * * *` | UTC |
| `tracked_cache_refresh` | Tracked Universe Cache Rebuild | market_data | `45 0 * * *` | UTC |
| `intraday_5m_backfill` | 5-Minute Candle Backfill | market_data | `30 13-21 * * 1-5` | UTC |
| `auto_ops_health_check` | Auto-Ops Health Remediation | maintenance | `*/15 * * * *` | UTC |

To see all schedules: query the internal agent tool `list_schedules`, or the Admin Schedules UI at `/settings/admin/schedules`.
To trigger a task immediately: use `run_task_now` with a catalog `task_id`.

#### Execution flow (production)
![Production execution flow](assets/production_execution_flow.png)

#### System flow (Beat → queue → workers → DB)
![Production system flow](assets/production_system_flow.png)

#### Example tick (UTC)
1. Celery Beat publishes a periodic task when the cron fires.
2. Worker consumes the task from Redis.
3. Task runs in the worker process; data updates land in Postgres; status is recorded in JobRun.

#### Dev vs prod behavior
- **Production:** Beat in the worker enqueues tasks from the catalog (and DB-backed schedule rows where used). Legacy Render Cron Jobs (`admin_coverage_backfill`, `admin_retention_enforce`, `ibkr-daily-flex-sync`) are **suspended** (see Render Services table). Optional: `RENDER_API_KEY` and `RENDER_OWNER_ID` only if you re-enable Render cron sync (`render_sync_service.py`).
- **Development:** Same catalog and DB-backed schedules as production; Render sync is a no-op locally. Use "Run Now" in Admin > Schedules to trigger tasks manually.

### Admin access bootstrap
To create the first admin user in production:
1. Set `ADMIN_SEED_ENABLED=true` plus `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
2. Deploy once; the admin user is created if it does not already exist.
3. Set `ADMIN_SEED_ENABLED=false` (recommended) after the initial seed.

Admin-only endpoints (all `/api/v1/market-data/admin/*` plus task triggers like `/market-data/indices/constituents/refresh` and `/market-data/symbols/{symbol}/refresh`) require an admin user.

### Backups
- Postgres: enable provider backups and periodic exports.
- Redis: used for caching and Celery broker; persistence is lower priority since schedules are now DB-backed.

### Scaling
- Scale API based on latency and request rate.
- Scale workers based on queue depth and job duration.
- Use rate limiting to protect upstream providers and DB.

### Pending rotations

**Status**: Active tracker of credentials exposed in chat during the Render migration (2026-04-23).
**Owner**: @sankalp
**Review cadence**: Weekly until cleared.

All secrets below were pasted into the Brain chat during the vault-unification + Render-migration sprint. They are currently the **live, working** credentials — do NOT rotate until the replacement flow is in place (otherwise you'll break prod).

Rotation order matters: do **P0 first** (highest blast radius + external dependencies), then work down. Each rotation = update vault → redeploy services that consume it → verify.

---

#### P0 — Rotate within 48h of migration completion (Phase 5 done)

These have the largest blast radius and are actively exploited if leaked:

| Key in vault | What it protects | Rotation steps |
|---|---|---|
| `AXIOMFOLIO_IBKR_PASSWORD` | Founder's live IBKR trading account | 1. Log into IBKR Client Portal → change password  2. Update `AXIOMFOLIO_IBKR_PASSWORD` in vault  3. Redeploy `axiomfolio-worker` (IBC reads on boot)  4. Verify IB Gateway container reconnects |
| `AXIOMFOLIO_TASTYTRADE_REFRESH_TOKEN` | Founder's active Tastytrade OAuth (live trading) | 1. my.tastytrade.com → API Access → revoke token  2. Re-complete OAuth flow via AxiomFolio Settings → Brokerages  3. New token auto-lands in `broker_oauth_connections` (per-user, not vault)  4. Delete `AXIOMFOLIO_TASTYTRADE_REFRESH_TOKEN` from vault once per-user flow confirmed |
| `AXIOMFOLIO_TASTYTRADE_CLIENT_SECRET` | Product-level Tastytrade OAuth app | 1. my.tastytrade.com → regenerate client secret  2. Update vault  3. Redeploy `axiomfolio-api` + `axiomfolio-worker`  4. Existing user tokens keep working (refresh uses new secret on next cycle) |
| `AXIOMFOLIO_SCHWAB_CLIENT_SECRET` | Product-level Schwab OAuth app | 1. Schwab Developer Portal → rotate secret  2. Update vault + redeploy  3. Users re-consent on next login (Schwab tokens are short-lived anyway) |
| `AXIOMFOLIO_OPENAI_API_KEY` | OpenAI billing (LLM auto-ops agent) | 1. platform.openai.com → revoke key  2. Generate new key, same project  3. Update vault  4. Redeploy `axiomfolio-api` + `axiomfolio-worker` |

---

#### P1 — Rotate within 2 weeks

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

#### P2 — Rotate within 30 days

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

#### Decommissioning checklist (old Render team)

These are **not rotations** — they get deleted when we decommission the old `AxiomFolio` Render team at end of Phase 5:

- [ ] Old `RENDER_API_KEY` = `rnd_SfuuwEBxo2peQ6AKOLjTqw3ksAlI` (used by migration scripts — invalidates itself when old team is deleted)
- [ ] Old Render team ID `tea-d64meenpm1nc738rhdsg` — delete team in dashboard
- [ ] Any scripts referencing the old team ID — already scoped to `AF_OLD_RENDER_KEY` env var, no hardcoded refs in repo

---

#### Rotation SLA policy (going forward)

Once migration settles, **no secret should live unrotated for >90 days**. Add this to the Studio Vault service monthly CPA/CFO review.

- P0 keys (broker/trading, OpenAI): rotate every 60 days
- P1 keys (OAuth app secrets, webhooks): rotate every 90 days
- P2 keys (read-only / metered): rotate on vendor-recommended cadence or on anomaly only

Brain will eventually own this alarm — a future `/api/v1/vault/expiring` endpoint will surface upcoming rotations to Studio. Implementation tracked under "Pending rotations" in the appendix.

---

#### How to rotate a secret in the Studio Vault

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
