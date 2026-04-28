---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: plan
domain: infra
status: active
---
# Render Migration — AxiomFolio → Paperwork Labs team

**Status:** READY TO EXECUTE (Phase 0 complete)
**Target:** Consolidate all AxiomFolio Render resources under the `Paperwork` team (LLC-owned), preserving prod DB data, with zero data loss and ~45 min of API downtime during cutover.

---

## Context

| | Old (source) | New (target) |
|---|---|---|
| **Team** | AxiomFolio | Paperwork |
| **Team ID** | `tea-d64meenpm1nc738rhdsg` | `tea-d6uflspj16oc73ft6gj0` |
| **Billing contact** | sankalp404@gmail.com (personal) | billing@paperworklabs.com (LLC) |
| **API key** | user-pasted `rnd_Sfuuw...` | vault `RENDER_API_KEY` = `rnd_K9gq...` |
| **Access** | direct REST API | MCP + REST API |
| **Autodeploy status** | **off** (manually disabled) | (new, will be on) |

**Why full recreate, not transfer?** Render does not support ownership transfer between teams — [confirmed open feature request since 2020](https://feedback.render.com/features/p/transfer-service-to-team-account). The only path is recreate + data migration.

---

## Resources to migrate

From `docs/infra/RENDER_INVENTORY.md`:

| Resource | Old ID | Plan | Notes |
|---|---|---|---|
| `axiomfolio-api` (web) | `srv-d64mkqi4d50c73eite20` | standard (Docker) | 35 env vars, port 8000 |
| `axiomfolio-frontend` (static) | `srv-d64mkhi4d50c73eit7ng` | free | 1 env var |
| `axiomfolio-worker` (bg) | `srv-d64mkqi4d50c73eite10` | standard (Docker) | 30 env vars, Celery fast+beat |
| `axiomfolio-worker-heavy` (bg) | `srv-d7hpo2v7f7vs738o9p80` | standard (Docker) | 12 env vars, Celery heavy queue |
| `axiomfolio-db` (postgres) | `dpg-d725m719fqoc739rc3f0-a` | basic_1gb | **7.3 GB data, 96 tables**, PG 16.13 |
| `axiomfolio-redis` (keyvalue) | `red-d64mkhi4d50c73eit7n0` | starter | ephemeral, not backed up |
| 3 cron jobs | `crn-*` | — | **retired** per render.yaml comment; drop |

Blueprint source of truth: [`render.yaml`](../render.yaml). Crons are intentionally absent (scheduling moved to Celery Beat inside `axiomfolio-worker`).

---

## Env var categorization

Dumped to `/tmp/axiomfolio-render-migration/*.envvars.json` (mode 600, gitignored).

**Auto-wired by `render.yaml`** — do NOT copy; new blueprint will set:
- `DATABASE_URL` (from new `axiomfolio-db`)
- `REDIS_URL`, `RATE_LIMIT_STORAGE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (from new `axiomfolio-redis`)
- `SECRET_KEY` (generated fresh)
- `ENVIRONMENT`, `LOG_FORMAT`, `AUTO_MIGRATE_ON_STARTUP`, `WORKER_ROLE` (static)

**Must copy from old → new** (product secrets):

| Category | Keys |
|---|---|
| Brokers (Schwab) | `SCHWAB_CLIENT_ID`, `SCHWAB_CLIENT_SECRET`, `SCHWAB_REDIRECT_URI`, `SCHWAB_AUTH_BASE` |
| Market data | `ALPHA_VANTAGE_API_KEY`, `FINNHUB_API_KEY`, `FMP_API_KEY`, `POLYGON_API_KEY`, `TWELVE_DATA_API_KEY` |
| LLM | `OPENAI_API_KEY` |
| Brain | `BRAIN_API_KEY`, `BRAIN_WEBHOOK_SECRET`, `BRAIN_WEBHOOK_URL`, `BRAIN_TOOLS_USER_ID` |
| Infra | `NEW_RELIC_LICENSE_KEY`, `RENDER_API_KEY`, `ENCRYPTION_KEY` |
| Flags | `ENABLE_TRADING`, `ALLOW_LIVE_ORDERS`, `TRADE_APPROVAL_MODE`, `TRADE_APPROVAL_THRESHOLD`, `MARKET_PROVIDER_POLICY`, `AGENT_AUTONOMY_LEVEL`, `DEPLOY_HEALTH_SERVICE_IDS` |
| CORS | `CORS_ORIGINS` |
| Rate limit | `RATE_LIMIT_DEFAULT` |

**Must add from `infra/env.prod.overrides.local`** (not currently in prod but should be):
- `ADMIN_SEED_ENABLED`, `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
- `RESEND_API_KEY`

---

## Cutover plan

### Phase 0 — Pre-flight ✓ DONE

- [x] Inventory both teams via API (`docs/infra/RENDER_INVENTORY.md`)
- [x] Verify DB allow-list includes this machine (`98.47.48.112`)
- [x] Install `pg_dump` v16 matching server version (`brew install postgresql@16`)
- [x] Snapshot all env vars to `/tmp/axiomfolio-render-migration/` (gitignored, mode 600)
- [x] Identify DB size: **7.3 GB / 96 tables**
- [x] Confirm autodeploy is off on all old services (deploy churn paused)

### Phase 1 — Provision new team (NO DOWNTIME)

Provisions services under `tea-d6uflspj16oc73ft6gj0` with empty DB. Old services remain live during this phase.

1. **[USER]** In Render dashboard → Paperwork team → **New → Blueprint**
   - Repo: `paperwork-labs/axiomfolio`
   - Branch: `main`
   - Render reads `render.yaml` and provisions:
     - `axiomfolio-db` (postgres basic_1gb) — new, empty
     - `axiomfolio-redis` (keyvalue starter)
     - `axiomfolio-api` (web, standard, Docker)
     - `axiomfolio-worker` (bg, standard, Docker)
     - `axiomfolio-worker-heavy` (bg, standard, Docker)
     - `axiomfolio-frontend` (static)
2. **[AGENT]** Once blueprint is applied, sync non-blueprint env vars via `scripts/migration/push-env-vars.sh` (uses both API keys — read old, write new)
3. **[AGENT]** Let services attempt first deploy. API will migrate an empty DB + seed admin user. Frontend builds. Workers idle.
4. **[USER]** Verify in dashboard: all 6 services show "live" or "running" status.

_Phase 1 impact:_ zero on prod. Old prod still serves `api.axiomfolio.com`.

### Phase 2 — Downtime window starts

1. **[USER]** Post to `#ops` Slack / update status page: "AxiomFolio API maintenance, ETA 45 min"
2. **[AGENT]** Suspend old services to guarantee write-stop:
   - Suspend `axiomfolio-worker`, `axiomfolio-worker-heavy`, `axiomfolio-api` (in that order — workers first so API can still refuse traffic gracefully)
3. **[AGENT]** Dump old DB:
   ```sh
   /opt/homebrew/opt/postgresql@16/bin/pg_dump \
     --format=custom --compress=9 --verbose \
     --no-owner --no-privileges \
     --dbname="$OLD_DATABASE_URL" \
     --file=/tmp/axiomfolio-render-migration/prod.dump
   ```
   ETA: ~15 min for 7.3 GB
4. **[AGENT]** Suspend new web/workers (to prevent app writes during restore), keep new DB unsuspended
5. **[AGENT]** Restore into new DB:
   ```sh
   /opt/homebrew/opt/postgresql@16/bin/pg_restore \
     --dbname="$NEW_DATABASE_URL" \
     --jobs=4 --no-owner --no-privileges \
     --verbose \
     /tmp/axiomfolio-render-migration/prod.dump
   ```
   ETA: ~20 min
6. **[AGENT]** Verify row counts match (sample top 10 tables by size)
7. **[AGENT]** Resume new services (api + workers)
8. **[AGENT]** Hit `https://<new-api>.onrender.com/health` — expect 200
9. **[AGENT]** Smoke: auth endpoint, portfolio list endpoint, one broker sync endpoint

### Phase 3 — DNS cutover

1. **[AGENT]** Remove custom domains from OLD services:
   - `api.axiomfolio.com` from old `axiomfolio-api`
   - `axiomfolio.com`, `www.axiomfolio.com` from old `axiomfolio-frontend`
2. **[AGENT]** Add custom domains to NEW services (Render will issue new SSL certs, ~2-5 min)
3. **[AGENT]** Update Cloudflare DNS (`CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ZONE_ID` in local `infra/env.dev`):
   - `api.axiomfolio.com` CNAME → new `srv-*.onrender.com`
   - `axiomfolio.com` / `www` CNAME → new static site
4. **[AGENT]** Verify SSL cert live: `curl -sI https://api.axiomfolio.com/health`
5. **[AGENT]** Wait 5 min for global DNS propagation, re-verify

_Downtime ends here._ Total ~45 min.

### Phase 4 — Post-cutover verification (24h soak)

- [ ] All New Relic signals green
- [ ] No 5xx burst in new service logs
- [ ] Celery beat schedule firing (check tasks ran)
- [ ] Broker sync task ran (Schwab OAuth flow intact)
- [ ] User can log in to frontend
- [ ] Zero hits on old service URLs (confirms DNS fully propagated)

### Phase 5 — Decommission (after 24h soak)

- [ ] Delete old cron jobs (3x): `admin_coverage_backfill`, `admin_retention_enforce`, `ibkr-daily-flex-sync`
- [ ] Delete old services (4x)
- [ ] Delete old `axiomfolio-redis`
- [ ] Delete old `axiomfolio-db` — **only after** new prod has run ≥24h clean
- [ ] Delete / repurpose old `tea-d64meenpm1nc738rhdsg` team
- [ ] Rotate `RENDER_API_KEY` for old team (invalidate the one pasted in chat)
- [ ] Push new AxiomFolio env vars into Studio Vault with `AXIOMFOLIO_` namespace
- [ ] Rotate all credentials flagged in `docs/ROTATION_BACKLOG.md`

---

## Rollback plan

**If Phase 2 restore fails or integrity check fails:**
1. Do NOT proceed to DNS cutover
2. Unsuspend OLD services (they still have the data + live DNS)
3. Drop the partial new DB and retry dump/restore
4. Prod continues serving from old team

**If Phase 3 DNS cutover causes SSL/connectivity issues:**
1. Revert Cloudflare DNS CNAME to old service
2. Re-add custom domain to old services (they still own the SSL cert)
3. Time-to-recover: ~2-10 min once CNAME change propagates

---

## Go/no-go checklist (read before executing Phase 2)

- [ ] New services in Paperwork team all show "live" (Phase 1 done)
- [ ] Env vars synced successfully (diff old → new shows only blueprint-managed keys differ)
- [ ] New `axiomfolio-db` has been verified reachable via psql
- [ ] Maintenance window announced (Slack / status page)
- [ ] DB dump destination has ≥20 GB free disk
- [ ] This agent has `pg_dump` v16 at `/opt/homebrew/opt/postgresql@16/bin/`
- [ ] Old DB allow-list still whitelists `98.47.48.112` (this machine)
- [ ] New DB has allow-list updated to whitelist `98.47.48.112` (needed for restore)
- [ ] No active user sessions in prod (or accept they'll get kicked)

---

## Scripts

All execution scripts live in `scripts/migration/`:
- `dump-old-db.sh` — pg_dump from old prod to local file
- `restore-new-db.sh` — pg_restore into new prod from local file
- `push-env-vars.sh` — copy env vars from old → new services via both API keys
- `swap-custom-domains.sh` — remove from old, add to new, update Cloudflare DNS
- `verify.sh` — smoke tests against a given API base URL
