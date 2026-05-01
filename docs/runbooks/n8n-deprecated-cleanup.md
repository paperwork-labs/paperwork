---
last_reviewed: 2026-05-01
---

# Deprecated n8n Workflows (Hetzner) — Retired

**TL;DR:** Lists legacy Brain-mirror n8n flows that must stay off. Read before touching the Hetzner n8n host or Wave M social automation.

**Status:** **RETIRED** (Brain-mirror / Slack-era automation)  
**Last updated:** 2026-04-30  
**Context:** Monorepo automation for Paperwork’s **cron-shaped** workloads moved to **Brain APScheduler**. Slack outbound and n8n Brain integration were removed in **WS-69 PR J** (see [decommission-checklist.md](./decommission-checklist.md)). The **Hetzner** n8n instance may still have held copies of these workflows until **Phase 1** of [hetzner-socials-repurpose.md](./hetzner-socials-repurpose.md) runs.

## Workflows that were on the VPS (do not re-enable)

| Workflow (repo reference) | Role | Replacement |
|---------------------------|------|-------------|
| `brain-slack-adapter.json` | Routed Brain scheduler output to Slack via n8n webhook | **Conversations** + Gmail SMTP for high/critical; Slack codepaths removed |
| `error-notification.json` | Error alert formatter / Slack notifier | Brain-native alerting / Conversations |
| `infra-status-slash.json` | Slack `/infra` slash command | Studio **Architecture** / infra probes; Slack decommissioned for this path |

Historically, many **cron** workflows lived under `infra/hetzner/workflows/retired/` with explicit Brain scheduler replacements (see [N8N_DECOMMISSION_INVENTORY.md](../strategy/N8N_DECOMMISSION_INVENTORY.md)) — those JSON definitions are archival only and must not be re-imported as operational automation without a new design review.

## Operator notes

- **Do not** point production Brain `N8N_*` env vars at this host for legacy mirroring — those integrations were stripped in PR J.
- After cleanup, treat the box as **empty slate** for **Wave M** social n8n only ([hetzner-socials-repurpose.md](./hetzner-socials-repurpose.md)).
