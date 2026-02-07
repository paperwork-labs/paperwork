## AxiomFolio Full Rebrand Runbook

### 1) Rename the GitHub repo
- Rename the repository in GitHub settings to `axiomfolio`.
- Update any downstream integrations (CI secrets, deployment hooks, webhooks).

### 2) Registry + image paths
- GHCR images are built as `ghcr.io/<owner>/<repo>/backend` and `ghcr.io/<owner>/<repo>/frontend`.
- After repo rename, images will be published under the new path automatically.

### 3) Render services + domains
- Create/rename services to `axiomfolio-*` (API, worker, frontend, redis, db).
- Attach custom domains:
  - `axiomfolio.com` → frontend (static)
  - `api.axiomfolio.com` → backend (web)
- Wait for TLS certificates to finish issuing.

### 4) DNS (Spaceship)
- Set A/ALIAS/CNAME per Render instructions for the apex and `api` subdomain.
- Keep TTLs low for the first cutover.

### 5) Database migration (preserve existing tables)
1. Create the new database (`axiomfolio`) in the provider.
2. Dump the old database:
   - `pg_dump --format=custom --no-owner --no-acl "$OLD_DATABASE_URL" -f axiomfolio.dump`
3. Restore into the new database:
   - `pg_restore --no-owner --no-acl --dbname "$NEW_DATABASE_URL" axiomfolio.dump`
4. Validate schema parity and row counts for key tables.
5. Keep a rollback snapshot of the old DB before cutover.

### 6) Cutover
- Update `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CORS_ORIGINS` in production.
- Run migrations via CI against the new DB.
- Deploy backend, then frontend, then enable cron jobs.

### 7) Validation checklist
- `/health` returns OK
- Login works, portfolio views load
- Worker consumes jobs; cron schedules enqueue correctly
- Alerts/monitoring active (logs, rate limits, job failures)

