# Render Inventory — AxiomFolio Team (pre-migration snapshot)

_Generated 2026-04-23. Owner: `tea-d64meenpm1nc738rhdsg` (team "AxiomFolio", contact sankalp404@gmail.com)._

## Services

| Name | ID | Type | Status | Repo | Branch |
|------|----|------|--------|------|--------|
| axiomfolio-worker-heavy | srv-d7hpo2v7f7vs738o9p80 | background_worker | not_suspended | https://github.com/paperwork-labs/axiomfolio | main |
| admin_coverage_backfill | crn-d64pouogjchc739tpi8g | cron_job | suspended | https://github.com/paperwork-labs/axiomfolio | main |
| axiomfolio-worker | srv-d64mkqi4d50c73eite10 | background_worker | not_suspended | https://github.com/paperwork-labs/axiomfolio | main |
| axiomfolio-api | srv-d64mkqi4d50c73eite20 | web_service | not_suspended | https://github.com/paperwork-labs/axiomfolio | main |
| admin_retention_enforce | crn-d64mkqi4d50c73eite2g | cron_job | suspended | https://github.com/paperwork-labs/axiomfolio | main |
| ibkr-daily-flex-sync | crn-d64mkqi4d50c73eite0g | cron_job | suspended | https://github.com/paperwork-labs/axiomfolio | main |
| axiomfolio-frontend | srv-d64mkhi4d50c73eit7ng | static_site | not_suspended | https://github.com/paperwork-labs/axiomfolio | main |

## Postgres

| Name | ID | Plan | Status |
|------|----|------|--------|
| axiomfolio-db | dpg-d725m719fqoc739rc3f0-a | basic_1gb | available |

## Key-Value (Redis)

| Name | ID | Plan | Status |
|------|----|------|--------|
| axiomfolio-redis | red-d64mkhi4d50c73eit7n0 | starter | available |

## Env var counts (per service)

- `axiomfolio-api` (`srv-d64mkqi4d50c73eite20`): 35 env vars
- `axiomfolio-frontend` (`srv-d64mkhi4d50c73eit7ng`): 1 env vars
- `axiomfolio-worker` (`srv-d64mkqi4d50c73eite10`): 30 env vars
- `axiomfolio-worker-heavy` (`srv-d7hpo2v7f7vs738o9p80`): 12 env vars

## DNS (current)

- `api.axiomfolio.com`  → Cloudflare (104.21.65.9 / 172.67.156.253)
- `axiomfolio.com`      → Cloudflare
- `brain.paperworklabs.com` → `brain-api-zo5t.onrender.com` (**separate Render account**, not in this team)
- `paperworklabs.com`   → 216.198.79.1 (Vercel)

## Migration plan (Option A — team rename + service transfer)

1. Rename team `tea-d64meenpm1nc738rhdsg` from "AxiomFolio" → "Paperwork Labs" (dashboard)
2. Obtain API key for the 2nd Render account (the one hosting `brain-api-zo5t`)
3. Transfer `brain-api` + any FileFree/LaunchFree services INTO the renamed team (dashboard "Transfer service")
4. Update billing contact → `founders@paperworklabs.com` (or whichever LLC-owned email)
5. Rotate `RENDER_API_KEY` after the old contact is no longer needed

Zero DNS changes required. Zero service recreation. Total active time: ~15 min.
