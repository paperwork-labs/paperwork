# infra/axiomfolio

AxiomFolio-specific dev infrastructure. The default dev stack (postgres, redis,
all backends, all frontends) lives in `infra/compose.dev.yaml` at the repo
root. This folder holds only what is specific to AxiomFolio.

See `docs/INFRA.md` for the full architecture.

## Contents

| Path                          | Purpose                                                                 |
| ----------------------------- | ----------------------------------------------------------------------- |
| `compose.profiles.yaml`       | Opt-in services: `ib-gateway` (ibkr), `cloudflared` (tunnel), `flower` (ops) |
| `env.examples/env.dev.example`| Documents AxiomFolio-specific dev env vars (broker tokens, flex query IDs, etc.) |
| `env.examples/env.prod.example`| Prod template (Render vars set via dashboard, this is for reference)  |
| `env.examples/env.test.example`| Pytest env template                                                   |
| _(observability)_             | OTel is in-app (`app/observability/tracing.py`); no external config files needed. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to ship spans. |

## Quick starts

```bash
# Default stack (no brokers, no tunnel):
docker compose -f infra/compose.dev.yaml up

# With IB Gateway:
docker compose -f infra/compose.dev.yaml \
               -f infra/axiomfolio/compose.profiles.yaml \
               --profile ibkr up

# With Cloudflare tunnel (OAuth dev testing):
docker compose -f infra/compose.dev.yaml \
               -f infra/axiomfolio/compose.profiles.yaml \
               --profile tunnel up

# With Celery Flower UI (task monitor):
docker compose -f infra/compose.dev.yaml \
               -f infra/axiomfolio/compose.profiles.yaml \
               --profile ops up
```

## Connection strings (shared dev stack)

AxiomFolio connects to the shared services on their dev defaults:

| Service      | URL from inside a container                                       |
| ------------ | ----------------------------------------------------------------- |
| postgres     | `postgresql://paperwork:paperwork_dev@postgres:5432/axiomfolio_dev` |
| redis        | `redis://redis:6379/3`                                            |
| celery broker| `redis://redis:6379/3`                                            |

The postgres role `paperwork` owns every product's DB in dev — this is a
dev-only convenience. Production Render deploys use per-service managed
databases with scoped roles (see `apis/axiomfolio/render.yaml`).

## Why opt-in profiles?

- **`ibkr`** — Interactive Brokers gateway needs your IBKR creds and
  takes ~60 s to warm up. Don't boot it unless you're testing live quotes
  or order placement.
- **`tunnel`** — Cloudflare tunnel opens a public URL to your local dev
  backend. Only needed for OAuth callback testing (Schwab, Google SSO).
- **`ops`** — Flower surfaces Celery task state. Useful for debugging
  but adds an extra container.

## What's NOT here (and why)

- **`compose.dev.yaml`** — superseded by root `infra/compose.dev.yaml`
  which now owns `api-axiomfolio`, `celery-axiomfolio-worker`, and
  `celery-axiomfolio-beat`. Kept in git history (`git log -- infra/axiomfolio/compose.dev.yaml`).
- **`compose.test.yaml`** — superseded. Tests now run against the shared
  `postgres` container using the `axiomfolio_test` DB, matching the
  filefree/brain pattern.
- **Backend source code** — lives at `apis/axiomfolio/app/`.
- **Frontend source code** — lives at `apps/axiomfolio/`.
- **Docs** — live at `docs/axiomfolio/`.
