---
owner: founder
last_reviewed: 2026-04-30
doc_kind: strategy
domain: paperwork-labs
status: living
---

# Day-0 Founder Actions Worksheet (WS-82)

**TL;DR:** Founder checklist for WS-82 setup. Open it for Wave 0 items (urgent), Week 1 critical path, vendor setups, and the `axiomfolio-frontend` retirement steps.

This worksheet is the single source of truth for founder-owned setup. Two tiers: **WS-82 Wave 0 P0** items are bleeding wounds — do today. **Critical path** items run in parallel to engineering through Week 1.

## WS-82 Wave 0 P0 — ALL COMPLETED (2026-04-30)

### A0. AxiomFolio DNS — DONE ✓
- Deleted old A records pointing to Cloudflare proxied IPs (Error 1000 resolved)
- Set `axiomfolio.com` A record → `76.76.21.21` (Vercel), DNS only
- Set `www.axiomfolio.com` CNAME → `cname.vercel-dns.com`, DNS only
- Added domain to axiomfolio Vercel project
- Added env vars: `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `BRAIN_API_URL`, `BRAIN_API_SECRET`
- Site now live at https://axiomfolio.com

### A1. Brain Render env vars — DONE ✓
- Added `VERCEL_API_TOKEN` to brain-api via Render API

### Item 19: Studio env vars — DONE ✓
- Added `VERCEL_MONOREPO_PROJECT_NAMES` to Studio via Vercel CLI

---

## Critical path (do these in Week 1, parallel to engineering)

| # | Action | Time | Unblocks | ☐ |
|---|--------|------|----------|---|
| 1 | Voice corpus export — 50-100 LinkedIn + X posts to `apis/brain/data/voice_corpus/sankalp/raw/` | 1hr | PR-32, PR-35, PR-36, PR-38, PR-39 | ☐ |
| 2 | VAPID key generation (web push) | 5min | PR-2, PR-4 | ☐ |
| 3 | Gmail app password | 5min | PR-2, PR-4 | ☐ |
| 4 | Olga Clerk provisioning | 10min | PR-4, PR-28 | ☐ |
| 5 | Vercel team budget cap | 5min | PR-4, PR-10 | ☐ |
| 6 | Cancel Slack workspace | 2min | Wave 0 | ☐ |
| 7 | Cancel ngrok subscription (if active) | 2min | PR-11 | ☐ |
| 8 | Genre catalog ratification (pick 1 starting viral genre) | 30min | PR-38 | ☐ |

## Vendor account setups (when their PR opens)

| # | Action | Time | Unblocks | ☐ |
|---|--------|------|----------|---|
| 9 | Postproxy/Late vendor account + first OAuth | 1hr | PR-31 | ☐ |
| 10 | Opus Clip Pro account + API key | 15min | PR-35 | ☐ |
| 11 | Apify account + first actor enable | 30min | PR-37 | ☐ |
| 12 | Cloudflare Tunnel + Zero Trust dual-app | 1hr | PR-30 | ☐ |
| 13 | Hetzner pre-snapshot before n8n reinstall | 15min | PR-30 | ☐ |
| 14 | Google Calendar OAuth scopes | 15min | PR-17a | ☐ |
| 15 | Stripe MRR webhook to Studio | 30min | PR-24b | ☐ |
| 16 | PostHog project key + funnels seeded | 1hr | PR-24b | ☐ |
| 17 | Viral account handle reservation (TikTok + IG + X + Threads) | 1hr | PR-38 | ☐ |

### Item 18 — Retire `axiomfolio-frontend` Render static site

<a id="item-18-retire-axiomfolio-frontend-render-static"></a>

Post–WS-02 cutover, the AxiomFolio frontend lives on **Vercel**. The legacy Render **static_site** `axiomfolio-frontend` should be deleted to stop failed builds and billing noise.

1. `render services list --output json | jq '.[] | select(.name == "axiomfolio-frontend")'`
2. `render services delete <service-id>` (confirm workspace)

> **TODO (WS-76):** Register Brain audit `founder_actions_pending` (weekly cadence; count open checkboxes) in `audit_registry.json` seed when a lightweight runner exists.
