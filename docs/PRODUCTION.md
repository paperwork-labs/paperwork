# Production Operations Guide

## Goals
- Provider-agnostic deployment (Render + Fly supported)
- Immutable Docker images
- Release-time DB migrations (no auto-migrate on app startup)
- Cost-aware scheduling (cron jobs instead of always-on beat)

## Core Services
- API (FastAPI web service)
- Worker (Celery)
- Cron runner (scheduled task enqueuer)
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
- `ENCRYPTION_KEY` (Fernet key for credential vault; generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)

**NEVER set these in production** (enforced by `validate_production_settings()` -- app will refuse to start):
- `IBKR_FLEX_TOKEN`, `IBKR_FLEX_QUERY_ID`, `TASTYTRADE_CLIENT_SECRET`, `TASTYTRADE_REFRESH_TOKEN`
- These are dev-only global fallbacks for seed accounts. In production, all broker credentials are per-user and stored encrypted in the `account_credentials` table via the credential vault.

Optional:
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
| `axiomfolio-worker` | Worker (Docker) | Standard | Celery worker |
| `axiomfolio-frontend` | Static | Free | React SPA |
| `axiomfolio-db` | PostgreSQL | Basic 1 GB | Primary database |
| `axiomfolio-redis` | Key-Value | Starter | Cache + Celery broker |

### Cloudflare Tunnel (Local Dev OAuth)

A Cloudflare Tunnel allows routing `api.axiomfolio.com` traffic to your local machine. This is required for testing Schwab OAuth locally because the callback URL (`https://api.axiomfolio.com/api/v1/aggregator/schwab/callback`) must match the Schwab Developer Portal registration exactly.

**Tunnel credentials** are stored in `infra/env.dev`:

- `CLOUDFLARED_TUNNEL_TOKEN`
- `CLOUDFLARED_TUNNEL_ID`

**Docker service**: `cloudflared` in `infra/compose.dev.yaml` (profile: `tunnel`).

**Workflow for local OAuth testing**:

1. In Cloudflare dashboard, temporarily disable the `api` CNAME record (or switch it to use the tunnel)
2. Start the tunnel: `make tunnel-up`
3. Verify: `make tunnel-logs` (should show "Connection registered")
4. Test the OAuth flow from `http://localhost:5173/settings/connections`
5. Stop the tunnel: `make tunnel-down`
6. Re-enable the `api` CNAME to `axiomfolio-api.onrender.com`

**Alternative**: Complete the initial Schwab OAuth link from the production instance at `https://axiomfolio.com`. Tokens are stored in the production database and can be copied to dev if needed (requires matching `ENCRYPTION_KEY`/`FERNET_KEY`).

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

## Scheduling (cron, no always-on beat)
Use scheduled jobs to enqueue tasks (task status names shown in parentheses):
- `backend.tasks.account_sync.sync_all_ibkr_accounts`
- `backend.tasks.market_data_tasks.bootstrap_daily_coverage_tracked` (`admin_coverage_backfill`, daily backfill chain)
- `backend.tasks.market_data_tasks.monitor_coverage_health` (`admin_coverage_refresh`)
- `backend.tasks.market_data_tasks.enforce_price_data_retention` (`admin_retention_enforce`)

Render cron defaults (UTC, from `job_catalog.py`):
- `*/5 * * * *` — stale-sync-recovery (auto-reset stuck syncs)
- `0 1 * * *` — admin_coverage_backfill (nightly pipeline: bars, indicators, snapshots)
- `20 1 * * *` — admin_snapshots_history_record (daily snapshot archive)
- `30 1 * * *` — backfill_position_metadata (enrich positions from snapshots)
- `0 2 * * *` — index constituents refresh (S&P 500, NASDAQ-100, Dow 30)
- `15 2 * * *` — IBKR daily FlexQuery sync
- `30 2 * * *` — Schwab daily sync + tracked symbols refresh
- `45 2 * * *` — data quality audit
- `0 * * * *` — admin_coverage_refresh (hourly health check)
- `10 4 * * *` — intraday 5m bar backfill (D-1)
- `30 4 * * *` — admin_retention_enforce (purge old 5m bars)
- `45 4 * * *` — fill missing snapshot fundamentals
- `0 4 * * 0` — refresh stale fundamentals (weekly, Sunday)
- `0 */6 * * *` — recover stale job runs

### Execution flow (production)
![Production execution flow](assets/production_execution_flow.png)

### System flow (cron → queue → workers → DB)
![Production system flow](assets/production_system_flow.png)

### Midnight example (UTC)
1. Provider cron triggers a job (e.g., 03:00 UTC).
2. `backend/scripts/run_task.py` enqueues the Celery task.
3. Worker pulls the task from Redis and executes it.
4. Data updates land in Postgres; status is recorded in JobRun.

### Dev vs prod behavior
- **Production:** Schedules are stored in PostgreSQL (`cron_schedule` table) and synced to Render cron-job services via the Render API. Set `RENDER_API_KEY` and `RENDER_OWNER_ID` on the API service.
- **Development:** Same DB-backed schedules, but Render sync is a no-op. Use "Run Now" in Admin > Schedules to trigger tasks manually.

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
