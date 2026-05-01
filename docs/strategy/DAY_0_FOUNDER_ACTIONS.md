---
owner: founder
last_reviewed: 2026-04-30
doc_kind: strategy
domain: paperwork-labs
status: living
---

# Day-0 Founder Actions Worksheet (WS-82)

This worksheet is the single source of truth for founder-owned setup. Two tiers: **WS-82 Wave 0 P0** items are bleeding wounds — do today. **Critical path** items run in parallel to engineering through Week 1.

## WS-82 Wave 0 P0 (DO TODAY — bleeding wounds)

These require dashboard clicks. All other Wave 0 PRs are running via cheap agents.

### A0. AxiomFolio login + DNS (Error 1000 blocking axiomfolio.com)

**Render env vars (axiomfolio-api service)** — needed for Clerk auth:
1. Render Dashboard → axiomfolio-api → Environment
2. Add `CLERK_JWT_ISSUER` = (Clerk → API Keys → Frontend API URL — copy the `https://...clerk.accounts.dev` or production Clerk URL)
3. Add `CLERK_SECRET_KEY` = (Clerk → API Keys → Secret keys → copy production key)
4. Save → service auto-redeploys

**Cloudflare DNS (axiomfolio.com)**:
1. Cloudflare Dashboard → axiomfolio.com → DNS
2. Delete any A records for `@` or `axiomfolio.com` that point to Cloudflare IPs (162.159.x.x, 172.66.x.x — these cause Error 1000)
3. Set apex `A` → `76.76.21.21` (Vercel anycast IP), Proxy status: **DNS only** (gray cloud)
4. Set `www` `CNAME` → `cname.vercel-dns.com`, Proxy status: **DNS only**
5. Wait ~2min then test: `dig axiomfolio.com +short` should return `76.76.21.21`
6. Browser test: `https://axiomfolio.com` should load

### A1. Brain Render env vars (for quota monitoring)

**Render Dashboard (brain-api service)**:
1. Render Dashboard → brain-api → Environment
2. Add `VERCEL_API_TOKEN` = (Vercel → Account Settings → Tokens → create "brain-api-quota-monitor")
3. Add `RENDER_API_KEY` = (Render → Account Settings → API Keys → create "brain-api-quota-monitor")
4. Save → service auto-redeploys

---

## DONE via CLI (2026-04-30)

- **Item 19**: `VERCEL_MONOREPO_PROJECT_NAMES` set on Studio via `vercel env add`

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
