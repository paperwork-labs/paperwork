---
owner: infra-ops
last_reviewed: 2026-04-24
doc_kind: philosophy
domain: infra
status: active
---

# Infra Philosophy

Immutable rules for placing services, choosing vendors, and changing infrastructure. Edits require founder + `infra-ops` persona ack.

**Mutable architecture ("how"):** [`docs/INFRA.md`](../INFRA.md).

## TL;DR

1. **When we add a new service vs. reuse** — default is **do not** add; see [§2](#2-when-not-to-add-a-service). A new service needs compliance requirement, true blast-radius isolation, or 90-day run-rate cost proof — otherwise refactor in place.
2. **Non-negotiables** — [vendor exit path, SOC 2, per-env scoping (§5)](#5-vendor-doctrine); [Tier-1 / Tier-2](#1-tier-1-vs-tier-2-placement) placement and public-surface rules; [cost/blast & region-like moves (e.g. Render `region`, DNS) via escalation (§3)](#3-cost--blast-radius-escalation); we **will not** add Kubernetes, self-hosted LLM inference, or a bespoke time-series / search / queue layer [§7](#7-what-we-will-not-do).
3. **What requires founder sign-off** — [blast-radius 3+](#3-cost--blast-radius-escalation) (e.g. DNS, CDN, TLS, `cloudflared`), production DB schema (4+), vendor migrations (5+), and changes to *this* locked doc; [§4](#4-change-freeze-triggers) freezes; [§7 Friday deploy ban](#7-what-we-will-not-do).

## 1. Tier-1 vs Tier-2 placement

**Tier-1 (Render):** customer-facing APIs and frontends. Anything a user URL eventually hits in production.

**Tier-2 (Hetzner):** internal automation, batch workers, n8n, fleet of cron jobs, anything that can tolerate a cold restart. <!-- STALE 2026-04-24: "cluster" is misleading — n8n/Postiz run on the Hetzner VM stack in `infra/hetzner`, not a multi-node n8n cluster. -->

Rules:

- Tier-1 services MUST have a Render preview environment per PR. No "we'll test in prod."
- Tier-2 services MUST NOT be reachable from the public internet without `cloudflared` or equivalent reverse proxy. n8n is reverse-proxied, never exposed.
- A Tier-2 service that grows a customer-facing surface MUST be promoted to Tier-1. No "shadow Tier-1" on Hetzner.
- A Tier-1 service is never "demoted" to Tier-2 to save money. Either kill it or keep it on Render.

## 2. When NOT to add a service

Default answer to "should we add a new service?" is **no**. Adding a service is a choice with a 24-month ongoing tax (deploys, secrets, monitoring, on-call). The threshold to overcome is one of:

1. **Compliance** — a regulator requires it (e.g. EFIN MeF transmitter)
2. **Hard isolation** — blast radius of failure must be zero on existing services (e.g. trading execution worker)
3. **Cost** — projected cost of NOT having it (engineer time, latency, third-party fees) exceeds 6 months of run-rate within 90 days

If the answer is "I want a new service because the existing one feels messy," the answer is to refactor the existing service — not add a new one. We have already paid the tax on the existing one.

## 3. Cost & blast-radius escalation

Every infra change carries a blast-radius score:

| Score | Examples | Approval bar |
|---|---|---|
| 1 | env var change in Render preview | self-merge after CI |
| 2 | Render service config change (scaling, region) | infra-ops persona ack |
| 3 | DNS / CDN / TLS / cloudflared change | founder ack |
| 4 | Database schema change in production | founder + on-call human |
| 5 | Vendor migration (e.g. Render account move) | sprint-level event with documented rollback |

Brain auto-tags PRs with the implied blast-radius score from the diff (`scripts/blast_radius.py` — TODO).

## 4. Change-freeze triggers

We freeze infra changes (no merges that touch `infra/`, `apis/*/Dockerfile`, `render.yaml`, alembic chain, or `.github/workflows/`) when ANY of the following is true:

- A production incident is open in `#infra` (`P0` or `P1`)
- A pending Render account or vendor migration is in flight
- A trading market open / close window is < 60 minutes away (AxiomFolio-specific)
- The founder is asleep AND no on-call human is awake (cross-time-zone safety)

Freezes are explicit: an `infra-ops` persona Slack post saying "freeze on" / "freeze off" with a reason.

## 5. Vendor doctrine

We prefer vendors in this order, from most to least preferred:

1. **Render** for compute (Tier-1)
2. **Hetzner** for VMs (Tier-2)
3. **Postgres on Render** for OLTP, **Neon** for branched / preview DBs
4. **Cloudflare** for DNS, CDN, Workers, Tunnel, R2
5. **Anthropic + OpenAI + Google** for LLMs (multi-vendor mandatory; no single-vendor lock-in)
6. **Slack + Linear + GitHub** for collaboration / source control
7. **Stripe** for money
8. **Plaid + IBKR + broker direct APIs** for trading

We do not adopt a vendor that does not have:

- A documented exit path (export tools, no proprietary lock-in formats)
- Per-environment scoping (dev / preview / prod)
- An incident page
- A SOC 2 Type II report (or equivalent)

## 6. Secrets

- Every secret lives in **the Studio vault** (Postgres-backed, encrypted at rest). No secrets in `.env.local` checked into git, no secrets in Render dashboard env vars without the vault as the source of truth.
- Rotation is automated where possible (`ROTATION_BACKLOG.md`). Manual rotation is an infra-ops persona on-call task.
- Brain has read access to a SCOPED subset of secrets per persona. The CFO persona never sees broker credentials; the trading persona never sees Stripe webhook secrets.
- A leaked secret is a P0. The runbook (`docs/SECRETS.md`) is followed verbatim — no improvisation.

## 7. What we will NOT do

- We will **not** add Kubernetes. Render + Hetzner cover all cases. If we hit "we need k8s" the actual answer is "split the workload."
- We will **not** run our own LLM inference. Vendor LLMs only.
- We will **not** run our own time-series DB, search index, or queue. Use Postgres + Redis + cron until the pain is real.
- We will **not** ship to production on Friday after 12:00 PT without explicit founder ack.
- We will **not** let infra knowledge live only in one person's head. Every recurring task gets a runbook within 2 occurrences.

## 8. Monorepo dev stack rules

_(moved from [`INFRA`](../INFRA.md) on 2026-04-24)._

1. **One dev stack.** A single `docker compose -f infra/compose.dev.yaml up`
   boots every product — postgres, redis, all backends, all frontends. No
   per-product dev compose.
2. **One postgres, one redis.** Each product gets its own logical database
   (`axiomfolio_dev`, `brain_dev`, `filefree_dev`, `launchfree_dev`) on a
   single `postgres:17-alpine` instance. Each product gets its own redis
   logical DB index (`/0..3`).
3. **Opt-in extras are profiles.** Interactive Brokers gateway, Cloudflare
   tunnel, Celery Flower — all live behind `docker compose --profile`
   flags and in `infra/<product>/compose.profiles.yaml` overlays.
4. **Per-product infra lives under `infra/<product>/`.** Observability
   configs, env templates, profile overlays — everything that is
   product-specific but dev-infra-shaped.
5. **Render deploys are per-product `render.yaml`.** Each backend sets
   `rootDir: apis/<product>`; each frontend sets `rootDir: apps/<product>`.
   Dev compose and prod Render are independent orchestrations of the
   same monorepo.

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. Append-only.

### Amendments

- **2026-04-24** — [§8](#8-monorepo-dev-stack-rules) added; five dev-stack rules moved from [`docs/INFRA.md`](../INFRA.md) to keep INFRA as operational "how" and PHILOSOPHY as normative "why" + locked rules.
