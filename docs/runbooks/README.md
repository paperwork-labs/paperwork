# Runbooks

Operational runbooks live in this directory. [**Standard template**](_TEMPLATE.md) — category, owner, verification, rollback.

## Index by category

### Operations

- [`brain-deploy-recovery.md`](brain-deploy-recovery.md) — Brain merge-time guards (Alembic, Docker healthcheck, import paths).
- [`pre-deploy-guard.md`](pre-deploy-guard.md) — Vercel quota + env vars + Clerk DNS before production deploy.
- [`credential-access.md`](credential-access.md) — How Brain/agents fetch infra credentials programmatically.
- [`hetzner-bootstrap.md`](hetzner-bootstrap.md) — Provision and operate Paperwork Hetzner boxes (+ legacy VPS repurposing appendix).

### Incidents

- [`clerk-dns-incident-2026-04-28.md`](clerk-dns-incident-2026-04-28.md) — Clerk + Cloudflare DNS post-mortem (2026-04-28).

### Setup

- [`filefree-preview-clerk-envs.md`](filefree-preview-clerk-envs.md) — FileFree Clerk env vars across Vercel environments.
- [`email-deliverability.md`](email-deliverability.md) — SPF + DMARC for `paperworklabs.com`.
- [`pwl-cli.md`](pwl-cli.md) — Monorepo `pwl` CLI.

### Decommission

- [`cloudflare-zone-decommission.md`](cloudflare-zone-decommission.md) — Remove duplicate zones from legacy Cloudflare account.
- [`decommission-checklist.md`](decommission-checklist.md) — Generic domain/app decommission.
- [`n8n-deprecated-cleanup.md`](n8n-deprecated-cleanup.md) — **Deprecated** — historical n8n on Hetzner (n8n removed from prod automation).

### Brain

- [`brain-self-merge-graduation.md`](brain-self-merge-graduation.md)
- [`brain-self-prioritization.md`](brain-self-prioritization.md)
- [`brain-weekly-retro.md`](brain-weekly-retro.md)

### Infrastructure

- [`cloudflare-ownership.md`](cloudflare-ownership.md) — Work-account zones, migration reference, DNS ops, **per-zone API tokens**.
- [`launchfree-api-health.md`](launchfree-api-health.md) — LaunchFree `/health` checks.
