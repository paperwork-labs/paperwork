---
last_reviewed: 2026-05-01
---

# Hetzner VPS — Social Automation Repurpose

**TL;DR:** Plan to clean legacy n8n on the Hetzner box, reinstall for social automation behind Cloudflare Tunnel, then wire Wave M. Use during PR-11 / PR-30 / Wave M work.

**Owner:** ops-engineer  
**Last updated:** 2026-04-30  
**Related:** [n8n deprecated cleanup](./n8n-deprecated-cleanup.md), [decommission checklist](./decommission-checklist.md) (Slack + n8n section)

## Context

- **VPS:** Hetzner CX22 (~$7/mo), historically hosting deprecated **Brain-mirror** n8n workflows (Slack adapter, error notifications, infra slash command).
- **Decision:** **REPURPOSE** (not shutdown) — the same box will host a **fresh** n8n stack for **social content automation** (Wave M).
- **Exposure:** UI and webhooks secured via **Cloudflare Tunnel** + **Zero Trust** (no public n8n ports).

## Phase 1: Cleanup (PR-11)

Operational checklist; execute in order when taking the box from legacy Brain-mirror mode into a clean slate.

- [ ] Take VPS snapshot (insurance backup).
- [ ] Stop and remove deprecated n8n containers (and orphan volumes if safe).
- [ ] Remove deprecated Brain-mirror workflow configs from disk (see [n8n-deprecated-cleanup.md](./n8n-deprecated-cleanup.md)).
- [ ] Document current VPS state: `docker ps -a`, disk use, open ports (should be minimal pre-tunnel), kernel/hostname, and snapshot ID.

## Phase 2: Fresh Install (PR-30)

- [ ] **Docker Compose:** fresh n8n + Cloudflare Tunnel sidecar (or separate tunnel container) with pinned image tags.
- [ ] **Cloudflare Zero Trust:** public hostname for operator UI (subdomain) + separate hostname for webhooks (narrow access / WAF as needed).
- [ ] **Backups:** daily export of n8n data (workflows + credentials metadata) to **Cloudflare R2** (or agreed object store).
- [ ] **Health check:** lightweight HTTP endpoint (n8n health or sidecar `/health`) monitored from Brain or external probe.

## Phase 3: Social Wiring (Wave M)

- [ ] Connect n8n to social platform APIs (tokens in Vault / n8n credential store).
- [ ] Wire **Brain → n8n** publishing pipeline (webhook or queue contract TBD in Wave M spec).
- [ ] Set up content queue + scheduling (cadence, idempotency, failure alerts via Conversations or email).

## Access

- **SSH:** documented in Vault (Hetzner project + host key pinning as per team practice).
- **Dashboard:** via Cloudflare Tunnel hostname **after Phase 2** (not via raw public IP).

## Rollback

- If repurpose fails mid-flight, restore from the Phase 1 snapshot and keep legacy stack **stopped** until a second maintenance window.
