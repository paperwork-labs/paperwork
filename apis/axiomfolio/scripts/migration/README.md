# Render migration scripts — AxiomFolio → Paperwork Labs team

One-shot migration from the old `AxiomFolio` Render team to the `Paperwork` team.
See [`docs/RENDER_MIGRATION_PLAN.md`](../../docs/RENDER_MIGRATION_PLAN.md) for the full plan.

## Prerequisites

```sh
# pg_dump v16 (matches server)
brew install postgresql@16

# jq, curl (already standard)

# Env vars — copy to a local scratch file and source before running each script:
#
# Old team (AxiomFolio)
export AF_OLD_RENDER_KEY="rnd_Sfuuw..."                    # user's personal Render key
export AF_OLD_API_SERVICE_ID="srv-d64mkqi4d50c73eite20"
export AF_OLD_FRONTEND_SERVICE_ID="srv-d64mkhi4d50c73eit7ng"
export AF_OLD_WORKER_SERVICE_ID="srv-d64mkqi4d50c73eite10"
export AF_OLD_WORKER_HEAVY_SERVICE_ID="srv-d7hpo2v7f7vs738o9p80"
export AF_OLD_DB_ID="dpg-d725m719fqoc739rc3f0-a"
export AF_OLD_REDIS_ID="red-d64mkhi4d50c73eit7n0"
export AF_OLD_OWNER_ID="tea-d64meenpm1nc738rhdsg"
#
# New team (Paperwork)
export AF_NEW_RENDER_KEY="$(../../../paperwork/scripts/vault-get.sh RENDER_API_KEY)"
export AF_NEW_OWNER_ID="tea-d6uflspj16oc73ft6gj0"
# populated after Phase 1 (Blueprint launch):
# export AF_NEW_API_SERVICE_ID=srv-...
# export AF_NEW_FRONTEND_SERVICE_ID=srv-...
# export AF_NEW_WORKER_SERVICE_ID=srv-...
# export AF_NEW_WORKER_HEAVY_SERVICE_ID=srv-...
# export AF_NEW_DB_ID=dpg-...
# export AF_NEW_REDIS_ID=red-...
#
# Cloudflare (for DNS cutover — Phase 3)
export CLOUDFLARE_API_TOKEN="jTw..."                         # from infra/env.dev
export CLOUDFLARE_ZONE_ID="3a216b7e555bf74416b05f29a5c38a4c"
```

## Execution order

| # | Script | Phase | Downtime |
|---|--------|-------|---------:|
| 0 | _Manual: click "New → Blueprint" in Render dashboard (Paperwork team)_ | 1 | 0 |
| 1 | `discover-new-ids.sh` | 1 | 0 |
| 2 | `push-env-vars.sh` | 1 | 0 |
| 3 | `dump-old-db.sh` | 2 | starts |
| 4 | `restore-new-db.sh` | 2 | ongoing |
| 5 | `verify.sh <new-onrender-url>` | 2 | ongoing |
| 6 | `swap-custom-domains.sh` | 3 | ends |
| 7 | `verify.sh https://api.axiomfolio.com` | 3 | ended |

## Safety

- All destructive steps on the OLD team are additive-only until Phase 5 (decommission).
- DB dump/restore does NOT touch old DB (read-only `pg_dump`).
- Custom-domain swap is reversible within 2-10 min.
- Scripts are idempotent where possible (re-running won't duplicate env vars or domains).
