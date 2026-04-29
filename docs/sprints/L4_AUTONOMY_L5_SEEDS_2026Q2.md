---
owner: engineering
last_reviewed: 2026-04-29
doc_kind: sprint
domain: company
status: shipped
sprint:
  start: 2026-04-28
  end: 2026-04-29
  duration_weeks: 0.3
  pr: 412
  prs: [364, 374, 375, 376, 377, 378, 379, 380, 382, 383, 384, 385, 386, 388, 389, 391, 392, 393, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412]
  ships: [brain, studio, filefree, axiomfolio, infra]
  personas: [orchestrator, agent-ops, infra-ops, brain-skill-engineer, ux-lead]
  plans:
    - docs/strategy/level_4_autonomy_+_platform.md
    - docs/STACK_AUDIT_2026-Q2.md
closes_pr_urls:
  - https://github.com/paperwork-labs/paperwork/pull/412
closes_workstreams:
  - WS-41-workstream-sprint-accuracy
  - WS-42-iac-drift-detector
  - WS-43-brain-freshness-surface
  - WS-44-brain-graduated-self-merge
  - WS-45-brain-kill-switch
  - WS-46-brain-auto-revert
  - WS-47-cf-per-zone-write-tokens
  - WS-48-apps-accounts-decommission
  - WS-49-stack-truth-audit
  - WS-50-anomaly-detection-writeback
  - WS-51-sprint-velocity-derive
  - WS-52-kg-self-validation
  - WS-53-slack-streamline-3-channels
  - WS-58-pwl-cli
  - WS-59-pwl-template-authoring-kit
  - WS-60-pwl-onboard-existing-apps
  - WS-61-objectives-yaml-manifest
  - WS-62-outcome-measurement-loop
  - WS-63-brain-self-prioritization
  - WS-64-brain-self-improvement-loop
  - WS-65-procedural-memory-consolidation
  - WS-66-paperwork-operating-score
  - WS-67-brain-coach-for-opus
  - WS-68-vercel-cost-bleed-stop
last_auto_status_check_at: null
---

# Level 4 Autonomy + L5 Self-Improvement Blitz — 2026-04-28/29

**Sprint window**: 2026-04-28 18:00 PT → 2026-04-29 09:55 PT (~16 working hours, ~36 PRs)
**Lead PR (closeout)**: [#412 (WS-57 batch A)](https://github.com/paperwork-labs/paperwork/pull/412)
**Result**: shipped — L4 platform handoff achieved (founder switches to product features); L5 seeds fully planted (Brain self-prioritizes, self-measures, self-improves).

## Goal

Take Paperwork Labs from L3 plumbing to **L4** (founder transitions to product features; Brain owns ops loop end-to-end) AND plant the **L5** (Brain proposes its own work, measures outcomes, ships improvements) seeds in the same blitz so the autonomy ladder bootstraps without waiting for a second sprint.

## Outcome

### L4 — founder hands ops to Brain

- **`pwl new-app <name>` CLI** scaffolds a new Paperwork app with Vercel project + DNS + Clerk + CI + runbook in one command (WS-58/59/60). Onboarded all 8 existing apps to the same template registry (`apis/brain/data/app_registry.json`).
- **Self-merge graduation** (WS-44): tier system in `apis/brain/data/self_merge_promotions.json`. Brain auto-promotes from data-only merges to brain-code after N=50 clean merges with zero unreverted reverts.
- **Kill switch** (WS-45) + **auto-revert** (WS-46): Brain pauses or reverts itself on incident.
- **Per-zone Cloudflare write tokens** (WS-47): least-privilege resolver `apis/brain/app/services/cloudflare_token_resolver.py` reduces blast radius from account-wide to single zone.
- **Apps/Accounts decommission framework** (WS-48): `apis/brain/data/decommissions.json` + runbook generator.
- **Anomaly detection** (WS-50): hourly z-score rolling baseline at `apis/brain/app/services/anomaly_detection.py`.
- **Sprint velocity** (WS-51): weekly metrics computed and surfaced in Studio admin tile.
- **KG self-validation** (WS-52): 6 rule classes daily-validated; high-severity violations block self-merge promotion.
- **Slack streamline** (WS-53): 3-channel + dedup + rate-limit + quiet-hours router landed as **dormant mirror engine** — strategic decision (2026-04-29) is to drop Slack entirely as primary surface; mirror code stays for optional opt-in.
- **Stack Truth Audit** (WS-49) → `docs/STACK_AUDIT_2026-Q2.md`: 32 KEEP / 30 UPGRADE / 3 REPLACE; ~80 person-days of upgrade scope.

### L5 — Brain bootstraps its own learning loop

- **OBJECTIVES.yaml** (WS-61): founder-written quarterly objectives at `docs/strategy/OBJECTIVES.yaml`; Brain reader decomposes into workstream candidates.
- **Outcome measurement** (WS-62): `apis/brain/data/pr_outcomes.json` records h1/h24/d7/d14/d30 success vs revert per merged PR.
- **Procedural memory consolidation** (WS-65): `apis/brain/data/procedural_memory.yaml` distilled "when X, do Y" rules. Hit 19 rules across 6 categories by close.
- **Self-prioritization** (WS-63): `apis/brain/app/services/self_prioritization.py` ranks workstream candidates daily.
- **Self-improvement loop** (WS-64): weekly retros at `apis/brain/data/weekly_retros.json` distill new procedural rules from outcome history.

### Bonus capabilities shipped same window

- **Paperwork Operating Score** (WS-66): 10-pillar composite 0–100 metric in `apis/brain/data/operating_score.json`. First recompute: 62.0/100 (autonomy + data architecture pillars are the lowest; founder has visibility for the first time).
- **Brain coach for Opus** (WS-67.A): `POST /api/v1/admin/coach/preflight` endpoint surfaces matching procedural rules before any planned action — the "smart check" pattern the founder explicitly requested.
- **Vercel cost bleed stop** (WS-68): `turbo-ignore` on all 8 apps + hourly billing monitor with 50/75/90/100% alerts. Caught and stopped a $36 → $47 spend escalation in real time.

## Tracks

| Track | What shipped | Key PRs |
|---|---|---|
| Phase A — Truth | WS-41 sprint accuracy, WS-42 IaC drift detector, WS-43 Brain freshness surface | #374 #382 #384 |
| Phase B — Hands | WS-44 graduated self-merge, WS-45 kill switch, WS-46 auto-revert | #377 #383 #391 |
| Phase C — Wallet | WS-47 per-zone CF tokens, WS-48 apps decommission framework | #401 |
| Phase A0 | WS-49 Stack Truth Audit | #389 |
| Phase D — Eyes+Voice | WS-50 anomaly, WS-51 sprint velocity, WS-52 KG validation, WS-53 Slack router | #399 #406 #404 #405 |
| Phase F — Platform | WS-58/59/60 `pwl` CLI + template kit + onboard existing | #388 #392 #395 |
| Phase G1 — L5 seeds parallel | WS-61 objectives, WS-62 outcomes, WS-65 procedural memory | #385 #378 #380 |
| Phase G2 — L5 seeds handoff | WS-63 self-prioritization, WS-64 self-improvement loop | #397 #398 |
| Bonus | WS-66 POS, WS-67 Brain coach, WS-68 cost bleed stop | #386 #393 #403 #408 #407 #409 |
| Closeout | Workstream truth sync; procedural rules for logs/Clerk/secrets defaults; WS-57 batch A deps | #410 #411 #412 |

## Strategic shifts captured during the blitz

These are **decisions made mid-flight** that change the next-phase plan:

1. **Drop Slack entirely as primary surface.** Studio PWA + Brain Conversations + web push (WS-53 dormant mirror engine) replaces it. Persona-validated 8/9 personas unaffected; EA persona migration pending.
2. **Drop n8n entirely.** Brain owns crons (already moved via Track K), webhook receivers, and adapter logic directly. ~$7-25/mo Render savings + ~3000 LOC deleted in upcoming PR J.
3. **Logs are first-class Brain data, not a SaaS purchase.** Codified in procedural memory as `brain_owns_logs_first_class_not_third_party_default`. WS-50 anomaly detection extends to log spikes; Studio surfaces a Logs tab.
4. **Email = Gmail SMTP, not SendGrid.** ~5 LOC. Founder's existing Gmail account.
5. **Clerk free plan stays.** `@paperwork-labs/auth-clerk` hides branding via CSS overrides. Pro budgeted into Year 2 when MAU growth makes it a TOS issue.
6. **Stack audit becomes recurring Brain capability.** Quarterly auto-run captured as WS-71 (newly added to roadmap).

## What we learned (consolidated retro)

- **Auto-merge guardrail violation** — PR #407 was auto-merged by github-actions[bot] despite explicit "do not merge" in babysit prompt. Root cause: babysitter enabled auto-merge instead of disabling it. Fix: procedural rule `babysit_agents_must_not_auto_merge` (added 2026-04-29).
- **Brain data dir path bug recurred 3x** (`operating_score.py`, `sprint_velocity.py`, `pr_outcomes.py`) — agents copied wrong pattern from peer files. Fix: procedural rule `brain_data_dir_traverses_three_levels`.
- **Cost guards must alert below cap, not at cap.** Vercel billing hit 91% with zero prior warning. Fix: monitor alerts at 50/75/90% per cycle (WS-68); procedural rule `cost_guards_must_alert_below_cap_not_at_cap`.
- **Vercel monorepo without turbo-ignore = every commit rebuilds every app.** Caused the 91% spend escalation. Fix: `turbo-ignore` in all 8 `vercel.json` files; procedural rule `vercel_monorepo_must_use_turbo_ignore`.
- **Cheap-agent merge orchestration via rebase queue works.** N parallel cheap agents touching `admin.py`, `schedulers/__init__.py`, `procedural_memory.yaml`, `workstreams.json` would deadlock without serialization. Pattern: each agent finishes and opens PR; orchestrator pulls next off queue and rebases; merge at queue head only.
- **Brain coach pattern** is the answer to "how does brain remember to do this for you" — pre-flight checklist endpoint surfaces matching procedural rules before any planned action. Foundation shipped in WS-67.A; wider rollout (Cursor rule wiring + auto-distillation) is WS-67.B/E.
- **Worktree isolation is non-negotiable for parallel cheap agents.** Sharing the orchestrator's working tree caused cross-branch untracked files. Fix: every cheap agent gets its own `git worktree` (rule `blast_radius_isolate_worktrees_for_parallel_dispatch`).
- **POS (Paperwork Operating Score) gives the company first-ever measurable health metric.** 62.0/100 today; lowest pillars are autonomy and data architecture. Brain self-prioritization (WS-63) will target lowest pillars first.

## Procedural rules added during blitz

| Rule | Source incident |
|---|---|
| `ruff_format_pre_push_guard` | PR #374 CI miss |
| `workstream_priority_unique` | PR #372/373 priority collisions |
| `cancelled_status_estimated_pr_count_null` | PR #372 schema reject |
| `vercel_design_storybook_known_failure` | PR #374 (storybook 10 / vite 8 / rolldown bug) |
| `medallion_tag_on_brain_service_files` | PR #377/380 medallion CI fails |
| `blast_radius_isolate_worktrees_for_parallel_dispatch` | hour 0–3 contention |
| `lighthouse_label_for_pr_perf_check` | POS pillar 4 |
| `a11y_label_for_pr_axe_check` | POS pillar 5 |
| `stack_audit_quarterly_refresh` | POS pillar 3 collector |
| `anomaly_alert_severity_threshold` | WS-50 design |
| `cloudflare_write_must_use_zone_resolver` | WS-47 design |
| `dora_metrics_freshness_24h` | POS pillar 2 collector |
| `brain_data_dir_traverses_three_levels` | recurring 3+ services |
| `vercel_monorepo_must_use_turbo_ignore` | WS-68 root cause |
| `cost_guards_must_alert_below_cap_not_at_cap` | WS-68 retro |
| `brain_must_act_as_opus_coach_for_recurring_failures` | founder ask → WS-67 |
| `kg_validation_runs_before_self_merge_promotion` | WS-52/44 wiring |
| `opus_offloads_mechanical_rebases_to_merge_orchestrator` | PR #401 retro |
| `babysit_agents_must_not_auto_merge` | PR #407 violation |
| `brain_owns_logs_first_class_not_third_party_default` | strategic decision |
| `clerk_free_plan_until_mau_scale_auth_clerk_shell` | strategic decision |
| `secrets_registry_hardening_ws57_batch_c` | strategic decision |

## Acceptance criteria — verdict

| L4 acceptance | Status |
|---|---|
| `pwl new-app` works end-to-end | ✅ WS-58/59/60 |
| `app_registry.json` is the manifest of monorepo apps | ✅ WS-60 |
| Single `#brain-asks` channel for escalations (or successor surface) | ⚠️ WS-53 mirror engine landed; founder pivoted to PWA+Conversations as primary; Slack drops |
| Founder can switch to product features without Brain breaking | ✅ all guardrails landed (kill switch, auto-revert, KG validation, anomaly, cost bleed stop, POS) |

| L5 acceptance | Status |
|---|---|
| `OBJECTIVES.yaml` exists, Brain reads it | ✅ WS-61 |
| Brain measures PR outcomes weekly | ✅ WS-62 |
| Procedural memory file with ≥10 rules | ✅ 22 rules |
| Brain proposes weekly workstream candidates | ✅ WS-63 |
| Brain ships self-improvement PRs (after track record) | ⏳ activates after 50 clean merges (WS-44 graduation gate) |

## What's NOT done (becomes Phase E + Phase H follow-up)

- **WS-54 Infrastructure Registry** — UI surface lives in IA reorg PR C; backend dispatchable.
- **WS-55 Runbook completeness audit** — cheap-agent dispatchable any time.
- **WS-56 Cost monitor unification** — partially in WS-68; needs LLM/Render unification (cheap-agent).
- **WS-57 batches B + C** — Node LTS upgrade, TS6, Zod4, uv migration, OpenAI SDK upgrade, Sentry rollout, secrets registry hardening, Postgres 18 plan, Render drift fix.
- **WS-67.B coach Cursor rule wiring** — Opus-side wrapper to call coach/preflight before any plan/dispatch.
- **WS-67.E auto-distillation** — weekly retro extension that turns 3+ same-root-cause incidents into new procedural rules automatically.
- **Phase H steady-state operation** — Brain runs the cycle indefinitely; founder writes quarterly OBJECTIVES.yaml only.

## How to read this in Studio

- `/admin/sprints` shows this sprint card pointing to PRs #364, #374-#412.
- `/admin/workstreams` shows 24 closed (Phase A..G2) and 3 remaining (WS-54/55/56) under Phase E.
- `/admin/operating-score` shows 62.0/100 with the autonomy + data architecture pillars lowest.
- `/admin/founder-actions` (or successor Conversations surface after IA reorg) shows pending founder review of `docs/STACK_AUDIT_2026-Q2.md` verdicts to greenlight WS-57 batches B+C.

## Provenance

- 36 merged PRs in the window
- 22 procedural rules added
- 16 workstream entries closed by truth-sync (PR #410)
- 9 workstream entries cancelled as superseded/deferred (PR #411 / this PR)
- 3 strategic decisions promoted to Brain procedural memory (logs, Clerk, secrets)
