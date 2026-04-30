---
owner: founder
last_reviewed: 2026-04-29
doc_kind: strategy
domain: paperwork-labs
status: living
---

# Day-0 Founder Actions Worksheet (WS-76)

This worksheet is the single source of truth for founder-owned setup that can run in parallel with engineering. Most items are account, OAuth, or vendor steps that do not block code merge but do block product loops when missing. **Voice corpus export** is the rate-limiting step for founder-voice and viral content work: start it in week one so tone and clip pipelines are not idle waiting on content.

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

> **TODO (WS-76):** Register Brain audit `founder_actions_pending` (weekly cadence; count open checkboxes) in `audit_registry.json` seed when a lightweight runner exists.
