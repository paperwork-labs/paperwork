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

## DNS + TLS
- Point `axiomfolio.com` to the Render static service and `api.axiomfolio.com` to the Render web service.
- Wait for Render to issue TLS certificates before enabling production traffic.
- Ensure `CORS_ORIGINS` includes the new frontend domain.

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

Render cron defaults (UTC):
- 02:15: IBKR daily Flex sync
- 03:00: admin_coverage_backfill (daily backfill chain)
- Hourly: admin_coverage_refresh
- 04:00: admin_retention_enforce

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
