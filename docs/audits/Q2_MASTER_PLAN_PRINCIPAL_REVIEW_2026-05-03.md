# Q2 Master Plan — Principal Engineer Review

**Reviewer**: Principal/Staff Engineer (Opus orchestrator, single-session review)
**Plan reviewed**: `~/.cursor/plans/paperwork_2026q2_master_plan_f9ce7c63.plan.md` — 5 tracks, ~46 workstreams, 10-12 weeks
**Date**: 2026-05-03
**Inputs consumed**: master plan, BRAIN_ARCHITECTURE.md (D1-D76, 2898 lines), strategy lock doc §0, bible gap audit (606 lines), 5 wave-1 audits, 2 superseded locked plans, 8 `.cursor/rules/*.mdc` files, repo state inspection (migrations, workflows, admin pages, snapshot files, scheduler init, workstream schema, main.py)

---

## 1. Executive Verdict

**Ship after fixes — 12 findings, 5 of which are P0 (must fix before kickoff).**

The plan is the right plan for this codebase. It correctly synthesizes the bible gap audit, the wave-1 code audits, and the strategy lock into a single execution document. The track structure (Make Brain Real → Company OS Surfaces → Infra Truth → B2B-Ready Spine → L4+L5 Autonomy) is the right sequencing. The single biggest risk if executed as written: **the Conversations canonical-persistence split-brain (JSON-on-disk + SQLite FTS as the source of truth, Postgres as a mirror) is never called out as a P0 fix, and it will silently corrupt or lose data when Render's ephemeral disk recycles.** This is not in any workstream. It is a data-loss risk on the founder's most-used surface. Every Track 2 "wire surface to Brain" story implicitly assumes Brain endpoints return coherent data from Postgres, but for Conversations — the only surface the founder uses daily — they don't. Fix this or nothing else matters.

---

## 2. What's Strong

- **Bible-to-plan traceability is excellent.** Every workstream cites its doctrine (D##) and audit (T##) reference. This is unusual for a plan this large and means the founder can verify any workstream's justification in <60 seconds.

- **The D65 surface coverage matrix (plan lines 117-131) is the right artifact.** Turning the bible gap audit's Tier 5 matrix into a workstream-by-workstream execution plan is exactly how you close the "half-wired features" pattern. Most teams never do this; this plan does it systematically.

- **Deferred scope is honestly labeled (plan lines 314-325).** The plan explicitly names what it's NOT building (public landing, Stripe Checkout, SOC-2, white-label, multi-tenant signup, customer success). This prevents scope creep from good intentions. The §0.5 trigger gate is a clean decision boundary.

- **The critical path Mermaid diagram (plan lines 248-278) captures the real dependency chain.** T1.0 → T1.2 → T4.1/T5.1 is correct. The plan avoids the common trap of showing everything as parallel when it isn't.

- **Wave K shared Python packages are already built (repo confirms 107 files under `packages/python/`).** The plan at T5.1-T5.3 assumes these exist, and they do. `data-engine`, `mcp-server`, `api-foundation`, `clerk-auth`, `money`, `observability`, `rate-limit`, `pii-scrubber` are all scaffolded with tests. This means T5.1 (kill FileFree tax-data duplicate) and T5.3 (extract mcp-server) are smaller than "L"-sized — they're closer to "M" because the package shells exist.

- **The milestone acceptance gates (plan lines 284-310) are specific and testable.** "5 consecutive Render deploys green" (T3.7), "13 snapshot JSON files deleted" (T2.10), "usage_meter accruing rows" (T4.4) — these are verifiable in <5 minutes each.

- **The cheap-agent cost budget ($170-250 plan line 334) is realistic** for ~46 workstreams at the S/M sizes dominating the plan.

---

## 3. What's Wrong

### F1. P0 — Conversations canonical persistence is JSON-on-disk + SQLite FTS, not Postgres. No workstream addresses this.

**Track + workstream affected**: ALL of Track 2 (Company OS Surfaces), specifically T2.5 (Conversations polish), but really a prerequisite for the entire plan.

**Specific gap**: Wave-1 audit `conversations-threads.md` (conv-gap-2, severity: high) is explicit: "Postgres conversations schema is mirror-only; canonical threads live on disk JSON + FTS, diverging from Alembic 012 narrative." `apis/brain/app/services/conversations.py` lines 3-5 say it plainly: "Persistence: JSON files at apis/brain/data/conversations/<id>.json with a sidecar SQLite FTS5 index." Render has ephemeral disk. If Brain redeploys or the container restarts, every conversation that hasn't been mirrored to Postgres is gone. The plan treats Conversations as "ok" in the coverage matrix (line 124) and gives it T2.5 (S, P2 — "unflag feature flag + polish"). This is not polish; this is a data-loss risk on the founder's only daily-use surface.

**Concrete fix**: Add **T1.0d** (P0, M): "Migrate Conversations canonical persistence from JSON-on-disk + SQLite FTS to Postgres-primary. Acceptance: `apis/brain/app/services/conversations.py` reads from and writes to `conversations` + `conversation_messages` tables directly (migration 012 already created them). Delete JSON fallback code. Delete SQLite FTS sidecar. Add Postgres `tsvector` column for full-text search on `conversation_messages.body`. All existing conversations backfilled. Verify on prod: `SELECT count(*) FROM conversations` matches `ls apis/brain/data/conversations/*.json | wc -l`." This blocks ALL of Track 2 because every "wire to Brain" workstream assumes Brain endpoints return authoritative data from Postgres.

---

### F2. P0 — Goals split-brain (three sources) is not called out as a unified workstream.

**Track + workstream affected**: T2.0 (Goals verification, XS, P1) and T2.10 (snapshot kill for `goals.json`).

**Specific gap**: Wave-1 audit `people-sprints-epics.md` (company-data-gap-2, severity: critical) documents three goal systems: (A) `apis/brain/data/goals.json` served via `GET /admin/okr/goals` in `admin.py:2190+`, (B) SQL `goals` table served via `GET /admin/goals` on the `epics.py` router, (C) `docs/strategy/OBJECTIVES.yaml` served as `GET /admin/strategic-objectives`. Studio `/admin/goals` reads from (A), not (B). The plan's T2.0 says "XS: open /admin/goals on phone, edit a goal, confirm Brain DB write" — but this will pass even if it's writing to `goals.json` (source A), not the SQL table (source B). The plan never unifies A and B.

**Concrete fix**: Promote T2.0 to M, P0. Rename: "Goals unification: migrate `/admin/goals` Studio page to read from SQL `goals` table (router B: `epics.py`), delete `goals.json`, delete `admin.py:2190+` OKR file-backed endpoints. Link `OBJECTIVES.yaml` as read-only strategic overlay on the Goals page, not a separate system. Acceptance: one `goals` table, one GET endpoint, one Studio page, `goals.json` deleted."

---

### F3. P0 — T1.2 (autopilot install) acceptance criteria reference `/admin/health`, which doesn't render APScheduler job status.

**Track + workstream affected**: T1.2 (autopilot install, XS, P0).

**Specific gap**: Plan line 106 says acceptance is "*/5 * * * * loop visible in /admin/health, rows landing in agent_dispatches." Repo inspection confirms `/health` and `/health/deep` endpoints exist in `apis/brain/app/routers/health.py`, and `/internal/schedulers` (main.py line 244-253) lists APScheduler jobs — but the plan says `/admin/health`, which is a Studio admin page. The Studio `/admin/infrastructure` page exists, but there is no evidence it renders APScheduler job status. The `/internal/schedulers` endpoint returns job metadata but is not rendered by any Studio page.

**Concrete fix**: T1.2 acceptance should read: "autopilot_dispatcher job visible in `GET /internal/schedulers` response (job_id `brain_autopilot_dispatcher`); at least 3 `agent_dispatches` rows written within 15 minutes of deploy; `GET /api/v1/agents/dispatches?limit=3` returns rows with `status=completed`. Add autopilot_dispatcher to `/admin/autopilot` Studio page status header (shows 'Loop running: last run X min ago' or 'Loop not running: install() missing')."

---

### F4. P0 — Migration 015 conflict: T2.4 (decisions table) claims it, but the plan doesn't verify 015 is actually free.

**Track + workstream affected**: T2.4 (decisions table, M, P1).

**Specific gap**: Plan line 136 says "create table if missing — should be migration 015 per locked plan." Repo inspection shows the latest migration is `014_agent_dispatches.py` and there are exactly 14 migration files (001-014). So 015 IS free today. But T1.5 (agent_procedures table + YAML→DB graduation, M, P2) also needs a migration. If both workstreams are dispatched in parallel (the plan's critical path diagram shows them as independent), they'll race for 015. Alembic doesn't handle parallel migration creation — both agents will write a file claiming to be the next revision, and the second one to merge will fail with a branch head conflict.

**Concrete fix**: Add a one-line constraint in the plan: "Migration number allocation: T2.4 = 015, T1.5 = 016. These MUST NOT be dispatched in parallel. T2.4 merges first. Orchestrator verifies `alembic heads` shows a single head after each merge."

---

### F5. P0 — T2.10 snapshot kill (13 files) depends on ~8 Brain endpoints that don't exist yet, but lists them as "parallel-safe after the corresponding Brain endpoint exists."

**Track + workstream affected**: T2.10 (snapshot kill, 13x S, P2).

**Specific gap**: Plan lines 146-163 list 13 snapshot files and the Brain endpoint each needs. Checking the plan's own table:
- `runbook-snapshot.json` → `GET /admin/runbooks` (Wave B3) — **doesn't exist**
- `docs-snapshot.json` → `GET /admin/docs` (Wave B3) — **partially exists** (admin.py has some docs routes, unclear coverage)
- `circles.json` → `GET /admin/circles` (Wave B6) — **doesn't exist**
- `conversation-spaces.json` → `GET /admin/conversation-spaces` (Wave B5) — **doesn't exist**
- `n8n-graph.json` → `GET /admin/workflows` (Wave B3) — **doesn't exist** (admin.py serves the JSON file directly)
- `system-graph.json` → `GET /admin/infra/services` (Wave B4) — **doesn't exist**
- `knowledge-graph.json` → `GET /admin/knowledge-graph` — **doesn't exist**
- `reading-paths.json` → `GET /admin/reading-paths` — **doesn't exist**
- `tracker-index.json` → `GET /admin/tracker-index` — **doesn't exist**
- `founder-actions.json` → `GET /admin/founder-actions` — **partially exists** (conversations.py loads founder_actions from YAML/JSON file, not a DB-backed endpoint)

The plan says "One PR per snapshot, parallel-safe after the corresponding Brain endpoint exists. ~13x S, P2." But creating the Brain endpoints is not a workstream in this plan — it's cited as Waves B3-B6 from the superseded locked plan. So T2.10 is blocked on work the plan doesn't schedule.

**Concrete fix**: T2.10 needs a sub-workstream T2.10a (M, P1): "Create Brain admin endpoints for the 8 missing snapshot sources. For each: (1) decide if the data lives in Postgres (new table) or is read from repo files at runtime; (2) implement `GET /admin/{endpoint}`; (3) only then can the corresponding snapshot file be killed." The 5 snapshots with existing endpoints (`workstreams.json`, `goals.json`, `personas-snapshot.json`, `docs-snapshot.json` partially, `founder-actions.json` partially) can be killed in parallel. The other 8 must wait for T2.10a.

---

### F6. P1 — T4.1 RLS rollout has "~30 SQLAlchemy queries audited" but the plan doesn't account for the Conversations split-brain.

**Track + workstream affected**: T4.1 (RLS rollout, L, P1).

**Specific gap**: RLS policies apply to Postgres tables. If Conversations remain JSON-on-disk canonical (per F1), then RLS on `conversations` and `conversation_messages` tables is a no-op — the actual data doesn't flow through those tables. The plan's RLS workstream assumes all data is in Postgres. If F1 (Conversations migration to Postgres) slips, T4.1 gives a false sense of multi-tenant safety on the founder's primary surface.

**Concrete fix**: Add F1 (Conversations Postgres migration) as a hard prerequisite of T4.1 in the critical path diagram. The RLS rollout cannot be marked complete until ALL Brain entities are Postgres-canonical.

---

### F7. P1 — T4.2 (Brain Gateway runtime) has zero implementation in the codebase and is sized as "L" — it's actually XL scope.

**Track + workstream affected**: T4.2 (Brain Gateway, L, P1) + T4.4 (usage meter, M, P1).

**Specific gap**: `grep` for `POST /v1/brain/invoke` and `brain.invoke` across `apis/brain/` returns **zero files**. The plan says "implement per Brain Gateway Architecture section" but the bible section (BRAIN_ARCHITECTURE.md) describes the contract, not the implementation. The implementation requires: (1) a new router file, (2) skill resolution by `source_kind` (5 kinds: anthropic_skill, mcp_server, openai_tool, oss_package, builtin), (3) MCP client HTTP calls to product MCP servers with per-user auth token resolution from `brain_user_vault` (which is dead code per F1.4/T1.4), (4) usage_meter row writes, (5) outcome hook callbacks, (6) rate limiting per org, (7) cost estimation, (8) error handling per source_kind. This is not one "L" workstream — it's 3-4 M workstreams. The critical path has T4.4 (usage meter) depending on T4.2, and T5.4/T5.5 (IP MCP servers) also depending on T4.2. If T4.2 slips by 2 weeks, the entire L4 handoff (T5.6) slips by 2 weeks.

**Concrete fix**: Split T4.2 into three sub-workstreams: T4.2a (M): "Gateway router + skill resolution + builtin dispatch" (gets the endpoint responding). T4.2b (M): "MCP client + `brain_user_vault` token resolution" (unblocked by T1.4). T4.2c (S): "Usage meter row write + cost estimation per invocation." This lets the critical path move as soon as T4.2a lands — T5.4/T5.5 only need T4.2a, not the full gateway.

---

### F8. P1 — Workstream schema regex (`apis/brain/app/schemas/workstream.py:14`) rejects all existing DB epic IDs.

**Track + workstream affected**: T1.0a (merge PR #689, P0) and T2.1 (Epics surface polish, S, P1).

**Specific gap**: `workstream.py` line 14 defines `_ID_RE = re.compile(r"^WS-\d{2,3}-[a-z0-9-]+$")`. The bible gap audit (line 27) and wave-1 audit both confirm the only DB epic ID is `epic-ws-82-studio-hq`, which doesn't match this regex. The plan (line 106) says PR #689 includes "relaxed Workstream schema" — but until I can read PR #689's diff, I can't verify the regex is actually fixed there. If it isn't, the workstream_dispatcher loop will throw ValidationError on every 5-minute tick and silently skip all dispatch work.

**Concrete fix**: T1.0a acceptance criteria should explicitly include: "After PR #689 merge, verify `workstream_dispatcher` can load at least one epic from DB without ValidationError. Test: `python -c 'from app.schemas.workstream import Workstream; Workstream(id=\"epic-ws-82-studio-hq\", ...)'` succeeds." If PR #689 doesn't fix this, add a P0 XS workstream to patch the regex.

---

### F9. P1 — T3.1 IaC drift detector is sized "L" and depends on 5 provider APIs, each requiring secrets the plan doesn't budget for.

**Track + workstream affected**: T3.1 (IaC drift, L, P1).

**Specific gap**: The workstream says "infra/state/*.yaml becomes canonical for each surface" and needs Cloudflare, Render, Clerk, Hetzner, and Neon state files. Repo confirms only `infra/state/vercel.yaml` and `infra/state/README.md` exist today. Building a drift detector that auto-reverts UI changes or files reconcile PRs requires: (1) read-only API tokens for each provider, (2) a state file schema per provider, (3) diffing logic per provider, (4) PR-filing automation, (5) a 30-minute cron. Each provider's API has different auth (Cloudflare: API token with zone read, Render: API key, Clerk: backend API key, Hetzner: API token, Neon: API key). The plan doesn't mention which of these tokens exist in the vault today.

**Concrete fix**: Add a prerequisite XS workstream T3.1-pre: "Audit Studio Vault for provider API tokens needed by IaC drift detector. List: CF_API_TOKEN (zone:read), RENDER_API_KEY, CLERK_SECRET_KEY, HETZNER_API_TOKEN, NEON_API_KEY. For each: exists? has sufficient scopes? If missing, create and vault. This unblocks T3.1." Without this, the cheap agent dispatched for T3.1 will get stuck mid-implementation waiting for secrets.

---

### F10. P1 — T5.5 (LaunchFree MCP server) includes "Python port of packages/filing-engine using playwright-python" and is sized "L" — it's a rewrite, not a port.

**Track + workstream affected**: T5.5 (LaunchFree MCP, L, P2).

**Specific gap**: Plan line 229 says "Python port of packages/filing-engine/ using playwright-python, DE first." `packages/filing-engine/` is a TypeScript package (2,449 lines per the superseded plan). Porting 2,449 lines of Playwright automation from TypeScript to Python is not "L" — it's XL. The plan marks it P2, which is appropriate for priority, but the sizing affects the "10-12 weeks" timeline if it's on the critical path. Checking the critical path diagram: T5.5 depends on T5.3 and T4.2, and T5.6 (`pwl` CLI, L4 handoff) does NOT depend on T5.5. So T5.5 is off the critical path — but the plan doesn't say this explicitly, which means a naive reader might block L4 handoff on it.

**Concrete fix**: Mark T5.5 as "off critical path — does not block L4 handoff or L5 activation." Re-size from L to XL. Note in the plan: "LaunchFree MCP is a post-L4 workstream; it can ship after the founder has transitioned to product work."

---

### F11. P1 — No workstream addresses the Conversations persona-reply endpoint mismatch (Studio proxies to a non-existent Brain route).

**Track + workstream affected**: T2.5 (Conversations polish, S, P2).

**Specific gap**: Wave-1 audit (conv-gap-4) documents: Studio has `POST /api/admin/conversations/{id}/reply` route (`apps/studio/src/app/api/admin/conversations/[id]/reply/route.ts`) that proxies to Brain, but Brain doesn't expose `POST .../reply` — it exposes `POST /api/v1/admin/conversations/{id}/persona-reply` (different path). T2.5 says "unflag BRAIN_CONVERSATION_INLINE_PERSONA_REPLY_READY" — but unflagging it will route requests to a non-existent Brain endpoint and 404. The plan assumes the flag is the only thing blocking persona-reply; the actual blocker is a route mismatch.

**Concrete fix**: T2.5 acceptance criteria should include: "Before unflagging, verify Studio proxy route path matches Brain's actual persona-reply endpoint. Fix whichever side is wrong. After unflagging, test: click 'Request persona reply' in Studio → Brain returns a persona-generated response in-thread within 10 seconds."

---

### F12. P2 — The plan's GHA workflow count is wrong ("~50 still on ubuntu-latest" per T3.9), and the actual count changes the sizing.

**Track + workstream affected**: T3.9 (GHA→Hetzner runner migration, M, P1).

**Specific gap**: Plan line 203 says "today 8 jobs use [self-hosted, hetzner], ~50 still on ubuntu-latest." Repo inspection shows 30 `.yaml` workflows + 8 `.yml` workflows = 38 total workflow files. `runs-on: ubuntu` appears in 36 of them (51 total `runs-on` lines including matrix jobs). `runs-on: self-hosted` appears in 5 files (9 total lines). So the ratio is closer to 51:9, not 50:8. The difference is small in absolute terms but the plan's policy audit still needs to touch every workflow file. More importantly, the 8 `.yml` files (including `axiomfolio-ci.yml`, `brain-pre-merge-guards.yml`, `axe-a11y-ci.yml`, etc.) are not in the `.yaml` glob — a naive auditor might miss them.

**Concrete fix**: T3.9 should note: "Audit ALL workflow files: `*.yaml` AND `*.yml` (38 total). The extension inconsistency itself should be fixed (standardize on `.yaml` per repo convention)."

---

## 4. What's Missing Entirely

### M1. Conversations Postgres migration (P0)

Covered in F1 above. This is the single most dangerous omission. The founder's only daily-use surface stores canonical data on Render's ephemeral disk. No workstream addresses this.

### M2. Staging environment for Brain

No workstream provisions a staging Brain. T4.1 (RLS rollout) says "24h staging burn-in" (plan line 214). T4.6 (tenant provision) says "spin up test-tenant-1 in staging" (plan line 219). But there's no staging Brain API on Render, no staging Neon database, no staging Redis. The plan assumes staging exists; it doesn't. Add a T3.x workstream: "Provision Brain staging on Render (second Starter instance, separate Neon branch, BRAIN_STAGING_URL env var, Studio can toggle Brain target between prod and staging via settings)."

### M3. Backup/restore for Brain Postgres + agent_episodes

No workstream addresses database backups. Neon provides point-in-time recovery (PITR) on paid plans, but the plan doesn't mention which Neon tier Brain uses or whether PITR is enabled. If Brain is on Neon free tier, there is no automated backup and a single bad migration (like the 014 backfill that resolved to the wrong path per dispatch-gap-3) could corrupt the only copy. Add a T3.x workstream: "Verify Neon PITR is enabled for Brain DB. Document recovery procedure in `docs/runbooks/BRAIN_DB_RECOVERY.md`. Test: restore to 1 hour ago, verify agent_episodes count matches."

### M4. PII scrubber audit on new Track 2 surfaces

Track 2 adds 5+ new Studio admin pages (decisions, sprints, transcripts, dispatches, skills). Each surface renders Brain data that may include PII from agent conversations (names, SSNs referenced in tax context, email addresses). The plan has no workstream that audits the new surfaces for PII display. The `.cursorrules` security rules (never log PII, SSN masked, etc.) apply to backend, but frontend rendering of episode content could show unmasked PII. Add a cross-cutting checklist item: "Every Track 2 surface that renders episode/transcript content must call `scrub_pii()` on displayed text or use the `<MaskedContent>` component."

### M5. Observability budget / Sentry quota

The plan mentions Sentry in T3.0 (stack audit) but has no workstream that verifies Sentry is actually receiving errors from Brain or Studio in production. If the Sentry DSN is misconfigured or the quota is exhausted, all of Track 3's "deploy stability" work ships without error visibility. Add a verification item to T3.7 acceptance: "Sentry receives at least 1 test error from Brain prod within 5 minutes of deploy."

### M6. Connection pool sizing for the autopilot loop

T1.2 wires `autopilot_dispatcher.install()` — a `*/5 * * * *` loop that opens DB sessions, queries workstreams, dispatches agents, and writes `agent_dispatches` rows. Brain is on Render Starter (512MB). If the autopilot loop runs concurrently with the existing ~15 scheduler jobs (confirmed in `__init__.py`), and each opens a connection, the Neon connection limit (25 on free tier) could be exhausted. The plan doesn't mention connection pooling. Add to T1.2 acceptance: "Verify `max_connections` on Neon after autopilot install. If free tier (25), confirm total concurrent APScheduler jobs don't exceed 20 (leaving 5 for web requests)."

### M7. Secret-rotation policy and cron

Wave-1 secrets audit (secrets-gap-1, severity: critical) documents no create/rotate/delete UI in Studio. T2.9 addresses the UI, but no workstream establishes a rotation policy (which secrets should rotate on what cadence) or a cron that alerts when secrets are overdue. `credential_expiry.py` exists but checks `expires_at` metadata, not rotation age. Add to T2.9: "Define rotation policy in `docs/runbooks/SECRET_ROTATION.md`: BRAIN_API_SECRET (90d), VERCEL_TOKEN (180d), provider API keys (365d). Wire `secrets_rotation_monitor` scheduler to create `alert` Conversation when any secret exceeds its policy age."

### M8. `closes_workstreams` auto-close reads JSON, not Postgres

Wave-1 audit (company-data-gap-5): `sprint_md_auto_close.py` gates completion against `workstreams.json`, not the SQL `epics` table. The plan's T2.10 kills `workstreams.json`. If T2.10 merges before `sprint_md_auto_close.py` is repointed to SQL, the auto-close service will silently break — it will try to load a file that no longer exists and either crash or no-op (depending on error handling). Add: "T2.10 prerequisite: repoint `sprint_md_auto_close.py` from `load_workstreams_file()` to `load_epics_from_db()`. Same for `workstream_progress.py:69` and `admin.py:321-336` (workstreams-board endpoint)."

---

## 5. Sequencing Call

The plan has 4 parallel tracks starting day 1. **That is wrong for Track 4 (B2B-Ready Spine).** Track 4 should not start until Track 1 is done and F1 (Conversations Postgres migration) has shipped.

**Recommended sequencing:**

**Week 1 (serial, orchestrator-only):**
1. F1: Conversations Postgres migration (P0, M) — blocks everything
2. T1.0a/b/c: Stop the bleed (merge PRs #689, #690, auto-merge guard)
3. T1.2: Wire autopilot_dispatcher.install() (XS)
4. F2: Goals unification (M)

**Weeks 2-3 (Track 1 remainder + Track 2 starts + Track 3 starts):**
- T1.1, T1.3, T1.4, T1.5 (Track 1 remainder, parallel-safe)
- T2.0-T2.4, T2.7 (Track 2 entities with existing endpoints)
- T3.0, T3.2, T3.7, T3.8 (Track 3 audit + deploy stability, read-only)

**Weeks 4-6 (Track 2 snapshot kills + Track 3 IaC + Track 4 starts):**
- T2.10a (create missing Brain endpoints for snapshots)
- T2.5, T2.6, T2.8, T2.9 (Track 2 polish)
- T3.1, T3.9 (Track 3 IaC drift + Hetzner migration)
- T4.1 (RLS, only after F1 is confirmed)

**Weeks 7-9 (Track 4 gateway + Track 5 starts):**
- T4.2a/b/c, T4.4, T4.6 (Gateway + usage meter + tenant provision)
- T5.1, T5.2, T5.3 (Wave K cleanup)

**Weeks 10-12 (Track 5 MCP + L4 handoff):**
- T5.4, T5.6, T5.7 (FileFree MCP, pwl CLI, app onboarding = L4 handoff)
- T5.8, T5.9 (L5 activation seeds)

**Hard prerequisites the plan diagram misses:**
- F1 (Conversations Postgres) → T4.1 (RLS)
- F2 (Goals unification) → T2.10 (snapshot kill for goals.json)
- T2.10a (new Brain endpoints) → T2.10 (snapshot kill for 8 files)
- M8 (repoint auto-close to SQL) → T2.10 (snapshot kill for workstreams.json)
- T1.5 migration number → T2.4 migration number (serialize, not parallel)

---

## 6. Honest Week Budget

The plan says "10-12 weeks." With the P0 fixes (F1-F5) and the missing workstreams (M1-M8), the honest estimate is:

| Scope | Original estimate | Revised estimate | Delta explanation |
|---|---|---|---|
| Track 1 + F1 + F2 | 2-3 wks | 3-4 wks | F1 (Conversations migration) adds ~1 week; F2 (Goals unification) adds ~0.5 week |
| Track 2 | 4-5 wks | 5-6 wks | T2.10a (8 missing Brain endpoints) adds ~1 week |
| Track 3 | 3-4 wks | 3-4 wks | No change (T3.1 secret prerequisite is XS) |
| Track 4 | 4-6 wks | 5-7 wks | T4.2 split (F7) extends by ~1 week; staging provisioning (M2) adds 0.5 week |
| Track 5 | 3-5 wks | 3-5 wks | T5.5 off critical path (F10) removes pressure; T5.1-T5.3 smaller than estimated |

**Revised total: 13-16 weeks** if serial. With the parallel tracks (2-3 at any time), **10-13 weeks** is achievable. The original "10-12 weeks" is **optimistic by 1-2 weeks** — call it **11-13 weeks** as the honest range.

**What would make "10 weeks" realistic:**
1. Drop T5.5 (LaunchFree MCP) entirely from this plan — it's XL, off critical path, and P2. Ship it in Q3.
2. Drop T2.10 for the 8 snapshot files that need new Brain endpoints. Kill only the 5 snapshots with existing endpoints. Defer the rest to a "snapshot kill phase 2" workstream.
3. Drop T3.5 (Slack streamline, P3) and T3.6 (Brain kill switch, P2 — nice-to-have but not blocking).

With those 3 cuts: **10-11 weeks** is honest.

---

## 7. Top 5 Actions Before Founder Kicks Off

### Action 1: Add T1.0d (P0) — Conversations Postgres migration

Insert between T1.0c and T1.1 in the plan:

```
- **T1.0d** Conversations canonical Postgres migration: rewrite `apis/brain/app/services/conversations.py`
  to use Postgres `conversations` + `conversation_messages` (migration 012) as the source of truth,
  not JSON-on-disk + SQLite FTS. Backfill existing conversations. Delete FTS sidecar.
  Add `tsvector` column on `conversation_messages` for full-text search. M, P0.
  Acceptance: `conversations.py` has zero `open()` calls, zero SQLite imports;
  `SELECT count(*) FROM conversations` ≥ 1; founder opens Studio Conversations on phone,
  sees all existing threads.
```

Add F1 as a predecessor of T4.1 in the critical path diagram.

### Action 2: Promote T2.0 (Goals) to M, P0 and add unification scope

Replace T2.0 in the plan:

```
- **T2.0** Goals unification: migrate `/admin/goals` Studio page from `goals.json` (admin.py OKR file
  endpoints) to SQL `goals` table (epics.py hierarchy endpoints). Delete `goals.json`. Delete
  `admin.py:2190+` file-backed OKR routes. Wire `OBJECTIVES.yaml` as read-only strategic overlay
  on the Goals page. M, P0. Acceptance: one `goals` table, one GET endpoint, one Studio page,
  `goals.json` deleted, OBJECTIVES.yaml visible on Goals page as "Strategic Context" section.
```

### Action 3: Fix T1.2 acceptance criteria and add migration serialization constraint

Replace T1.2 acceptance in the plan with the corrected version from F3. Add a note after T2.4:

```
**Migration ordering constraint**: T2.4 = migration 015, T1.5 = migration 016. These MUST merge
sequentially (T2.4 first). Orchestrator runs `alembic heads` after each merge to verify single head.
```

### Action 4: Add T2.10a (missing Brain endpoints) and mark T2.10 blocked

Insert before T2.10:

```
- **T2.10a** Create Brain admin endpoints for 8 snapshot sources that lack DB-backed APIs:
  runbooks, circles, conversation-spaces, workflows (n8n), infra/services, knowledge-graph,
  reading-paths, tracker-index. For each: (1) decide Postgres table vs repo-file reader,
  (2) implement GET endpoint, (3) add to REGISTRY.md. 8× S → effective M, P1.
  Blocks: T2.10 for those 8 files.
```

Mark T2.10 as "5 files immediately killable (workstreams, goals, personas per T2.7, and the 2 partials); 8 files blocked on T2.10a."

### Action 5: Move Track 4 start to week 4 and add staging provisioning

Add to Track 3:

```
- **T3.x** Provision Brain staging environment: Render Starter ($7/mo) for brain-staging,
  Neon branch for staging DB, staging Redis on Upstash. Studio env toggle (BRAIN_API_URL
  switches between prod/staging via admin setting). XS, P1.
  Acceptance: `curl https://brain-staging.paperworklabs.com/api/v1/health` returns 200.
```

Update the critical path: Track 4 (T4.1 RLS) depends on T3.x (staging exists) AND F1 (Conversations Postgres migration). T4.1's "24h staging burn-in" now has an actual staging to burn in against.

---

*End of review. The plan is strong — it's the first plan in this repo that accurately traces from doctrine to workstreams with honest severity labels and specific acceptance criteria. The five actions above are cheap patches that prevent the three highest-risk failure modes: data loss (F1), split-brain (F2), and false-positive RLS completion (F6). Fix those and this plan ships.*
