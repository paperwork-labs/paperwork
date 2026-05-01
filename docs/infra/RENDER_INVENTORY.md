---
owner: infra-ops
last_reviewed: 2026-04-30
doc_kind: reference
domain: infra
status: active
---
# Render Inventory — 2026-04-30

**Owner**: `infra-ops` persona.
**Workspace**: `tea-d6uflspj16oc73ft6gj0` (Paperwork team, `billing@paperworklabs.com`).

## Live Services

| Service | Type | ID | Repo | Dockerfile / Runtime | Plan | Status |
|---|---|---|---|---|---|---|
| `brain-api` | web | `srv-d74f3cmuk2gs73a4013g` | `paperwork-labs/paperwork` | `apis/brain/Dockerfile` | starter | running |
| `filefree-api` | web | `srv-d70o3jvkijhs73a0ee7g` | `paperwork-labs/paperwork` | python (FastAPI) | starter | running |
| `axiomfolio-api` | web | `srv-d7lg0o77f7vs73b2k7m0` | `paperwork-labs/paperwork` | `apis/axiomfolio/Dockerfile` | standard | running |
| `axiomfolio-worker` | worker | `srv-d7lg0o77f7vs73b2k7lg` | `paperwork-labs/paperwork` | `apis/axiomfolio/Dockerfile` | standard | running |
| `axiomfolio-worker-heavy` | worker | `srv-d7lg0o77f7vs73b2k7kg` | `paperwork-labs/paperwork` | `apis/axiomfolio/Dockerfile` | standard | running |

## Data Stores

| Name | Type | ID | Plan | Status |
|---|---|---|---|---|
| `axiomfolio-db` | postgres 18 | `dpg-d7lg0e77f7vs73b2k220-a` | basic_1gb (15 GiB) | available |
| `axiomfolio-redis` | keyvalue (Redis 8.1.4) | `red-d7lg0dv7f7vs73b2k1t0` | starter | available |

## Decommissioned Services

| Service | Decommission Date | Notes |
|---|---|---|
| `axiomfolio-frontend` | 2026-04-30 | Migrated to Vercel (`apps/axiomfolio`) |
| `launchfree-api` | 2026-04-25 | Commented out in `render.yaml`; backend not yet wired |

## Health Endpoints

```bash
https://brain-api-zo5t.onrender.com/health
https://filefree-api-5l6x.onrender.com/health
https://axiomfolio-api-02ei.onrender.com/health
```

## Related

- `render.yaml` — consolidated blueprint (source of truth)
- `docs/infra/RENDER_REPOINT.md` — repointing runbook
- `docs/infra/RENDER_QUOTA_AUDIT_2026Q2.md` — cost analysis
