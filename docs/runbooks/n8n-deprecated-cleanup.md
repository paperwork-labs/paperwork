---
last_reviewed: 2026-05-02
doc_kind: runbook
status: deprecated
---

# Deprecated n8n Workflows (Hetzner) — Retired

> **Category**: decommission
> **Owner**: @infra-ops
> **Last verified**: 2026-05-02
> **Status**: deprecated (**n8n removed** from production automation — WS-69; this doc is archival only.)

**TL;DR:** Lists legacy Brain-mirror n8n flows that must stay off. Read before interpreting historical Hetzner notes or decommission inventories.

Historically **`hetzner-socials-repurpose.md`** tracked a plan to reinstall n8n for social automation — that playbook is **merged** into [`hetzner-bootstrap.md`](hetzner-bootstrap.md) under **Repurposing (legacy Social VPS)**.

## Deprecated status

Brain-mirror / Slack-era n8n automation was retired; monorepo **cron-shaped** workloads use **Brain APScheduler**. Read [`decommission-checklist.md`](decommission-checklist.md) for Slack + n8n decommission context.

## Workflows that were on the VPS (do not re-enable)

| Workflow (repo reference) | Role | Replacement |
|---------------------------|------|-------------|
| `brain-slack-adapter.json` | Routed Brain scheduler output to Slack via n8n webhook | **Conversations** + Gmail SMTP for high/critical; Slack codepaths removed |
| `error-notification.json` | Error alert formatter / Slack notifier | Brain-native alerting / Conversations |
| `infra-status-slash.json` | Slack `/infra` slash command | Studio **Architecture** / infra probes; Slack decommissioned for this path |

Historically, many **cron** workflows lived under `infra/hetzner/workflows/retired/` with explicit Brain scheduler replacements (see [N8N_DECOMMISSION_INVENTORY.md](../strategy/N8N_DECOMMISSION_INVENTORY.md)) — those JSON definitions are archival only and must not be re-imported as operational automation without a new design review.

## Operator notes

- **Do not** point production Brain `N8N_*` env vars at a legacy host — those integrations were stripped in WS-69.
- After cleanup on any leftover box, use [`hetzner-bootstrap.md`](hetzner-bootstrap.md#repurposing-legacy-social-vps) for repurposing procedural notes only.
