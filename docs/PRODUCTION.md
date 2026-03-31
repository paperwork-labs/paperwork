# Production Operations Guide

## Table of contents

- [At a glance](#at-a-glance)
- [Goals](#goals)
- [Core Services](#core-services)
- [Required Env Vars](#required-env-vars-minimum)
- [CI/CD](#cicd-github-actions)
- [Domains](#domains)
- [DNS, TLS, and Cloudflare](#dns-tls-and-cloudflare)
- [Cloudflare Tunnel (Local Dev OAuth)](#cloudflare-tunnel-local-dev-oauth)
- [Request Path](#request-path-production)
- [Database migration](#database-migration-rename--preserve-data)
- [Scheduling](#scheduling-celery-beat)
- [Admin access bootstrap](#admin-access-bootstrap)
- [Backups](#backups)
- [Scaling](#scaling)
- [Rollback](#rollback)

---

## At a glance

| Item | Value |
|------|-------|
| **Domains** | Frontend: `https://axiomfolio.com`; API: `https://api.axiomfolio.com` |
| **Provider** | Render (API, worker, frontend, Postgres, Redis); DNS/TLS via Cloudflare |
| **Key env** | `DATABASE_URL`, `REDIS_URL`, `ENCRYPTION_KEY`, `CORS_ORIGINS`; optional Brain integration: `BRAIN_API_KEY`, `BRAIN_WEBHOOK_URL`, `BRAIN_WEBHOOK_SECRET`. Legacy (retained): `RENDER_API_KEY`, `RENDER_OWNER_ID` (for Render cron sync, if ever re-enabled) |

---

## Goals
- Provider-agnostic deployment (Render + Fly supported)
- Immutable Docker images
- Release-time DB migrations (no auto-migrate on app startup)
- Celery Beat scheduling (embedded in worker, catalog-driven from `job_catalog.py`)

## Core Services
- API (FastAPI web service)
- Worker (Celery)
- Celery Beat (embedded in worker, `--beat`; see `render.yaml` `dockerCommand`)
- Postgres (managed)
- Redis (managed)

## Required Env Vars (minimum)
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
- `NEW_RELIC_LICENSE_KEY`
- `ADMIN_SEED_ENABLED` (one-time admin bootstrap)
- `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (only if seeding)
- `CELERY_TASK_SOFT_TIME_LIMIT` (default 300s)
- `CELERY_TASK_TIME_LIMIT` (default 360s)

## CI/CD (GitHub Actions)
1. Build and push Docker images to GHCR.
2. Run DB migrations using backend image.
3. Trigger provider deploy hooks or run Fly deploys.
4. Smoke test `/health`.

### Option A migration policy
- Keep `AUTO_MIGRATE_ON_STARTUP=false` in production runtimes.
- Require `DATABASE_URL_PRODUCTION` GitHub secret so the production workflow always runs:
  - `alembic -c backend/alembic.ini upgrade head`
- Treat missing migration secret as a hard deploy failure.

## Domains

- Frontend (static): `https://axiomfolio.com`
- API: `https://api.axiomfolio.com`

## DNS, TLS, and Cloudflare

### Domain Registrar

**Spaceship** is the domain registrar (owns `axiomfolio.com`). DNS is delegated to Cloudflare.

### Cloudflare DNS

Nameservers (configured in Spaceship):

- `emely.ns.cloudflare.com`
- `kayden.ns.cloudflare.com`

DNS records (configured in Cloudflare dashboard):

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `api` | `axiomfolio-api.onrender.com` | Proxied (orange cloud) |
| CNAME | `@` (root) | Render frontend `.onrender.com` hostname | Proxied |
| CNAME | `www` | `axiomfolio.com` | Proxied |

### Cloudflare SSL/TLS

Mode: **Full (strict)**. Both Cloudflare and Render terminate TLS. Cloudflare encrypts the connection to Render's origin, and Render provides its own certificate. Any other mode causes redirect loops.

### Render Custom Domains

| Service | Custom Domain | Status |
|---------|--------------|--------|
| `axiomfolio-api` (web) | `api.axiomfolio.com` | Verified, certificate issued |
| `axiomfolio-frontend` (static) | `axiomfolio.com` | Verified |

Render subdomains remain enabled as fallbacks: `axiomfolio-api.onrender.com`.

### Render Services

| Service | Type | Plan | Purpose |
|---------|------|------|---------|
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

### CORS

Ensure `CORS_ORIGINS` includes the frontend domain. Current production value:

```
CORS_ORIGINS=https://axiomfolio.com,https://staging.axiomfolio.com
```

## Database migration (rename + preserve data)
If you are renaming the database (e.g., `old_db` → `axiomfolio`), migrate data before cutover:
1. Create the new database in the provider (empty).
2. Export from the old database: `pg_dump --format=custom --no-owner --no-acl "$OLD_DATABASE_URL" -f axiomfolio.dump`.
3. Import into the new database: `pg_restore --no-owner --no-acl --dbname "$NEW_DATABASE_URL" axiomfolio.dump`.
4. Validate row counts for key tables and keep a rollback snapshot of the old DB.
5. Point `DATABASE_URL` and related env vars at the new DB and run migrations via CI.

## Scheduling (Celery Beat)
Production uses **Celery Beat embedded in the worker** (`--beat` in `render.yaml`). Tasks and default crons are defined in `backend/tasks/job_catalog.py`.

Representative Celery targets (see catalog for full list):

- `backend.tasks.account_sync.sync_all_ibkr_accounts`
- `backend.tasks.market.coverage.daily_bootstrap` (`admin_coverage_backfill`)
- `backend.tasks.market.maintenance.prune_old_bars` (`admin_retention_enforce`)

**Default cron** values below are from `backend/tasks/job_catalog.py` (`JobTemplate.id`, `display_name`, `group`, `default_cron`, `default_tz`). Production may override via DB-backed schedules; Beat is the runtime driver.

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

### Execution flow (production)
![Production execution flow](assets/production_execution_flow.png)

### System flow (Beat → queue → workers → DB)
![Production system flow](assets/production_system_flow.png)

### Example tick (UTC)
1. Celery Beat publishes a periodic task when the cron fires.
2. Worker consumes the task from Redis.
3. Task runs in the worker process; data updates land in Postgres; status is recorded in JobRun.

### Dev vs prod behavior
- **Production:** Beat in the worker enqueues tasks from the catalog (and DB-backed schedule rows where used). Legacy Render Cron Jobs (`admin_coverage_backfill`, `admin_retention_enforce`, `ibkr-daily-flex-sync`) are **suspended** (see Render Services table). Optional: `RENDER_API_KEY` and `RENDER_OWNER_ID` only if you re-enable Render cron sync (`render_sync_service.py`).
- **Development:** Same catalog and DB-backed schedules as production; Render sync is a no-op locally. Use "Run Now" in Admin > Schedules to trigger tasks manually.

## Admin access bootstrap
To create the first admin user in production:
1. Set `ADMIN_SEED_ENABLED=true` plus `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
2. Deploy once; the admin user is created if it does not already exist.
3. Set `ADMIN_SEED_ENABLED=false` (recommended) after the initial seed.

Admin-only endpoints (all `/api/v1/market-data/admin/*` plus task triggers like `/market-data/indices/constituents/refresh` and `/market-data/symbols/{symbol}/refresh`) require an admin user.

## Backups
- Postgres: enable provider backups and periodic exports.
- Redis: used for caching and Celery broker; persistence is lower priority since schedules are now DB-backed.

## Scaling
- Scale API based on latency and request rate.
- Scale workers based on queue depth and job duration.
- Use rate limiting to protect upstream providers and DB.

## Rollback
- Roll back by redeploying the previous image tag.
- If migrations are non-reversible, use guarded feature flags until data migrations complete.
