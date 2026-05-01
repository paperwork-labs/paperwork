---
last_reviewed: 2026-05-01
---

# Handoff — End of L4/L5 Blitz Chat → New Work

**Date**: 2026-04-29
**From**: orchestrator chat that ran the 48-hour Level 4 / Level 5 blitz + Vercel cost crisis + strategic shift to Brain-first / Studio-PWA / drop Slack-and-n8n
**To**: (1) Studio IA reorg + UX expense-reporting chat (already in flight); (2) any future operator/agent picking up Phase E remainder

This is the last document this chat needs to leave behind. Everything in here is verified against `git log origin/main` and the schemas in `apis/brain/app/schemas/`.

---

## What got done in this chat

### L4 platform handoff — ✅ achieved

Brain owns the ops loop end-to-end. Founder can move to product features.

- **`pwl new-app` CLI** scaffolds new Paperwork app in one command (Vercel project + DNS + Clerk + CI + runbook). All 8 existing apps onboarded to the same template registry (`apis/brain/data/app_registry.json`).
- **Self-merge graduation** with kill switch + auto-revert + KG self-validation — Brain auto-promotes from data-only merges to brain-code after 50 clean merges with zero unreverted reverts.
- **Per-zone Cloudflare write tokens** (least-privilege resolver) — blast radius reduced from account-wide to single zone.
- **Anomaly detection** (z-score, hourly), **sprint velocity** (weekly), **POS pillar collectors** (10-pillar composite) all live.
- **Vercel cost bleed stop** — `turbo-ignore` on all 8 apps + hourly billing monitor with 50/75/90/100% alerts (caught $36 → $47 escalation in real time).
- **Stack Truth Audit** at `docs/STACK_AUDIT_2026-Q2.md` — 32 KEEP / 30 UPGRADE / 3 REPLACE. WS-57 batch A landed (PR #412). Batches B + C are the remaining stack work.

### L5 self-improvement seeds — ✅ planted

- **OBJECTIVES.yaml** at `docs/strategy/OBJECTIVES.yaml` — Brain reads + decomposes.
- **Outcome measurement** — `apis/brain/data/pr_outcomes.json` records h1/h24/d7/d14/d30 success vs revert per merged PR.
- **Procedural memory** — 22 "when X, do Y" rules at `apis/brain/data/procedural_memory.yaml`.
- **Self-prioritization + weekly retros** — `apis/brain/data/workstream_candidates.json` + `weekly_retros.json` — Brain ranks daily, retros weekly, distills new rules.
- **Brain coach for Opus (WS-67.A)** — `POST /api/v1/admin/coach/preflight` surfaces matching procedural rules before any planned action. The "smart check" pattern.

### Strategic shifts captured

These were **decisions made mid-flight** that change the next-phase plan. All are codified in `apis/brain/data/procedural_memory.yaml` so they survive context switches.

1. **Drop Slack entirely as primary surface.** Studio PWA + Brain Conversations + web push replaces it. WS-53 mirror engine stays as dormant code; not the primary surface. Rule: implicit in WS-70.
2. **Drop n8n entirely.** Brain owns crons (already moved via Track K), webhook receivers, and adapter logic directly. ~$7-25/mo Render savings + ~3000 LOC deleted in WS-70.
3. **Logs are first-class Brain data, not a SaaS purchase.** Codified as `brain_owns_logs_first_class_not_third_party_default`. Studio surfaces a Logs tab; high-severity log matches fan out via web push.
4. **Email = Gmail SMTP, not SendGrid.** ~5 LOC. Captured as WS-72.
5. **Clerk free plan stays until ~10k MAU.** Codified as `clerk_free_plan_until_mau_scale_auth_clerk_shell`. `@paperwork-labs/auth-clerk` hides branding via CSS overrides.
6. **Stack audit becomes recurring Brain capability.** Captured as WS-71.
7. **Babysit agents must NOT auto-merge.** PR #407 was auto-merged against explicit instructions. Codified as `babysit_agents_must_not_auto_merge`.

---

## What "Phase E" means after the strategic pivot

Phase E was originally:

| WS | Original framing | Updated framing |
|---|---|---|
| WS-54 Infrastructure Registry | New backend + new Studio surface | UI surface lives in IA reorg PR C; backend dispatchable as cheap-agent |
| WS-55 Runbook completeness audit | Cheap-agent audit pass | Unchanged; cheap-agent dispatchable any time |
| WS-56 Cost monitor unification | Unified cost dashboard | Partly delivered by WS-68 (Vercel); remaining: LLM (Anthropic/OpenAI/Gemini) + Render unification |
| WS-57 Stack audit upgrade PRs | Big batch | Batch A merged PR #412; batches B + C remain (WS-73) |

**Phase E is no longer a sprint** — it's a small backlog of dispatchable cheap-agent work. The actual next major sprint is the Studio IA reorg (WS-69) which consumes WS-54's surface and reframes everything around Brain-as-engine.

---

## Forward backlog (registered as workstreams)

| WS | What | Owner | Where it lives |
|---|---|---|---|
| **WS-54** Infrastructure Registry (backend) | Brain endpoint + JSON store of every prod surface | Brain self | dispatchable any time |
| **WS-55** Runbook completeness audit | Walk every runbook and flag missing sections | Brain self | dispatchable any time |
| **WS-56** Cost monitor unification | Add LLM + Render cost monitors with same alert pattern as WS-68 | Brain self | dispatchable any time |
| **WS-57 / WS-73** Stack upgrade batches B + C | Node LTS, TS6, Zod4, OpenAI SDK, Sentry rollout, Storybook+Vite repair, Langfuse v4, uv migration, httpx unification, Postgres 18 plan, Render drift fix, secrets registry hardening, deployment placeholder cleanup | Brain self | dispatchable in two waves |
| **WS-67.B** Brain-coach Cursor rule wiring | Opus-side wrapper to call coach/preflight before any plan/dispatch | orchestrator | this chat or new chat |
| **WS-67.E** Auto-distillation | Weekly retro extension that turns 3+ same-root-cause incidents into new procedural rules automatically | Brain self | after WS-67.B |
| **WS-69** Studio IA reorg + expense reporting | 8-PR plan in `/Users/paperworklabs/.cursor/plans/studio_ia_reorg_plan_2033873b.plan.md` | UX chat (you) | active |
| **WS-70** Slack + n8n full decommission | After WS-69 + PWA push prove out for 1 week | Brain self / orchestrator | sequence after WS-69 |
| **WS-71** Recurring stack audit | Quarterly cron walks deps + writes `STACK_AUDIT_<year>-Q<quarter>.md` | Brain self | dispatchable any time |
| **WS-72** Gmail SMTP fallback | ~5 LOC for severity:high notification fallback | Brain self | dispatchable any time |

Every one of these is in `apps/studio/src/data/workstreams.json` and validates against `WorkstreamsFile`. They're discoverable in Studio admin.

---

## What this chat is **not** taking forward

Cleared from `workstreams.json` because superseded or completed-via-other-channel:

| WS | Reason cleared |
|---|---|
| WS-15 Accounts app build | Strategy dropped — auth lives per-app via `@paperwork-labs/auth-clerk` |
| WS-18 Brain prod-enable | Superseded — ambient learning shipped via WS-62/64/65/66/67 |
| WS-20 Track M theme migration | Superseded — Track M tokens shipped per-app via brand canon PRs |
| WS-21 Brand iteration | Brand canon locked PR #197/198; ongoing not a workstream |
| WS-24 Track I3 GitHub webhook secret | Founder action via Render dashboard (no code change tracked) |
| WS-26 Track L secrets rotation | Folded into WS-57 batch C secrets registry hardening |
| WS-36 Decommission accounts-app Vercel | Done by virtue of WS-15 cancellation |
| WS-38 Tighten DMARC p=reject | Moves to ops calendar; no code workstream needed |
| WS-39 CF per-zone readonly tokens | Superseded by WS-47 (write tokens) |
| WS-40 Decommission old CF personal | Founder action via Cloudflare dashboard |

---

## Open founder decisions (none blocking)

| Decision | Status |
|---|---|
| Vercel team on-demand budget = $0 | **Founder action**: set in https://vercel.com/paperwork-labs/~/settings/billing → Spend Management |
| Greenlight stack-audit verdicts to start WS-73 (batches B + C) | **Founder action**: `docs/STACK_AUDIT_2026-Q2.md` table is the green-light list |
| Generate Gmail app password for WS-72 SMTP fallback | 5-min founder action, blocks WS-72 |
| Provision Olga in Clerk → Studio admin → PWA install | Day-0 of WS-69 PR I (push) → WS-70 (Slack disconnect) |

Everything else was decided data-driven in this chat per the L4 plan's rule #1 (founder decisions empty by default).

---

## What lives where now

| Concern | Source of truth |
|---|---|
| Workstream backlog | `apps/studio/src/data/workstreams.json` (validated by `WorkstreamsFile`) |
| Sprint logs | `docs/sprints/*.md` — including new `L4_AUTONOMY_L5_SEEDS_2026Q2.md` covering all 24 closed WS |
| Strategic plans | `docs/strategy/*.md` + `/Users/paperworklabs/.cursor/plans/*.plan.md` |
| Stack audit | `docs/STACK_AUDIT_2026-Q2.md` (recurring → WS-71) |
| Brain operating doctrine | `apis/brain/data/procedural_memory.yaml` (22 rules) |
| Founder objectives | `docs/strategy/OBJECTIVES.yaml` |
| Brain self-improvement loop data | `apis/brain/data/{pr_outcomes,self_merge_promotions,workstream_candidates,weekly_retros,operating_score,kg_validation,anomaly_alerts,sprint_velocity}.json` |

---

## How to read this in Studio

After PR #410 (status truth-sync) and this PR land:

- `/admin/sprints` — new card "Level 4 Autonomy + L5 Self-Improvement Blitz — 2026-04-28/29" lists all 24 closed workstreams.
- `/admin/workstreams` — board now shows 45 completed + 9 cancelled + 3 remaining Phase E + 5 forward (WS-69..73). Cancelled entries reflect supersedence reasons in their notes.
- `/admin/operating-score` — 62.0/100 with autonomy and data-architecture pillars lowest; Brain self-prioritization will target lowest pillars.
- `/admin/founder-actions` (or successor Conversations surface after WS-69) — founder decisions list above.

---

## Single-line directive for the IA reorg chat

> Workstream backlog is now truthful in main. Phase E is just WS-54..WS-56 + WS-73 (cheap-agent dispatchable; not part of your IA work). Your scope is WS-69 (IA reorg + expense reporting) which sequences before WS-70 (Slack + n8n full decommission). Brain procedural memory rules `brain_owns_logs_first_class_not_third_party_default`, `clerk_free_plan_until_mau_scale_auth_clerk_shell`, `secrets_registry_hardening_ws57_batch_c` are authoritative — don't relitigate. Day-0 founder actions: VAPID keys, Olga Clerk provisioning, Gmail app password.

---

This chat is now **done**. Anything new opens a new chat.
