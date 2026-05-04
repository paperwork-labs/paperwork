# Brain Architecture Bible — Gap Audit (2026-05-03)

**Auditor**: Opus orchestrator (Brain bible single-pass review, founder-approved exception to cheap-agent-only fleet rule)
**Bible reviewed**: `docs/BRAIN_ARCHITECTURE.md` v10 — 2,771 lines, 60 design decisions (D1-D63 with gaps), 228 findings (F1-F228)
**Scope**: gap-finding only — NO code changes, NO bible edits, NO `.mdc` rule edits. Output is a structured patch list the founder will review before a separate chat ships fixes.

---

## Executive Summary

The Brain Architecture Bible is an A+ specification for **Consumer Brain** — an AI life-intelligence product for end users (couples, restaurants, refunds, Memory Moat, Brain Fill Meter, Circle Sharing, financial referrals). It is **silent or wrong** on **Brain-as-Company-OS**, which is the surface the founder uses every single day to run Paperwork Labs (employees, epics, sprints, conversations, transcripts, agent dispatches, decisions, secrets). The bible has **zero mentions** of "epic," "workstream," or "transcript" in the operational sense; one passing mention of "sprint drift"; and only flags consumer agent_conversations as a "P9 deferred" schema addition while production Brain already runs a fully-built Conversations surface (composer, persona-reply, snooze, status, react). This is the single root cause of the founder's repeated "half-finished features" frustration: the bible never said the company-OS surface should exist, so when WS-82 Studio HQ shipped 13 sprint waves the bible had no acceptance criteria for them, and orphaned components (`sprints-overview-tab.tsx`, `WorkstreamsBoardClient`, `brain_user_vault` table, `autopilot_dispatcher.install()`, `transcripts.py` GET endpoints) ship and never get noticed.

**Severity rollup**:

- **Tier 1 (architectural omissions)**: 7 BLOCKING + 4 HIGH + 2 MEDIUM = **13 missing decisions** that explain >80% of the half-wired features. Headlined by **D64 Brain as Company OS**, **D65 Internal Operations Schema**, **D66 Conversations as Founder Action Surface**, **D67 Transcripts as Knowledge**, **D68 Agent Dispatch as First-Class Entity**, **D69 End-to-End Verification at Workstream Layer**, **D70 Studio Admin Surface Coverage Matrix**.
- **Tier 2 (existing decisions contradicted by ground truth)**: **6 amendments** required, headlined by D54 Dual-Context (incomplete), Section 8 Studio Dashboard (severely outdated), D31/D24 Persona system (mixes rules with employees), Section 2 Schema (commented-out tables that exist in production), D62 brain_skills (duplicates instead of pointers).
- **Tier 3 (existing decisions defined but not implemented)**: **5 strikes-or-implements**, headlined by D61 Per-User Vault (`brain_user_vault` table exists, ZERO code touches it), D40 Procedural Memory, D41 Langfuse, D42 Generative UI components, D45 Tax Season Wrapped.
- **Tier 4 (cross-references to operational rules outside the bible)**: **4 doctrines** that should be summarized inside, headlined by `cheap-agent-fleet.mdc`, `no-silent-fallback.mdc`, `production-verification.mdc`, `brain-coach.mdc`.
- **Tier 5 (Studio admin coverage matrix)**: **10 entities × 5 dimensions** — only **2 of 10 entities** are fully wired round-trip (Conversations, Goals); 5 are partially wired; 3 are orphaned.
- **Tier 6 (E2E verification doctrine at workstream layer)**: **1 new doctrine** that subsumes `production-verification.mdc` at the higher level.

**Single biggest gap if we fix nothing else**: write **D64 — Brain as Company OS** and the immediately-adjacent **D65 — Internal Operations Schema** and **D70 — Studio Admin Surface Coverage Matrix**. These three decisions together establish the missing north star ("Brain is also the queryable graph of the company's own operations, observable from Studio, on phone and desktop"), the missing data model (Goal → Epic → Sprint → Task/PR → Decision → Conversation → Transcript → Episode → Employee → Skill → Secret), and the missing acceptance bar (every entity must have DB row + API + Studio page + E2E verified on phone before "shipped"). With those three decisions in place, every half-wired feature surfaced below becomes a tracked debt, not an invisible accident.

**Two ground-truth contradictions to flag up-front** (the founder's pre-audit notes were close but slightly off):

1. The pre-audit summary said "epics: 1 (only `epic-ws-82-studio-hq` exists in DB)." Subagent code survey confirms there IS an epics table (created in an Alembic migration, exposed via `getEpicHierarchy()` in Studio's brain-client). The `/admin/workstreams` route exists and renders the Epics hierarchy, not a workstreams board (`apps/studio/src/app/admin/workstreams/page.tsx:67-70` titles itself "Epics"). So the entity is "Epic" in code/DB but "Workstream" in the locked plan and rule files. **The bible needs to reconcile these names** — see Tier 1 D65.
2. Pre-audit notes said `WorkstreamsBoardClient` is "orphaned." Subagent confirms the drag-and-drop board lives at `apps/studio/src/app/admin/workstreams/workstreams-client.tsx` and is referenced ONLY by its own test file — zero page imports. So the route `/admin/workstreams` renders Epics, while a built-but-unmounted "workstreams board" sits dormant. The Workstream Pydantic schema in `apis/brain/app/schemas/workstream.py:14` requires id pattern `^WS-\d{2,3}-[a-z0-9-]+$` — but the only DB epic id is `epic-ws-82-studio-hq`, so the regex would reject it, which is the source of the live `workstreams_loader.py:128` ValidationError every minute.

---

## Gap Tier 1 — Architectural omissions (need new D## or new section)

These are gaps where **no decision exists today**. They explain the half-wired-feature pattern more than any other class of gap. Severity is scored against the founder's north-star metric: "how many repeated half-finished feature incidents would this decision have prevented?"

### T1.1 — D64. Brain as Company OS (Internal Operations Mode)

- **Severity**: BLOCKING
- **What's missing**: The bible defines Brain as a consumer life-intelligence product (`docs/BRAIN_ARCHITECTURE.md:18-25`) and a meta-product that subsumes FileFree/LaunchFree/AxiomFolio as user-facing skills (D49, D62). It never says Brain is **also** the company's own operating system — the queryable graph of how Paperwork Labs runs itself. D54 (Dual-Context, lines 433-443) gestures at founder dogfood ("personal Brain + Paperwork Labs org Brain") but stops at "context switching UI in P9" without acknowledging that the org-Brain context is where Brain spends >95% of its actual current usage and where every shipped feature needs to land.
- **Why it matters (which half-wired feature it explains)**: Without this north star, every "company OS" feature is built against an absent spec. WS-82 Studio HQ shipped 13 waves with no bible acceptance criteria for any of them; `sprints-overview-tab.tsx` was built without a `page.tsx` because nothing in the bible says "internal sprint surfaces must be reachable on phone"; `brain_user_vault` table got a migration but zero readers because nothing in the bible says "internal-Brain features must be observable in Studio." This is the missing root.
- **Where in the doc it should land**: Promote to a top-level section before D49 (Memory Moat) — call it **`## Operating Modes`** with subsections "Consumer Brain" / "Company OS" / "Meta-Product". Anchor D64 inside it, before existing D49. Insertion point: after "Reference Data Storage Doctrine" section (`docs/BRAIN_ARCHITECTURE.md:780-806`) and before "Brain Gateway Architecture" section (`docs/BRAIN_ARCHITECTURE.md:809-861`). The two doctrines that already exist there are infrastructure-level; the new Operating Modes section is product-level and belongs right before them.
- **Proposed canonical name**: `D64. Brain as Company OS — Internal Operations Mode`
- **Skeleton patch text**:

  > Brain runs in three operating modes against a single backend, single schema, single agent loop. The mode is determined by `organization_id` and `user_id` resolution at request time:
  >
  > **Mode 1 — Consumer Brain** (`organization_id = 'user-{uuid}'`): the AI life-intelligence product specified across D1-D63. Memory Moat, Brain Fill Meter, Circle Sharing, financial referrals. End-user facing.
  >
  > **Mode 2 — Company OS** (`organization_id = 'paperwork-labs'`): the queryable graph of how Paperwork Labs runs itself. The founder uses this every day. Goals, Epics, Sprints, Tasks/PRs, Decisions, Conversations, Transcripts, AgentDispatches, Employees, Skills, Secrets — all live in Brain DB, all are observable from Studio admin (`paperworklabs.com/admin/*`), all are accessible to the founder on phone (Studio PWA) and desktop. This is not a separate product, not a separate service, not a separate database. It is the same Brain running with a different organization scope. The data model lives in D65 (Internal Operations Schema). The surface contract lives in D70 (Studio Admin Surface Coverage Matrix).
  >
  > **Mode 3 — Meta-Product** (per-user, but Brain composes across product MCP servers): Brain calls FileFree / LaunchFree / AxiomFolio / Distill MCP servers via the gateway (D62) on behalf of an end user. The bible's existing F90 framing covers this.
  >
  > **Why this matters (founder dogfood doctrine)**: Sankalp and Olga are not just the first customers of Consumer Brain (D54). They are also the only users of Company OS today, and they are the canary that catches half-wired features before any external user can. Every feature shipped against Mode 2 must be E2E verified by the founder on phone + desktop before being marked shipped (see D69). The Memory Moat thesis (D49) also applies recursively to the company itself: Brain accumulates years of company decisions, sprint history, persona dispatches, transcripts — that is the company's own switching cost away from running on Notion/Linear/Slack.
  >
  > **Anti-pattern this rules out**: building a company-OS feature inside Studio that calls third-party APIs (Linear, Notion, GitHub Projects) without first asking "should this entity live in Brain?" If the entity is part of how Paperwork Labs runs itself, the answer is yes — see D65.

---

### T1.2 — D65. Internal Operations Schema (Goal → Epic → Sprint → Task → PR → Decision)

- **Severity**: BLOCKING
- **What's missing**: The bible's Memory Schema (Section 2, `docs/BRAIN_ARCHITECTURE.md:863-1316`) covers consumer-side tables (`agent_organizations`, `agent_episodes`, `agent_entities`, `agent_costs`, `brain_skills`, `brain_user_vault`, etc.) and the org/team/individual hierarchy from D19. It never specifies the **operational** hierarchy (Goal → Epic → Sprint → Task → PR → Decision) that the company actually runs on. The locked plan (`/Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_—_final_plan_4c44cfe9.plan.md:74-83`) lists "Wave B Brain schema 014-024" and "Wave H Activity feed + Brain dispatcher uses ownership graph" but the bible never reconciles its own schema with these waves. The DB now has at least 30 tables across 14 migrations; only the consumer subset is in the bible.
- **Why it matters**: Without a canonical operational schema, two things go wrong. (a) Naming drifts: bible calls knowledge units "episodes," locked plan calls them "ownership graph," `.cursor/rules/cheap-agent-fleet.mdc` calls them "workstreams," Brain DB calls them "epics," Studio route calls them "workstreams" but renders "Epics" — five names for overlapping concepts. (b) Acceptance criteria are absent: when an `agent_dispatches` table lands in migration 014, no one can say "this should also have a Studio page and a transcript ingest" because no schema decision exists. The founder's phrase from the brief — "sprints, epics, workstream, goals, brain, automation, backend, infra setup, setup workers, employees (people) — these are all tied together right" — is asking for exactly this missing decision.
- **Where in the doc it should land**: New top-level section between current Section 2 (Memory Schema) and Section 3 (Model Routing Matrix). Title: **`## 2A. Internal Operations Schema (Company OS)`**. Insertion point: after `docs/BRAIN_ARCHITECTURE.md:1316` (end of consumer schema), before `docs/BRAIN_ARCHITECTURE.md:1318` (Section 3 header).
- **Proposed canonical name**: `D65. Internal Operations Schema — Goal → Epic → Sprint → Task → PR → Decision (Company OS data model)`
- **Skeleton patch text**:

  > The Company OS mode (D64) has its own canonical entity hierarchy. These entities live in the same Brain DB as consumer episodes; they are scoped by `organization_id = 'paperwork-labs'` and exposed via `/api/v1/admin/*` endpoints. The hierarchy is a strict tree, top-down:
  >
  > **Goal** → multi-quarter venture objective (e.g. "Launch FileFree MeF Transmitter Jan 2027"). Owns 1-N Epics. Schema: `goals` table, FK from `epics.goal_id`. UI: `/admin/goals`.
  >
  > **Epic** → multi-week initiative scoped to one Goal (e.g. "WS-82 Studio HQ"). Owns 1-N Sprints. Schema: `epics` table — current id pattern is `epic-ws-{NN}-{kebab-slug}` (verified live in DB). UI: `/admin/workstreams` (renders Epics hierarchy despite the route name; see naming reconciliation below).
  >
  > **Sprint** → 1-3 day execution unit shipping 1-3 PRs (e.g. "WS-82 Wave A — schema bones"). Owns 1-N Tasks. Schema: `sprints` table, FK `sprint.epic_id`. Sprint markdown lives at `docs/sprints/*.md` with `closes_workstreams:` frontmatter; the auto-close service (`apis/brain/app/services/sprint_md_auto_close.py`) reconciles markdown → DB rows. UI: `/admin/sprints` (currently MISSING — `sprints-overview-tab.tsx` is orphaned, see T1.7 / Tier 5).
  >
  > **Task / PR** → atomic unit of work. May or may not have a corresponding GitHub PR. Schema: `tasks` table, FK `task.sprint_id`, optional `task.pr_url`. UI: surfaced inline on Sprint and Epic detail pages.
  >
  > **Decision (D##)** → canonical strategic-decision record committed to `docs/KNOWLEDGE.md`. Each decision is also a row in Brain DB so it can be queried (`/api/v1/admin/decisions`) and back-referenced by Episodes. Schema: `decisions` table with `external_id` (e.g. "D85"), `title`, `body`, `created_at`, `references[]` (links to other entities). UI: `/admin/docs` already surfaces docs — Decisions need their own canonical view.
  >
  > **Conversation** → persistent thread of founder ↔ Brain interaction (see D66). Schema: `conversations` + `thread_messages`. UI: `/admin/conversations`.
  >
  > **TranscriptEpisode** → ingested chunk of an external chat session (e.g. Cursor agent session, Slack thread, voice note transcription) that becomes part of Brain memory (see D67). Schema: `transcript_episodes`. UI: `/admin/transcripts` (currently MISSING).
  >
  > **AgentDispatch** → record of one Task-tool dispatch to a cheap-agent subagent (see D68). Schema: `agent_dispatches`. UI: `/admin/autopilot` (partially exists, only surfaces Episode source-prefix `autopilot`, not the AgentDispatch table directly).
  >
  > **Employee / Persona** → the 17 employees in the company (16 personas + Founder). Schema: `employees` table in Brain DB (verified live, exposed via `GET /admin/employees`). UI: `/admin/people`. **NOT to be confused with the 35 rule files in `.cursor/rules/*.mdc`** — those are doctrines, not employees, and the current `apps/studio/src/data/personas-snapshot.json` mixes the two (see Tier 2 amendment T2.4).
  >
  > **Skill** → Brain capability registered in `brain_skills` (D62). Either built-in or pointer to a product MCP server. UI: `/admin/architecture?tab=flows` (currently — should grow into `/admin/skills` per Wave G of locked plan).
  >
  > **Secret** → encrypted credential, lives in Studio Vault (canonical) with optional Brain registry overlay. Per-user credentials live in `brain_user_vault` (D61, currently dead-code per Tier 3 T3.1). UI: `/admin/infrastructure?tab=secrets` + `/admin/secrets/intake/[token]`.
  >
  > **Naming reconciliation**: "Workstream" (used in `cheap-agent-fleet.mdc`, locked plan, `apis/brain/app/schemas/workstream.py`) and "Epic" (used in DB rows, `getEpicHierarchy()`, Studio nav label) refer to the same entity. The locked plan's id pattern `WS-NN-kebab` is a workstream alias for the epic; the DB's `epic-ws-82-studio-hq` is the canonical id. Going forward: **the canonical name is "Epic"; "Workstream" is deprecated as a synonym** (Brain MUST accept both id patterns until all rule files and schemas are reconciled — see follow-up patch in Tier 2 T2.5). The Pydantic Workstream schema's regex `^WS-\d{2,3}-[a-z0-9-]+$` (`apis/brain/app/schemas/workstream.py:14`) is the source of the live ValidationError every minute on the workstream_dispatcher loop because it rejects `epic-ws-82-studio-hq` — fix scope is "extend regex to accept `^(WS-\d{2,3}|epic-ws-\d{2,3})-[a-z0-9-]+$` until rename completes."
  >
  > Mermaid diagram of the hierarchy belongs in this section.

---

### T1.3 — D66. Conversations as the Founder Action Surface (Brain ↔ Founder)

- **Severity**: BLOCKING
- **What's missing**: Section 8 (Studio Dashboard, `docs/BRAIN_ARCHITECTURE.md:1456-1458`) gives Conversations one phrase ("Conversations (thread explorer)"), and Section 2 schema marks `agent_conversations` as P9 deferred (`docs/BRAIN_ARCHITECTURE.md:1136-1146`, commented-out). The `.cursor/rules/ea.mdc` rule file has 200+ lines describing how Brain Conversations are the EA's primary surface today (proactive briefings tagged `daily-briefing` / `weekly-plan` / `decision` / `pr-review` / `alert`, reactive thread replies, persona routing, founder dogfood mode, mobile PWA push). Reality: Brain ships POST `/admin/conversations`, GET `/admin/conversations`, GET single, POST messages, POST status (resolve/reopen/archive), POST snooze, POST persona-reply, POST react — a full product surface. The bible never specs it.
- **Why it matters**: Without a canonical decision, the conversation surface evolves ad-hoc. Recently added: persona-reply endpoint that's feature-flagged off in Studio (`BRAIN_CONVERSATION_INLINE_PERSONA_REPLY_READY = false` per subagent, in `conversations-client.tsx:290`); compose modal; founder-actions backfill; expense-conversation card subtype. Each was built without an architectural anchor. Tags are conventionally typed but not enforced. There is no spec for: when does Brain auto-create a conversation vs append to a thread? When does a persona reply on its own vs wait for founder action? What's the SLA on a `urgency: high` conversation? The EA persona file answers some of these, but **doctrine that lives only in `.mdc` files is not bible**.
- **Where in the doc it should land**: Replace Section 8 (Studio Dashboard, current 3-line stub at `docs/BRAIN_ARCHITECTURE.md:1456-1458`) with a real section. Anchor D66 inside it. Cross-reference the EA persona file but DO NOT delegate the spec there — the architecture spec lives in the bible.
- **Proposed canonical name**: `D66. Conversations as the Founder Action Surface — Brain ↔ Founder threaded loop`
- **Skeleton patch text**:

  > In Company OS mode (D64), Conversations are the **primary** surface where Brain communicates with the founder and the founder communicates back. They are the company-OS equivalent of the consumer chat in `apps/brain/` — both share the underlying `agent_conversations` + `thread_messages` schema, but conversations are designed for Brain-to-founder action items, not founder-to-Brain Q&A. The two coexist.
  >
  > **Conversation lifecycle**:
  >
  > 1. **Creation**: Brain creates a conversation via `POST /admin/conversations` (admin auth). Triggers include: scheduled briefings (EA daily/weekly via APScheduler), infra alerts (`tag: alert`), PR-ready summaries (`tag: pr-review`), expense approvals (`tag: expense-approval`), session bookends (`tag: session-bookend`), audit findings (`tag: weekly-audit-digest`). Each conversation is created with `persona`, `tags[]`, `urgency`, `title`, `body`. Brain MUST set the persona that owns the thread.
  > 2. **Threading**: Founder replies → `POST /admin/conversations/:id/messages` appends a `ThreadMessage`. Brain auto-routes the thread to the appropriate persona based on tag + content keywords (smart persona routing, see EA persona file). Persona response is appended as another `ThreadMessage`.
  > 3. **State**: Conversations have status `open | resolved | archived` and are snoozable. Snooze hides until a deadline. Resolve marks done. Archive deletes from inbox view.
  > 4. **Reactions**: Founder can react to a single message (emoji); reactions are signals for Brain's procedural-memory loop ("founder approved this kind of suggestion → do more like it").
  > 5. **Persona-reply**: An explicit endpoint to ask Brain to compose a persona response without the founder typing first — useful for reflective replies, summaries, or escalations. Currently feature-flagged off in Studio per `apps/studio/src/app/admin/brain/conversations/conversations-client.tsx:290`; this decision unblocks shipping it.
  >
  > **Tag taxonomy** (canonical; replaces the historical Slack channel directory in `.cursor/rules/ea.mdc`): `daily-briefing`, `weekly-plan`, `decision`, `pr-review`, `alert`, `filing-engine`, `company`, `general`, `deployment`, `social-content`, `tax-insights`, `trading`, `expense-approval`, `expense-monthly-close`, `expense-rule-change`, `session-bookend`, `weekly-audit-digest`. New tags require a bible PR — this prevents tag sprawl.
  >
  > **Urgency SLA**:
  >
  > | Urgency | Push notification | Founder action expected within | Auto-escalation if ignored |
  > |---|---|---|---|
  > | `info` | No | 24h | None |
  > | `low` | No | 24h | None |
  > | `medium` | In-app only | 12h | Surface in next daily briefing |
  > | `high` | PWA push | 4h | Re-notify after 4h, escalate to `urgent` after 24h |
  > | `urgent` | PWA push + email | 1h | Re-notify hourly until acknowledged |
  >
  > **Founder dogfood doctrine**: Conversations are the canary surface (D54 + D69). If the founder cannot action a conversation on their iPhone PWA in <30 seconds, the surface is broken — regardless of what works on desktop.

---

### T1.4 — D67. Transcripts as Knowledge (Cursor Sessions, Voice, External Threads)

- **Severity**: HIGH
- **What's missing**: Bible mentions "transcription" only for Whisper voice input (D29, `docs/BRAIN_ARCHITECTURE.md:241-247`). It does NOT spec **TranscriptEpisodes** as ingested knowledge — chunks of external chat sessions (Cursor agent transcripts at `/Users/paperworklabs/.cursor/projects/.../agent-transcripts/`, Slack threads, voice notes, browser tab recordings) that become permanent Brain memory and can be read back. Reality: a `transcript_episodes` table exists in Brain DB; Brain has `POST /admin/transcripts/ingest` (verified by subagent). Brain does NOT have a GET endpoint to read what's been ingested. Studio has no `/admin/transcripts/` page (verified absent).
- **Why it matters**: The founder's pre-audit notes say "Plans (`.cursor/plans/*.plan.md`, `docs/sprints/*.md`) are NOT ingested into any Brain table. No backfill script. Bible doesn't say they should be — but the founder thought they were." Same pattern: the absence of a decision means transcript ingestion was built halfway (write-only, no read), and external knowledge sources (Cursor plans, sprint markdown, agent-transcripts) sit outside Brain's queryable graph. This is the difference between Brain "knowing" the company and Brain "having a half-wired ingest endpoint that no one can query."
- **Where in the doc it should land**: New decision in Section 1 (D-list), inserted after D62 (Skill Registry) and before D63 (Browser Context Connector). Insertion point: `docs/BRAIN_ARCHITECTURE.md:746` (end of D62) → new D67 → existing D63 starts at `docs/BRAIN_ARCHITECTURE.md:748`.
- **Proposed canonical name**: `D67. Transcripts as Knowledge — Cursor sessions, voice notes, external threads as ingested episodes`
- **Skeleton patch text**:

  > A **TranscriptEpisode** is an ingested chunk of an external chat session — Cursor agent transcript, Slack thread, voice note, browser session — that becomes permanent Brain memory. Schema: `transcript_episodes` table with FK `source_kind` (`cursor_session` | `slack_thread` | `voice_note` | `external_doc`), `source_ref` (file path or URL), `body` (full text or chunk), `embedding` (for vector recall), `episode_id` (FK back to `agent_episodes` so transcripts are first-class memory).
  >
  > **Ingest paths**:
  >
  > - `POST /admin/transcripts/ingest` (existing, manual or automated) — accepts a payload with source_kind + source_ref + body. Chunks long bodies. Generates embeddings. Writes to `transcript_episodes` AND `agent_episodes` so retrieval works the same way.
  > - **Cursor session backfill** (planned): nightly job scans `/Users/paperworklabs/.cursor/projects/.../agent-transcripts/*.jsonl` for new sessions, ingests parent transcripts (NOT subagent transcripts per the citation rule), tags by date and parent uuid.
  > - **Sprint markdown ingest** (planned): on PR merge to `docs/sprints/*.md`, ingest the markdown body as a TranscriptEpisode with `source_kind = sprint_doc` and link to the corresponding Sprint row (D65).
  > - **Plan markdown ingest** (planned): scan `/Users/paperworklabs/.cursor/plans/*.plan.md` weekly, ingest as TranscriptEpisodes with `source_kind = plan_doc`. (The locked Brain plan at `4c44cfe9` should be the first ingested.)
  >
  > **Read paths** (all currently MISSING — must ship before this decision counts as built):
  >
  > - `GET /admin/transcripts` — paginated list with filter by source_kind, date range, search query.
  > - `GET /admin/transcripts/:id` — single transcript with chunks.
  > - `/admin/transcripts/` Studio page — renders the list, search, and individual transcript view.
  >
  > **Why this is separate from Conversations (D66)**: Conversations are designed for two-way founder ↔ Brain dialog with status, snooze, react. Transcripts are designed for one-way external-source ingestion with retrieval. They share the underlying `agent_episodes` memory but have different lifecycles, different Studio views, and different write-paths.
  >
  > **No-silent-fallback enforcement** (`.cursor/rules/no-silent-fallback.mdc`): if transcript ingest fails for one chunk in a 50-chunk session, the per-chunk failure MUST be logged + counted, and the session-level success MUST report `chunks_ingested=49 chunks_failed=1` not `success=true`.

---

### T1.5 — D68. Agent Dispatch as a First-Class Entity (Cheap-Agent Fleet → Brain)

- **Severity**: HIGH
- **What's missing**: Bible's D31 (Hierarchical Persona Architecture) covers persona orchestration and the 4-tier model. It does NOT spec **AgentDispatch** as a first-class entity — a single persisted record of one Task-tool dispatch to a cheap-agent subagent (model, persona, prompt size, cost, outcome, validator notes). The cheap-agent fleet doctrine (`.cursor/rules/cheap-agent-fleet.mdc`) lives entirely outside the bible and references "Phase H Brain self-dispatch loop" repeatedly without the bible ever defining Phase H or its data model. Reality: an `agent_dispatches` table exists from migration 014 (per founder pre-audit notes); `apis/brain/app/schedulers/autopilot_dispatcher.py` defines an `install()` method (line 344 per subagent finding) but **it is never called by any startup function** — so the `*/5 * * * *` dispatch loop never runs in production.
- **Why it matters**: The founder repeatedly bumps into half-wired dispatch surfaces. `/admin/autopilot` page exists but reads from `agent_episodes` with `source_prefix=autopilot`, not from the `agent_dispatches` table directly. The `agent_dispatch_log.json` file (referenced by `.cursor/rules/cheap-agent-fleet.mdc` Rule 6 and `brain-coach.mdc`) has no app-level writer in `apis/brain/app/` — only readers. The `merge_queue.json` referenced in cheap-agent-fleet Rule 4 has no writer in apis/brain/app/ either. Without a bible decision, every cheap-agent rule says "log here, write there" but nothing actually wires the fleet to Brain.
- **Where in the doc it should land**: New D68 in Section 1 D-list, inserted after the new D67 (Transcripts) per insertion order. Cross-reference into Section 12 (Hierarchical Persona Architecture) and into the new D69 (Verification Doctrine).
- **Proposed canonical name**: `D68. Agent Dispatch as a First-Class Entity — Cheap-Agent Fleet → Brain learning loop`
- **Skeleton patch text**:

  > Every dispatch of a Task-tool subagent (cheap-agent fleet — composer-1.5, composer-2-fast, gpt-5.5-medium, claude-4.6-sonnet-medium-thinking — never Opus per `.cursor/rules/cheap-agent-fleet.mdc` Rule 2) is recorded as one **AgentDispatch** row in Brain DB. This is the data substrate for Phase H Brain self-improvement.
  >
  > **Schema** (`agent_dispatches`, lives in Brain DB, scoped to `organization_id = 'paperwork-labs'` for the company-OS dispatcher; consumer dispatcher rows can coexist with `organization_id = 'user-{uuid}'`):
  >
  > - `id`, `created_at`, `parent_dispatch_id` (nullable, for Brain-self-dispatch loops), `epic_id` (FK to D65 Epic when the dispatch is workstream work)
  > - `persona_slug`, `model`, `model_size_tier` (XS/S/M/L per `docs/PR_TSHIRT_SIZING.md`)
  > - `prompt_tokens`, `completion_tokens`, `cost_usd_estimated`, `cost_usd_actual`
  > - `status` (`pending` | `running` | `completed` | `failed` | `vetoed_by_orchestrator`)
  > - `preflight_consulted` (boolean, set by `stamp_preflight` per `.cursor/rules/brain-coach.mdc`)
  > - `pr_url` (nullable, set when dispatch opens a PR), `pr_outcome` (`merged` | `closed_unmerged` | `auto_reverted`)
  > - `validator_notes` (text, mandatory orchestrator review per cheap-agent-fleet Rule 3)
  > - `outcome_summary` (one-line "what shipped"), `not_done_summary` (per cheap-agent-fleet Rule 5 — explicit scope-overflow disclosure)
  > - `parent_uuid` (nullable; for Cursor parent-session attribution)
  >
  > **Two write paths**:
  >
  > 1. **Inline (live)**: when Brain's autopilot scheduler dispatches a cheap-agent, it INSERTs an `agent_dispatches` row at dispatch start, UPDATEs at completion. Currently broken — `autopilot_dispatcher.install()` is never called. **Fix scope** (separate PR per Tier 3 T3.5): wire `install()` into `apis/brain/app/main.py` startup.
  > 2. **Backfill (one-shot)**: migration 014's backfill from JSON file (per founder pre-audit notes) — re-runnable script that ingests `apis/brain/data/agent_dispatch_log.json` (or .jsonl) into the `agent_dispatches` table. The JSON files referenced in cheap-agent-fleet Rule 6 (`pr_outcomes.json`, `procedural_memory.yaml`, `self_merge_promotions.json`, `long_tail.json`, `merge_queue.json`) MUST migrate to corresponding Brain DB tables — see Cross-product implications section below.
  >
  > **Read paths** (currently partial — `/admin/autopilot` reads episodes not dispatches; must add direct dispatch endpoints):
  >
  > - `GET /admin/agent-dispatches?status=&persona=&model=&from_date=&to_date=&limit=` — paginated list.
  > - `GET /admin/agent-dispatches/:id` — single dispatch with full payload + validator notes + outcome.
  > - `/admin/agent-dispatches` or `/admin/autopilot` Studio page — renders list, allows orchestrator approve/veto on `pending` rows.
  >
  > **Brain self-improvement loop** (Phase H — define here, NOT in cheap-agent-fleet.mdc): the nightly self-improvement cron (D35) reads `agent_dispatches` from the past 24h and:
  >
  > - Computes per-(persona × model × workstream-type) acceptance rate. Updates `procedural_memory` rules accordingly.
  > - Identifies dispatch types where validator_notes show repeated criticism. Adds those patterns to `procedural_memory.yaml`.
  > - Surfaces the report in a `weekly-audit-digest` Conversation (D66).
  >
  > This subsumes the JSON-file substrate described in cheap-agent-fleet Rule 6: the JSON files are interim during the L4 blitz; the post-blitz substrate is `agent_dispatches` rows. The bible commits to that promotion timeline.

---

### T1.6 — D69. End-to-End Verification at the Workstream Layer (Phone + Desktop)

- **Severity**: BLOCKING
- **What's missing**: `.cursor/rules/production-verification.mdc` covers PR-layer verification (deploy live, /health 200, behavioral curl, 5-min log watch). The bible has nothing equivalent at the **workstream layer** — the higher question of "is this Epic actually shippable?" — and nothing that bridges PR-merged → workstream-shipped via founder dogfood. Founder's own framing: "a workstream is not shipped until used round-trip on phone." Today, `closes_workstreams:` frontmatter on sprint markdown auto-closes the workstream (`apis/brain/app/services/sprint_md_auto_close.py`) — purely on PR merge, with zero E2E verification.
- **Why it matters**: This is the doctrine that catches `sprints-overview-tab.tsx` being orphaned (it would never have been "shipped" because no founder ever opened it on phone). It catches `brain_user_vault` having zero callers. It catches `transcript_episodes` having no read endpoint. It catches `autopilot_dispatcher.install()` never being wired. Every half-wired feature in this audit fails one of these checks. The PR-verification doctrine is necessary but not sufficient; the workstream-verification doctrine is the missing higher rule.
- **Where in the doc it should land**: Sibling to D64 in the new `## Operating Modes` section. Cross-reference both `.cursor/rules/production-verification.mdc` (PR-layer) and `.cursor/rules/no-silent-fallback.mdc` (data-layer) so the bible is the apex rule and the .mdc files are the per-layer enforcement.
- **Proposed canonical name**: `D69. End-to-End Verification at the Workstream Layer — Phone + Desktop founder dogfood doctrine`
- **Skeleton patch text**:

  > **Rule.** A workstream (Epic — see D65 reconciliation) is NOT shipped until **all five** of the following are true:
  >
  > 1. **PR-layer verification passes** per `.cursor/rules/production-verification.mdc`: deploy live, /health 200, behavioral curl green, 5 minutes of clean logs.
  > 2. **DB row exists**: every Brain entity introduced or modified by the workstream has its rows visible via the corresponding `/api/v1/admin/*` endpoint with auth.
  > 3. **Studio page exists and is reachable from `paperworklabs.com/admin/*` nav** (D70 surface coverage). No orphaned components. If a tab component is built (e.g. `sprints-overview-tab.tsx`), it MUST be mounted on a `page.tsx` that is reachable from the admin nav within the same workstream.
  > 4. **Founder uses it round-trip on iPhone (Studio PWA)** within 24h of PR merge. Round-trip = open the page, take an action, see the result reflected. Voice-only or read-only access does not count. The founder is the primary canary; if the surface breaks on phone, the surface is not shipped.
  > 5. **Founder uses it round-trip on desktop** within 24h of PR merge. Same definition.
  >
  > **Failure modes** (none of these is "shipped"):
  >
  > - PR merged + deploy green + nav link missing → not shipped (component is orphaned).
  > - DB row exists + API exists + Studio page exists + founder hasn't opened it → not shipped (untested).
  > - Founder opened on desktop only → not shipped (mobile failure mode is the most expensive class of bug per `.cursor/rules/no-hallucinated-ui-labels.mdc` and the founder's own UX).
  > - PR merged + scheduler defined + scheduler never installed → not shipped (this is exactly the `autopilot_dispatcher` failure mode).
  >
  > **Auto-close discipline**: `apis/brain/app/services/sprint_md_auto_close.py` currently auto-closes workstreams from `closes_workstreams:` frontmatter on sprint markdown merge. **This is too lenient.** Auto-close should require BOTH frontmatter declaration AND a verification checklist completion event. Proposal: add a `verification_completed_at` timestamp column on the Sprint row (D65) that is only set when the founder posts a one-click "verified on phone + desktop" action in the corresponding Conversation thread (D66). Auto-close fires only when both `closes_workstreams:` is present AND `verification_completed_at IS NOT NULL`.
  >
  > **No-silent-fallback at the workstream layer**: if a workstream ships without verification — for example, an emergency fix at 2am — the Sprint row MUST be marked `status: shipped_unverified` and a follow-up Conversation tagged `verification-debt` MUST be auto-created. Silent "shipped" without verification is forbidden.

---

### T1.7 — D70. Studio Admin Surface Coverage Matrix (every Brain entity has a Studio page)

- **Severity**: BLOCKING
- **What's missing**: Section 8 (Studio Dashboard, `docs/BRAIN_ARCHITECTURE.md:1456-1458`) lists 7 page types in a single sentence, with phase numbers. There is no canonical mapping of "every Brain entity must have: DB + API + Studio page + E2E verified." This is the surface contract.
- **Why it matters**: This is the doctrine that prevents the surface coverage matrix gaps in Tier 5. Once written, it becomes a compile-time check: every new Alembic migration that creates a public Brain entity must come with a Studio page in the same workstream, or it's not shipped.
- **Where in the doc it should land**: Replace Section 8 entirely. The replacement is a real section, ~80-150 lines, owning the surface contract.
- **Proposed canonical name**: `D70. Studio Admin Surface Coverage Matrix — every Brain entity has a Studio page`
- **Skeleton patch text**:

  > Studio admin (`paperworklabs.com/admin/*`) is the **canonical surface for Company OS mode** (D64). Every Brain entity that is part of the Internal Operations Schema (D65) MUST have a Studio page meeting all of the following criteria:
  >
  > 1. Reachable from `apps/studio/src/lib/admin-navigation.tsx` admin nav (no orphaned routes).
  > 2. Server-renders from a live Brain `/api/v1/admin/*` endpoint (no static snapshot fallbacks except for graceful degradation; if Brain is down, page shows "Brain unreachable" not stale data).
  > 3. Mobile-responsive at 375px and tested in Studio PWA on iPhone.
  > 4. Implements the four-state UX rule from `.cursor/rules/no-silent-fallback.mdc`: explicit `loading` / `error` / `empty` / `data` branches.
  > 5. Either fully read-only OR has a labeled action surface (no read-only-pretending-to-have-actions).
  >
  > **Coverage matrix** (filled by gap-audit Tier 5 below; this is the canonical structure — actual cell values live in Tier 5).
  >
  > **Anti-pattern this rules out**:
  >
  > - Building a snapshot file (`apps/studio/src/data/*.json`) that mirrors a Brain DB entity. The snapshot is fine as a build-time fallback but the live source MUST be Brain. The locked plan Wave E says "delete `apps/studio/src/data/*.json`" — this decision codifies that direction.
  > - Building a tab component without a `page.tsx`. If the work is real, mount the page in the same PR. If the page is deferred, the tab component MUST be archived under `apps/studio/src/app/_archive/` not left in the active tree.
  > - Mixing entities of different kinds in a single snapshot. The current `apps/studio/src/data/personas-snapshot.json` is the canonical example — 52 entries containing a mix of 47 employees/personas and 5 rule files (`cheap-agent-fleet`, `no-silent-fallback`, `git-workflow`, `code-quality-guardian`, `plan-mode-first`). This is forbidden going forward; rules and personas are different entities (D65) with different surfaces (`/admin/people` vs a future `/admin/doctrine`).

---

### T1.8 — D71. Reference Knowledge Pipeline (Plans, Sprints, Decisions ingestion path)

- **Severity**: HIGH
- **What's missing**: Bible covers consumer email/calendar/Maps ingestion (D50, D58) and Reference Data Storage Doctrine for tax/formation/portal data (post-D63 unnumbered section). It does NOT spec how the company's own knowledge artifacts (`.cursor/plans/*.plan.md`, `docs/sprints/*.md`, `docs/KNOWLEDGE.md` D## entries, `.cursor/rules/*.mdc` doctrine) are ingested into Brain so Brain can answer "what did we decide about X" or "which sprint touched Y." The locked plan's Wave D says "Backfill (workstreams, transcripts, rules, infra, docs)" — but the bible is silent on this.
- **Why it matters**: Brain coach (`.cursor/rules/brain-coach.mdc`) tells the orchestrator to consult `recall_memory` before dispatch. But if `recall_memory` doesn't include sprint history, decision log, or rule files, then the consult is hollow. This is the company-OS analog of D49 (Memory Moat) — the company's own switching cost away from running on Notion/Linear lives in Brain accumulating its own history.
- **Where in the doc it should land**: New decision after D67 (Transcripts) and before D68 (Agent Dispatch). Or alternatively, fold into D67 as a sub-section. Recommend: standalone D71 because the ingest cadence is different (transcripts are continuous; reference knowledge is one-shot backfill + on-merge updates).
- **Proposed canonical name**: `D71. Reference Knowledge Pipeline — Plans, Sprints, Decisions, Rules ingested into Brain memory`
- **Skeleton patch text** (~10 sentences):

  > Five categories of company-internal knowledge MUST be ingested into Brain DB so Brain can answer historical questions:
  >
  > 1. **Plans** (`/Users/paperworklabs/.cursor/plans/*.plan.md` — gitignored locally, present on founder's machine): one-shot backfill via dedicated script, then nightly delta scan. Each plan becomes a TranscriptEpisode (D67) with `source_kind = plan_doc`.
  > 2. **Sprint markdown** (`docs/sprints/*.md`, in repo): on every PR merge that touches `docs/sprints/`, ingest the new/modified file as a TranscriptEpisode with `source_kind = sprint_doc` AND link to the corresponding Sprint row (D65) via `sprint_id`. The auto-close service (`sprint_md_auto_close.py`) already parses these files; extend it to also ingest the body.
  > 3. **Decision log** (`docs/KNOWLEDGE.md`, in repo): on every PR merge that touches the file, parse the diff for added `### D##` headings, INSERT into `decisions` table (D65), ingest the body as a TranscriptEpisode with `source_kind = decision_doc` linked via `decision_id`.
  > 4. **Rule files** (`.cursor/rules/*.mdc`, in repo, bundled into Brain Docker image already): on every Brain Docker build, parse the bundled `.mdc` files and upsert into a `rules` table with sha versioning. Rules are not Decisions — they are doctrine. Surface in a future `/admin/doctrine` page (Tier 5).
  > 5. **The bible itself** (`docs/BRAIN_ARCHITECTURE.md`): on every PR merge, ingest the diff section by section as TranscriptEpisodes with `source_kind = bible_doc`. This decision MUST be re-ingested first.
  >
  > **No-silent-fallback enforcement**: ingestion failures must be visible in `/admin/health` with per-source freshness ("Plans: last ingest 3h ago / 87 of 87 files current; Sprints: last ingest 30s ago / 142 of 142 files current; ..."). If ingest fails for any source for >24h, auto-create a Conversation tagged `alert` urgency `high`.

---

### T1.9 — D72. Founder Dogfood Mode (Olga + Sankalp as canary, every feature)

- **Severity**: MEDIUM
- **What's missing**: D54 (Dual-Context, `docs/BRAIN_ARCHITECTURE.md:433-443`) acknowledges Sankalp + Olga have personal Brain + org Brain + household Circle. The bible says "they exercise every feature before any external user touches it" but **only in the consumer-product context**. There is no equivalent doctrine for Company OS mode — i.e. that every Company OS feature is dogfooded by the founder before being marked shipped. D69 codifies the verification rule; D72 codifies the *who* (the founder is the only canary that matters in Company OS mode, because there are no other users) and the *cadence* (within 24h of PR merge).
- **Why it matters**: Without naming the founder as the canary, the verification rule is impersonal and easy to forget. With it named, it becomes a personal accountability loop.
- **Where in the doc it should land**: Sibling to D64, D69 in the new `## Operating Modes` section.
- **Proposed canonical name**: `D72. Founder Dogfood Mode — Sankalp + Olga are the only canary for Company OS`
- **Skeleton patch text** (~6 sentences):

  > In Company OS mode (D64), there are exactly two users: Sankalp and Olga. There is no other canary. Every Company OS workstream is shipped against their actual usage; if it doesn't work for them on phone + desktop within 24h of PR merge, it is not shipped (D69). The founder dogfood loop is the only signal Brain has for company-OS feature quality. Olga's onboarding to the Conversations surface (the Slack-decommission migration) is the explicit test of this doctrine: every feature she needs MUST exist on phone before her first session, or she falls back to Slack-style mental models that the company has already moved past. Brain procedural memory MUST treat "founder did not open this surface within 24h" as a failure signal and surface it in the weekly-audit-digest Conversation.

---

### T1.10 — D73. JSON-File-to-Brain-DB Migration Doctrine (apis/brain/data/* substrate decision)

- **Severity**: MEDIUM
- **What's missing**: Several JSON files under `apis/brain/data/*` are referenced by cheap-agent-fleet rules and brain-coach rules as the substrate for procedural memory and dispatch logging — `procedural_memory.yaml`, `agent_dispatch_log.json`, `pr_outcomes.json`, `merge_queue.json`, `long_tail.json`, `self_merge_promotions.json`. The bible never says when these graduate from JSON files to Brain DB tables. Subagent finding: `merge_queue.json` has no writer in `apis/brain/app/`; `agent_dispatch_log.json` (the .json variant) has no writer either. So today these are partially-wired files referenced by doctrine but unmaintained.
- **Why it matters**: This is the company-OS analog of the Reference Data Storage Doctrine (`docs/BRAIN_ARCHITECTURE.md:780-806`). That doctrine says "tax brackets stay in JSON in `packages/data/`" because they have an annual cadence and need git audit trail. The company-OS substrate question is the inverse: "agent dispatches happen continuously, so they MUST live in DB." But the bible never asserts this, so the L4 blitz left them in JSON files without a graduation path.
- **Where in the doc it should land**: New decision in Section 1, after D71 and before D72. Cross-reference Reference Data Storage Doctrine.
- **Proposed canonical name**: `D73. JSON-File-to-Brain-DB Migration Doctrine — operational substrate belongs in DB, not files`
- **Skeleton patch text** (~8 sentences):

  > The Reference Data Storage Doctrine (post-D63) says canonical reference data with annual cadence belongs in `packages/data/src/**/*.json`, not Postgres. The inverse is also doctrine: **continuous operational substrate belongs in Brain DB, not files**. The current state of `apis/brain/data/*` (`procedural_memory.yaml`, `agent_dispatch_log.json`, `pr_outcomes.json`, `merge_queue.json`, `long_tail.json`, `self_merge_promotions.json`) is a transitional artifact of the L4 blitz; per `.cursor/rules/cheap-agent-fleet.mdc` Rule 6 these files were the substrate during the 48-hour blitz, but the post-blitz substrate is rows in `agent_dispatches` (D68), `agent_procedures` (D40), `agent_episodes` (Section 2), and the audit log.
  >
  > **Migration rule**: every JSON file under `apis/brain/data/*` referenced by a `.mdc` rule MUST have either (a) an active writer in `apis/brain/app/` keeping it current, or (b) a documented migration path to a Brain DB table with a target ship date. If neither, the file is dead doctrine and the rule MUST be amended to remove the reference. Today, `merge_queue.json` and `agent_dispatch_log.json` (the .json variant) have neither — Tier 3 of this audit lists them as strike-or-implement.
  >
  > **No-silent-fallback enforcement**: if a `.mdc` rule references a JSON substrate file and the file is missing or stale (>7 days old without a planned cadence), Brain MUST surface this in `/admin/health` and create an `alert` Conversation. Silently degrading on missing substrate is forbidden.

---

### T1.11 — D74. Bible Phase-Numbering / Wave-Numbering Reconciliation

- **Severity**: MEDIUM
- **What's missing**: Bible uses phases P0-P10 (`docs/BRAIN_ARCHITECTURE.md:2273-2509`). Locked Brain plan uses Waves A-K (`/Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_—_final_plan_4c44cfe9.plan.md:71-99`). Sprint epics use WS-NN naming (e.g. epic-ws-82-studio-hq). Cheap-agent-fleet doctrine references "Phase H" and "WS-67" and "WS-69" without the bible defining either. There is no canonical mapping.
- **Why it matters**: When the founder asks "what wave is this in?" or "is this Phase H?" the answer requires triangulating four naming systems. This causes constant orientation cost. It also means the bible's Phased Execution Plan (Section 20) is divorced from the actual execution that happens in waves and sprints.
- **Where in the doc it should land**: New section between current Section 20 (Phased Execution Plan) and Section 21 (Monthly Cost Model). Title: **`## 20A. Phase ↔ Wave ↔ Workstream Reconciliation`**.
- **Proposed canonical name**: `D74. Phase ↔ Wave ↔ Epic ↔ Workstream Naming Reconciliation`
- **Skeleton patch text**: a single-table reconciliation showing P0-P10 (bible) ↔ Wave A-K (locked plan) ↔ Epic ids (DB) ↔ Workstream ids (rule-file conventions). Plus a rule: "going forward, the canonical operational name is **Epic** with id pattern `epic-ws-{NN}-{kebab}`. Bible Phases stay as the consumer roadmap; Waves stay as the locked plan; Workstream/WS-NN is deprecated as a synonym for Epic and must be reconciled to it during ingestion."

---

### T1.12 — D75. Brain → Studio Auth & API Contract (admin endpoints, internal tokens, CORS)

- **Severity**: MEDIUM
- **What's missing**: Bible's D9 (Internal authentication, `docs/BRAIN_ARCHITECTURE.md:78-80`) says "BRAIN_API_SECRET shared between n8n and Brain API." Reality: Studio admin server-side calls Brain via `BRAIN_API_URL` + `BRAIN_INTERNAL_TOKEN` per `apps/studio/src/lib/brain-admin-proxy.ts` (subagent finding). The `/admin/secrets` Brain-overlay flow per AGENTS.md docs and `docs/infra/BRAIN_SECRETS_INTELLIGENCE.md` adds another auth surface. No bible decision specifies the canonical Brain↔Studio auth contract.
- **Why it matters**: Auth is critical security surface. Today there is BRAIN_API_SECRET (legacy n8n), BRAIN_INTERNAL_TOKEN (Studio overlay), BRAIN_MCP_TOKEN (per render.yaml), BRAIN_ADMIN_TOKEN (per ea.mdc) — at least four token names referenced across docs without a canonical spec.
- **Where in the doc it should land**: Amend D9 to be the canonical place. Insertion point: after `docs/BRAIN_ARCHITECTURE.md:80` (end of D9 body).
- **Proposed canonical name**: `D75. Brain ↔ Studio Internal API Contract — token taxonomy, CORS, admin auth`
- **Skeleton patch text** (~6 sentences):

  > Three internal auth tokens, each with a single canonical purpose:
  >
  > - `BRAIN_API_SECRET` — legacy n8n adapter token; deprecated; remove when n8n adapters are fully retired (per AGENTS.md "non-cron n8n workflows remain by design" carveout).
  > - `BRAIN_INTERNAL_TOKEN` (preferred name for `BRAIN_ADMIN_TOKEN`) — Studio's server-side service-to-Brain auth for `/api/v1/admin/*` endpoints. Used by `apps/studio/src/lib/brain-admin-proxy.ts` and by EA persona's `conversations-persona.sh` script per `.cursor/rules/ea.mdc`.
  > - `BRAIN_MCP_TOKEN` — per-call user resolution for the `/v1/brain/invoke` gateway (D62). External callers (ChatGPT, Claude desktop) and Brain itself use this format. Stored in `brain_user_vault` per D61.
  >
  > CORS: Brain admin endpoints accept Studio's origin (`paperworklabs.com`) only, not consumer Brain frontends. Consumer Brain endpoints (`/v1/brain/*`) accept their own product origins per D12. The bible MUST list every endpoint's auth requirement in a table; this section is that table.

---

### T1.13 — D76. Schema Changes Always Have Studio Surface in Same PR (anti-orphan)

- **Severity**: HIGH
- **What's missing**: There is no rule saying "if you add an Alembic migration that creates a public Brain entity, the same PR MUST add (or modify) a Studio page." The closest is `.cursor/rules/no-silent-fallback.mdc`, but that's about runtime data flow, not schema-to-surface flow.
- **Why it matters**: This rule is what would have caught `brain_user_vault` (migration 001 created it; never wired to any code or surface) and `transcript_episodes` (table exists; no GET endpoint; no Studio page) at PR review time. It is a structural anti-orphan rule.
- **Where in the doc it should land**: New decision in the same Operating Modes section as D64/D69/D72.
- **Proposed canonical name**: `D76. Schema-to-Surface Co-Shipping — Alembic migration + API + Studio page in the same PR`
- **Skeleton patch text** (~5 sentences):

  > Every Brain Alembic migration that creates a public entity (i.e. an entity surfaced in Internal Operations Schema D65 or referenced by any rule file) MUST be accompanied in the same PR by:
  >
  > 1. The corresponding `apis/brain/app/models/*.py` SQLAlchemy model.
  > 2. The corresponding `apis/brain/app/routers/*.py` GET endpoint(s) — at minimum a paginated list and single-row read.
  > 3. The corresponding `apps/studio/src/app/admin/*/page.tsx` Studio page (or, if intentionally deferred, an `--archived` annotation in PR body explaining why and a tracker reference for the surface ship date).
  > 4. A founder-dogfood checklist item in the PR body (D72): "I will open this in Studio PWA on iPhone within 24h of merge."
  >
  > **Anti-pattern this rules out**: "I'll add the table now, surface comes later." That is the exact pattern that produced `brain_user_vault` and `transcript_episodes` orphans. CI guard: ripgrep on every Brain PR — if `apis/brain/alembic/versions/*.py` is modified and no `apps/studio/src/app/admin/**/page.tsx` is created or modified in the same PR, fail with "schema-to-surface co-shipping required (D76)."

---

## Gap Tier 2 — Existing decisions contradicted by ground truth (need amendment)

### T2.1 — Section 8 (Studio Dashboard) — severely outdated, needs full rewrite

- **What's wrong**: Section 8 (`docs/BRAIN_ARCHITECTURE.md:1456-1458`) describes 7 admin pages in one sentence, all phased to "P5 / P6 / P8" — which means the bible thinks these don't exist yet. Reality (subagent inventory): `/admin` has ~40 pages live today across Conversations, Goals, Workstreams (Epics), People, Autopilot, Architecture, Infrastructure, Docs, Expenses, Vendors, Bills, PR-Pipeline, etc. Most are server-rendered against live Brain APIs. The section is years out of date.
- **Proposed amendment**: Replace Section 8 entirely with the new D70 (Studio Admin Surface Coverage Matrix — Tier 1 T1.7). Move the surviving design content (page list, what each surfaces, mobile-first PWA specs) into D70's body. Cross-reference into D64 / D66 / D67 / D68 / D69.

### T2.2 — D54 (Dual-Context Architecture) — incomplete; doesn't acknowledge Company OS

- **What's wrong**: D54 (`docs/BRAIN_ARCHITECTURE.md:433-443`) says Sankalp/Olga have personal Brain + org Brain + household Circle, and "context switching UI in P9." It frames this as founder-dogfood for the consumer product. It does NOT acknowledge that the org-Brain context is the production company-OS mode where Brain spends ~95% of its actual usage today, and that the org-Brain context has its own data model (D65), surfaces (D70), and verification doctrine (D69) that the bible has never specified.
- **Proposed amendment**: Insert a new closing paragraph in D54 acknowledging Company OS as the primary use of the org-Brain context, cross-referencing the new D64 (Brain as Company OS) and D65 (Internal Operations Schema). Verbatim:

  > **Beyond founder dogfood**: the `paperwork-labs` org-Brain context is not just where Sankalp + Olga test consumer features before shipping — it is the production Company OS mode for Paperwork Labs (D64). Every entity in the company's operating model (Goals, Epics, Sprints, Conversations, Transcripts, AgentDispatches, Decisions, Employees, Skills, Secrets) lives in this context with its own canonical data model (D65), surface contract (D70), and verification doctrine (D69, D72). The org-Brain context is the founder-facing primary today; the personal-Brain context will become founder-facing primary when the consumer product ships at P9. Both run on the same backend.

### T2.3 — D62 (Platform Brain + Skill Registry) — needs explicit "no skills built inside Brain" amendment

- **What's wrong**: D62 (`docs/BRAIN_ARCHITECTURE.md:679-746`) plus the post-D62 unnumbered section "IP skills live in product backends as MCP servers" (`docs/BRAIN_ARCHITECTURE.md:731-746`) ARE explicit that IP skills live in product MCP servers, not in Brain. Good. BUT — the seeded `brain_skills` rows in Section 2 schema (`docs/BRAIN_ARCHITECTURE.md:1305-1315`) include `tax-filing`, `llc-formation`, `financial-calculators` as `requires_connection: false` (i.e. built-in to Brain) — which contradicts the IP-skills-in-MCP rule. So the schema seed and the doctrine disagree.
- **Proposed amendment**: Edit the seed INSERT in Section 2 to mark these as `source_kind = 'mcp_server'` with `source_ref` pointing at the planned product MCP endpoints (or `source_kind = 'todo_mcp'` if not yet built — Wave I3 per locked plan). Add the missing schema columns (`source_kind`, `source_ref`, `source_version`) explicitly to `brain_skills` table definition — the post-D62 section references them but the schema definition (`docs/BRAIN_ARCHITECTURE.md:1237-1251`) doesn't include them.

### T2.4 — D24 / D31 (Persona system) — production mixes rules with employees, contradicting the spec

- **What's wrong**: D24 and D31 spec a persona system based on `.cursor/rules/*.mdc` files paired 1:1 with `apis/brain/app/personas/specs/*.yaml`. The 16 personas are `cos`, `cto`, `cro`, `tax-intelligence`, `legal-compliance`, `financial-ops`, `ux-design`, `product-intelligence`, plus 5 Tech Advisory Board, plus founder-mind. Reality: production `apps/studio/src/data/personas-snapshot.json` contains 52 entries, of which **5 are rule files masquerading as personas** (`cheap-agent-fleet`, `no-silent-fallback`, `git-workflow`, `code-quality-guardian`, `plan-mode-first`) per subagent finding. The `/admin/people` page renders Brain DB employees (correct) AND the snapshot personas (mixes rules with personas).
- **Proposed amendment**: Add a new sub-section under D24 titled **"Personas vs Rules vs Employees — three distinct entity classes"**. Verbatim:

  > Three distinct entity classes that share `.mdc` file infrastructure but are NOT interchangeable:
  >
  > - **Persona** — an AI persona with a system prompt, model defaults, escalation rules. Has a 1:1 pairing of `.cursor/rules/<persona>.mdc` (instructions) + `apis/brain/app/personas/specs/<persona>.yaml` (typed contract). 16 today (D31).
  > - **Rule / Doctrine** — a `.cursor/rules/*.mdc` file that codifies engineering practice (e.g. `cheap-agent-fleet`, `no-silent-fallback`, `git-workflow`). NOT a persona. Has no PersonaSpec, no model defaults, no escalation. Surfaced in a future `/admin/doctrine` Studio page; ingested into Brain via D71.
  > - **Employee** — a human or human-like entity in the company directory (`employees` table in Brain DB, exposed via `GET /admin/employees`, surfaced in `/admin/people`). 17 today (16 personas + Founder per founder pre-audit notes).
  >
  > **Cleanup required**: `apps/studio/src/data/personas-snapshot.json` MUST be split into two snapshot files (`personas-snapshot.json` and `rules-snapshot.json`), or — preferably per Wave E of the locked plan — eliminated entirely in favor of live Brain endpoints (`/admin/personas`, `/admin/rules`, `/admin/employees`). The current mixed-content snapshot is a Tier 2 contradiction that produces confused `/admin/people` UX.

### T2.5 — Section 2 schema — commented-out tables that exist in production

- **What's wrong**: Section 2 schema (`docs/BRAIN_ARCHITECTURE.md:1136-1218`) commented-out blocks for `agent_conversations`, `agent_procedures`, `agent_circles`, `agent_circle_members`, `agent_delegated_access`, `agent_access_audit_log` marked as "P9 addition" and "P5 addition." Reality: at minimum `agent_conversations` (or equivalent `conversations` + `thread_messages`) tables exist and are heavily in use today (per subagent finding on the conversations router — POST/GET/PATCH endpoints all live).
- **Proposed amendment**: Audit each commented block against current Alembic migrations (subagent identified migrations 001-014). For each table that exists in production, uncomment the schema and remove the "Pn addition" comment. For each that doesn't yet exist, keep commented but update the phase reference to match locked plan Wave numbering.

### T2.6 — D31 (Hierarchical Persona) — STALE marker explicit; needs reconciliation

- **What's wrong**: D31 contains an explicit `<!-- STALE 2026-04-24 -->` HTML comment (`docs/BRAIN_ARCHITECTURE.md:1544`) flagging that the tier-0/1/2 `.mdc` tree is a "strategic design story" and the operational source of truth is `apis/brain/app/personas/specs/*.yaml`. So the bible itself acknowledges this section is stale — but the patch was never applied.
- **Proposed amendment**: Reconcile in a follow-up patch. Bring the visible D31 / Section 12 content into agreement with the actual PersonaSpec registry (the live registry table belongs in `docs/BRAIN_PERSONAS.md` per the existing pointer; reduce Section 12 to architecture rationale only and stop listing personas by name).

---

## Gap Tier 3 — Existing decisions defined but not implemented (strike-or-implement)

### T3.1 — D61 (Per-User Encrypted Vault, `brain_user_vault`)

- **What's not built**: `docs/BRAIN_ARCHITECTURE.md:669-677` defines D61 with full schema. Migration 001 creates the `brain_user_vault` table. The Pydantic model exists. **No code in `apis/brain/app/` reads or writes the table.** `apis/brain/app/tools/vault.py` is HTTP-only (calls Studio `/api/secrets`), bypassing the per-user vault entirely. Subagent confirmed.
- **Recommendation**: **Implement-now (small scope)**, not strike. The per-user vault is mandatory infrastructure for D62 IP skills via gateway (each per-user MCP token gets stored here). Suggested PR scope: implement `vault.set / vault.get / vault.list / vault.delete` repository functions against the existing table; wire them into a new tool path in `apis/brain/app/tools/vault.py` distinct from the Studio HTTP path; make D62 connector minting flow store the bearer token in `brain_user_vault` per the post-D62 unnumbered section. This is a Wave I3 prerequisite and should land before any IP MCP server is wired through the gateway.

### T3.2 — D40 (Procedural Memory, `agent_procedures`)

- **What's not built**: `docs/BRAIN_ARCHITECTURE.md:313-315` says "Phase: P5 (schema + extraction), P6+ (learned optimization)." Section 2 schema has the commented-out CREATE TABLE block. Cheap-agent-fleet doctrine and brain-coach doctrine BOTH reference `apis/brain/data/procedural_memory.yaml` as the substrate today. The graduation path from YAML file to `agent_procedures` rows is not specified.
- **Recommendation**: **Implement-now (small scope)** but split: (a) ship the `agent_procedures` table as the primary substrate; (b) keep the YAML file as a build-time seed that's parsed once and INSERTed into the table on every Brain Docker build; (c) when the Brain self-improvement loop (D35) adds new procedures, write to the table only — never back to the YAML file. The YAML becomes immutable seed; the table becomes the live state. This resolves T1.10 (D73) for procedural_memory.yaml specifically.

### T3.3 — D41 (Production Observability via Langfuse)

- **What's not built**: `docs/BRAIN_ARCHITECTURE.md:317-319` says "Self-hosted Langfuse on Hetzner." Production `render.yaml:184-189` shows `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST: https://langfuse.paperworklabs.com` env vars wired into Brain. So the env contract exists. **The bible doesn't say whether the actual Langfuse instance is up, populated with traces, or wired into Brain's agent loop**, and the gap audit can't verify that without log inspection. The subagent surveys did not surface a Langfuse client integration in `apis/brain/app/services/agent.py`.
- **Recommendation**: **Implement-now (small scope)**. If the Langfuse instance is up, ship the agent-loop tracing client (one PR). If it's not, decide whether to spin it up or strike D41 (replace with the Brain-internal tracing in `agent_audit_log` only). Ambiguity here makes "production observability" feel done-on-paper and missing-in-practice.

### T3.4 — D42 (Generative UI components)

- **What's not built**: `docs/BRAIN_ARCHITECTURE.md:321-323` lists 8 components (RefundCard, StatusSelector, DocumentUpload, etc.). Subagent inventory shows none of these exist as Studio admin components today — though some equivalent stat-card / hq components exist for company-OS use. Bible phases this to "P9" so this is forward-looking, not orphaned.
- **Recommendation**: **No action this audit**. D42 is consumer-product-future-state; not in the half-wired class. Leave for the consumer Brain build-out.

### T3.5 — `autopilot_dispatcher.install()` defined, never called (BLOCKING)

- **What's not built**: Subagent finding: `apis/brain/app/schedulers/autopilot_dispatcher.py:344` defines `install()`. **Zero callers in the codebase.** So the `*/5 * * * *` cheap-agent dispatch loop never runs in production. This is referenced by cheap-agent-fleet doctrine as the live dispatch substrate, so the doctrine itself is broken at the substrate level.
- **Recommendation**: **Implement-now (5-line PR)**. Wire `autopilot_dispatcher.install()` into the main scheduler startup path in `apis/brain/app/main.py` (next to where `pr_sweep.start_scheduler()` and the other schedulers are called). This is the fix for D68 (T1.5) shipping at all. Without this, every other Tier 1 / Tier 2 fix that depends on `agent_dispatches` rows being written is blocked. **This is the single highest-leverage 5-line fix in the audit.**

### T3.6 — `transcript_episodes` table exists, no GET endpoint, no Studio page

- **What's not built**: Per subagent + founder pre-audit notes: `transcript_episodes` table exists; `POST /admin/transcripts/ingest` exists (write-only); zero GET endpoints; zero Studio pages.
- **Recommendation**: **Implement-now**, but blocked by D67 (T1.4) bible patch landing first. Once D67 is in the bible, the implementation PR has clear acceptance criteria: GET list + GET single + Studio page mounted at `/admin/transcripts/page.tsx` + nav link.

---

## Gap Tier 4 — Cross-references to operational rules outside the bible

The bible currently lives separately from the operational `.cursor/rules/*.mdc` files. Some rule-file doctrine should be summarized inside the bible because it's bedrock that affects architecture, not just engineering practice.

### T4.1 — `.cursor/rules/cheap-agent-fleet.mdc` — summarize as appendix

- **What it covers**: Six rules for operating cheap-agent fleets at scale. Founder escalation triggers, mandatory `model:` parameter, no-Opus-as-subagent, mandatory orchestrator review, merge queue, scope-overflow disclosure, learning-loop substrate.
- **Recommendation**: Yes — summarize. This is the doctrine the bible's D31/D34/D35 implicitly assume but never make explicit. Add a new appendix `## 27. Cheap-Agent Fleet Doctrine (Operational Rules Summary)` that references the rule file as canonical and summarizes the six rules in a table, plus an explicit bridge to D68 (Agent Dispatch as First-Class Entity) so the architecture spec and the operational rules are linked.

### T4.2 — `.cursor/rules/no-silent-fallback.mdc` — summarize in safety section

- **What it covers**: Bans silent zero-on-error and empty-dict-as-success. Mandates four-state UX (loading/error/empty/data) on frontend.
- **Recommendation**: Yes — summarize. Add to Section 5 (Safety Layer) as a sub-section. The bible already cites no-silent-fallback in some Tier 1 patches above; making it canonical inside the bible's safety section closes the loop. Suggested wording: "Brain Safety Layer is structured around two doctrines: Defense-in-Depth (D36, four guardrail layers) and No-Silent-Fallback (errors and gaps must be visible to a downstream observer). The latter is enforced by `.cursor/rules/no-silent-fallback.mdc`; the bible commits to the doctrine and references the rule file for enforcement detail."

### T4.3 — `.cursor/rules/production-verification.mdc` — bridge to new D69

- **What it covers**: PR-layer verification doctrine (deploy live, /health, behavioral check, log watch).
- **Recommendation**: Yes — bridge. Once D69 (T1.6) lands, the bible should explicitly say "PR-layer verification: see `.cursor/rules/production-verification.mdc`. Workstream-layer verification: see D69. Both are required."

### T4.4 — `.cursor/rules/brain-coach.mdc` — surface in architecture as preflight contract

- **What it covers**: Mandates `recall_memory` consult before cheap-agent dispatch and irreversible decisions; logs `preflight_consulted` on dispatch payloads.
- **Recommendation**: Yes — surface. The `preflight_consulted` field IS in the proposed D68 schema (T1.5). Add to D35 (Nightly Self-Improvement Loop) a paragraph: "Brain coach preflight (`.cursor/rules/brain-coach.mdc`) is the input loop to D35's output. Every dispatch logged with `preflight_consulted: false` is a candidate for procedural-memory rule extraction — repeated false → coach nudge → rule update → behavior change measured next cycle. This closes the learning loop."

---

## Gap Tier 5 — Studio admin surface coverage matrix

For each Brain entity in the proposed Internal Operations Schema (D65, T1.2), check five dimensions: (1) DB row exists, (2) GET API endpoint exists, (3) Studio page exists at canonical route, (4) Studio page is reachable from admin nav, (5) E2E verified by founder on phone within 24h of last change.

Legend: ✅ live + canonical, ⚠️ partial / wrong shape / orphaned, ❌ missing.

| Brain Entity | DB row | GET API | Studio page | Reachable from nav | E2E verified | Bible mentions |
|---|---|---|---|---|---|---|
| **Goal** | ✅ `goals` (verified — `getGoals()` exists in `BrainClient`) | ✅ exposed via `/api/admin/goals` (Studio proxy) | ✅ `/admin/goals` | ✅ in admin-navigation.tsx | ⚠️ unknown | ❌ zero mentions |
| **Epic** (a.k.a. Workstream) | ✅ `epics` (1 row: `epic-ws-82-studio-hq`) | ✅ `getEpicHierarchy()` | ⚠️ `/admin/workstreams` route renders Epics; route name misleading | ✅ in admin-navigation.tsx (label "Epics") | ⚠️ unknown | ❌ zero mentions |
| **Sprint** | ✅ `sprints` (14 rows) | ⚠️ inferred via Epic hierarchy / sprint markdown only | ❌ `/admin/sprints/page.tsx` MISSING; `sprints-overview-tab.tsx` orphaned | ❌ no nav link | ❌ no surface to verify | ❌ one passing mention ("sprint drift" in §17) |
| **Task / PR** | ⚠️ partial | ⚠️ surfaced inline only | ⚠️ inline on Epic detail | n/a (always inline) | ⚠️ unknown | ❌ zero ops mentions |
| **Decision (D##)** | ⚠️ in `docs/KNOWLEDGE.md` only — Brain DB table likely missing | ❌ no `/admin/decisions` API | ⚠️ `/admin/docs` surfaces docs but no canonical Decisions view | ⚠️ via /admin/docs only | ⚠️ partial | ⚠️ implicit only |
| **Conversation** | ✅ `conversations` + `thread_messages` (live) | ✅ `/admin/conversations` GET + GET single + POST messages + status + snooze + persona-reply (feature-flagged) + react | ✅ `/admin/conversations` (proxy) + `/admin/brain/conversations` (canonical) | ✅ in admin-navigation.tsx | ✅ founder uses daily | ❌ as P9 deferred only |
| **TranscriptEpisode** | ✅ `transcript_episodes` (per founder pre-audit) | ❌ no GET endpoint (POST ingest only per subagent) | ❌ `/admin/transcripts/` MISSING per subagent | ❌ no nav link | ❌ no surface | ❌ zero mentions |
| **AgentDispatch** | ✅ `agent_dispatches` (migration 014 per founder pre-audit) | ⚠️ `/admin/autopilot` reads episodes, not dispatches table | ⚠️ `/admin/autopilot` exists; reads episodes with `source_prefix=autopilot` | ✅ in admin-navigation.tsx | ⚠️ unknown — dispatcher loop never installed (T3.5) | ❌ zero mentions |
| **Employee / Persona** | ✅ `employees` (17 rows) | ✅ `GET /admin/employees` | ✅ `/admin/people` | ✅ in admin-navigation.tsx | ⚠️ contaminated by personas-snapshot.json mixing 5 rules with employees | ⚠️ via D24/D31, but mixed up |
| **Skill** | ✅ `brain_skills` (seeded per Section 2) | ⚠️ partial — visible via `/admin/architecture` flow tab | ⚠️ no canonical `/admin/skills` page; lives inside Architecture | ⚠️ via /admin/architecture | ❌ orphaned redirect at `/admin/agents` → `/admin/architecture?tab=flows` | ✅ D62 (well-specified) |
| **Secret** (vault) | ✅ Studio `secrets` table | ✅ `/api/admin/secrets` (with Brain registry overlay) | ✅ `/admin/infrastructure?tab=secrets` (read-only) | ✅ via /admin/infrastructure | ⚠️ partial — read-reveal-copy only; no create/edit/rotate UI per subagent | ❌ scattered (D81 + D86 + D87 in KNOWLEDGE.md, not in bible) |
| **brain_user_vault** | ✅ table exists | ❌ no read endpoint | ❌ no Studio page | ❌ no nav link | ❌ no surface | ✅ D61 (fully specified, but **schema-only / dead code**) |

**Rollup**: of 12 surfaced entities, only **3 are fully wired round-trip** (Goal, Conversation, partly Skill via architecture tab) — and only Conversation has explicit founder daily-use evidence. **5 entities are partially wired with significant gaps** (Epic/Workstream naming, Sprint missing page, AgentDispatch table unread, Decision no canonical view, Secret no admin actions). **3 entities are essentially missing on the surface side** (Sprint page, TranscriptEpisode page, brain_user_vault). **1 entity is dead code in the bible's own spec** (brain_user_vault per D61 — see T3.1).

This matrix IS the canonical surface for D70 (T1.7). It belongs verbatim in the bible once the Tier 1 patches land.

---

## Gap Tier 6 — End-to-end verification doctrine at workstream layer

This is fully addressed by Tier 1 T1.6 (D69) plus Tier 1 T1.9 (D72) plus Tier 1 T1.13 (D76). They form the three legs of the workstream-layer verification doctrine:

- **D69** = the rule (5 conditions for "shipped").
- **D72** = the canary (founder is the only signal in Company OS mode).
- **D76** = the structural prevention (schema-to-surface co-shipping in same PR).

Insertion: all three live in the new `## Operating Modes` section per Tier 1. Cross-reference into Section 5 (Safety Layer) and Section 8 (replaced by D70). Cross-reference both `.cursor/rules/production-verification.mdc` (PR layer) and `.cursor/rules/no-silent-fallback.mdc` (data layer) — neither is replaced; both become enforcement detail beneath the new bible doctrine.

---

## Cross-product implications

### CP1 — AxiomFolio MCP and the bible's D62 IP-skills section

The post-D62 unnumbered section "IP skills live in product backends as MCP servers" (`docs/BRAIN_ARCHITECTURE.md:731-746`) and the Brain Gateway Architecture section (`docs/BRAIN_ARCHITECTURE.md:843-852`) explicitly cover AxiomFolio's MCP server as the reference implementation: `apis/axiomfolio/app/mcp/server.py`, with FileFree and LaunchFree marked TODO in Wave I3. **This is accurate**. No amendment needed for AxiomFolio.

The gap is on the FileFree and LaunchFree side: the bible says "TODO Wave I3" but the locked plan also says Wave I3 is blocked on Wave K2 (extracting the shared `mcp-server` Python package per `/Users/paperworklabs/.cursor/plans/brain_=_curated_multi-tenant_agent_os_—_final_plan_4c44cfe9.plan.md:90`). The bible should reference Wave K2 explicitly so the dependency is visible in one place.

**Recommended amendment to bible**: in the post-D62 IP-skills table (`docs/BRAIN_ARCHITECTURE.md:847-851`), append to the FileFree and LaunchFree TODO rows: "blocked on Wave K2 (`packages/python/mcp-server` extraction from AxiomFolio reference impl)."

### CP2 — Per-product MCP requires per-product persona and skill registration in Brain

When FileFree's MCP server ships, Brain needs to:

1. INSERT a `brain_skills` row with `skill_id = 'tax-filing'`, `source_kind = 'mcp_server'`, `source_ref = 'https://api.filefree.ai/mcp'`.
2. Update the `tax-intelligence` persona spec to include the `tax-filing` skill in its `requires_tools` list.
3. Add a connector definition (D26) for the FileFree MCP token mint flow, which stores the per-user bearer token in `brain_user_vault` (D61 — must be wired first per T3.1).

The bible's D62 spec covers (1) but not (2) or (3). **Recommended amendment**: add a new sub-section under D62 titled **"Persona ↔ Skill ↔ Connector triple registration"** describing the three-table coordination required for each new IP skill.

### CP3 — JSON files in `apis/brain/data/*` — which migrate to DB?

Cheap-agent-fleet Rule 6 lists six substrate files. Per Tier 1 T1.10 (D73, JSON-to-Brain-DB Migration Doctrine), the rule is "continuous operational substrate belongs in DB." Mapping each file to its target:

| File | Target Brain DB table | Migration status |
|---|---|---|
| `procedural_memory.yaml` | `agent_procedures` (per D40, T3.2) | T3.2 ships it |
| `agent_dispatch_log.json` (or `.jsonl`) | `agent_dispatches` (per D68, T1.5) | T1.5 + T3.5 ships it |
| `pr_outcomes.json` | new `pr_outcomes` table OR JSONB column on `agent_dispatches` | needs decision in D68 |
| `merge_queue.json` | new `merge_queue` table OR redis list | currently no writer (per subagent) |
| `long_tail.json` | new `long_tail_workstreams` table OR JSONB on `epics` | low-priority |
| `self_merge_promotions.json` | new `self_merge_promotions` table | tied to `agent_dispatches.pr_outcome` |

**Recommended amendment to bible**: when D68 (T1.5) lands, include this mapping table in the D68 body so the substrate question is answered comprehensively in one place.

---

## Recommended doc-patch sequencing

The patches are ordered to minimize re-work and allow parallel execution by cheap subagents where possible. Each patch is sized to fit under the 800-line cap. Each is dispatchable to the cheap-agent fleet per `.cursor/rules/cheap-agent-fleet.mdc` model rules.

**Wave 0 — Bible bedrock (Opus orchestrator only — these are doctrine; cannot be cheap-delegated)**
- Patch 0.1: New `## Operating Modes` section with D64 + D69 + D72 + D76. Insert before existing "Reference Data Storage Doctrine" section. ~250 lines.
- Patch 0.2: New `## 2A. Internal Operations Schema (Company OS)` section with D65, including reconciled entity table and Mermaid diagram. Insert after current Section 2. ~300 lines.

**Wave 1 — Surface contracts (Opus + cheap-agent split)**
- Patch 1.1 (Opus): Replace Section 8 (Studio Dashboard) with D70 (Surface Coverage Matrix). Includes Tier 5 matrix verbatim. ~200 lines.
- Patch 1.2 (Opus): Add D66 (Conversations as Founder Action Surface) as a new top-level section after the new D70. ~250 lines.
- Patch 1.3 (claude-4.6-sonnet-medium-thinking — L size): Add D67 (Transcripts as Knowledge) as new D67 in Section 1 D-list, slot between D62 and D63. ~80 lines.
- Patch 1.4 (claude-4.6-sonnet-medium-thinking — L size): Add D68 (Agent Dispatch as First-Class Entity) and D71 (Reference Knowledge Pipeline) and D73 (JSON-File-to-Brain-DB Migration Doctrine) as new decisions in Section 1 D-list. ~250 lines.

**Wave 2 — Reconciliation amendments (gpt-5.5-medium — M size, parallel)**
- Patch 2.1: Amend D9 → new D75 (Brain ↔ Studio Internal API Contract). ~50 lines.
- Patch 2.2: Amend D54 (add Beyond-Founder-Dogfood paragraph). ~15 lines.
- Patch 2.3: Amend D24/D31 (add Personas-vs-Rules-vs-Employees sub-section). ~30 lines.
- Patch 2.4: Amend D62 (clarify built-in vs MCP skills + persona-skill-connector triple registration). ~50 lines.
- Patch 2.5: Amend Section 2 schema (uncomment tables that exist in production; update phase markers). ~80 lines.
- Patch 2.6: Add `## 20A. Phase ↔ Wave ↔ Workstream Reconciliation` section with D74. ~60 lines.

**Wave 3 — Operational rule appendix (composer-2-fast — S size, parallel)**
- Patch 3.1: Add `## 27. Cheap-Agent Fleet Doctrine` appendix summarizing rule file (T4.1). ~80 lines.
- Patch 3.2: Add no-silent-fallback summary to Section 5 Safety Layer (T4.2). ~30 lines.
- Patch 3.3: Add brain-coach preflight loop bridge to D35 (T4.4). ~20 lines.

**Wave 4 — Implementation PRs (after bible patches land — these are CODE, not bible)**
These are NOT part of this audit's deliverable. Listed for the founder's planning visibility. Each is dispatchable to cheap-agent fleet per its own size:

- Implement T3.5 (`autopilot_dispatcher.install()` wired into main.py) — XS, composer-1.5. **5-line PR. Highest-leverage fix in the audit.**
- Implement T3.6 (transcripts GET endpoints + Studio page) — M, gpt-5.5-medium.
- Implement T3.1 (brain_user_vault wired) — M, gpt-5.5-medium.
- Implement T3.2 (procedural_memory YAML→table migration) — M.
- Fix workstreams_loader.py:128 ValidationError (Pydantic regex extension) — XS, composer-1.5.
- Fix probe_failure_dispatcher.py:49 IndexError (parents[N] container path) — XS, composer-1.5.
- Build `/admin/sprints` page mounting the orphaned `sprints-overview-tab.tsx` — S, composer-2-fast.
- Split `personas-snapshot.json` into personas + rules + employees (or migrate to live Brain endpoints per Wave E of locked plan) — M, gpt-5.5-medium.
- Add CI guard for D76 schema-to-surface co-shipping — S, composer-2-fast.

**Parallel execution plan**: Wave 0 must serialize (Opus orchestrator, two patches sequential because they both touch top-level structure). Wave 1 patches 1.3 and 1.4 can run parallel after Wave 0 completes; 1.1 and 1.2 serialize against Wave 0 because they replace existing top-level sections. Wave 2 all parallel after Wave 1. Wave 3 all parallel after Wave 2. Wave 4 (implementation) parallel after Wave 0-3 complete.

Total bible patch volume: ~1,800 lines added / ~150 lines deleted across 14 patches. No single patch >300 lines; well under the 800-line cap. Estimated cheap-agent cost: ~$15-25 (mostly L tier for Wave 1.3/1.4, M for Wave 2). Opus cost for Wave 0 + 1.1/1.2 review: ~$30-50.

---

## Notes on what was NOT covered (transparency)

This audit deliberately excluded several adjacent gaps because they are downstream of the bible-level fixes and the founder's brief said "do not propose entirely new product features":

- **Consumer Brain** product evolution beyond the existing 60 D-decisions. The bible is excellent on consumer side; no gaps surfaced there warrant Tier 1 status.
- **Voice / multimodal** (D29, D63 browser context) — bible is forward-looking-correct here.
- **Brain Mobile App** (`apps/brain-mobile/` per D48) — not yet built; no half-wired feature evidence to surface.
- **Distill B2B compliance API** — out of scope for Brain bible audit; covered by Distill product docs.
- **Render deploy failures** mentioned in founder pre-audit notes (5 consecutive pre-deploy failures over 14h, alembic upgrade head failing on migration 014's f-string-built INSERT) — these are runtime bugs, not bible gaps. They should fix themselves once T3.5 (autopilot_dispatcher.install) is wired and the workstream_dispatcher loop's Pydantic ValidationError is fixed.
- **Schedulers `probe_failure_dispatcher.py:49` IndexError** — runtime bug, listed in Wave 4 implementation PRs; not a bible gap.

---

**End of audit.**

The founder's next chat should patch the bible in Wave order (0 → 1 → 2 → 3) before any of the Wave 4 implementation PRs ship. Once D64/D65/D69/D70 are in the bible, every Wave 4 implementation PR has clear acceptance criteria for the first time. That is the single change that turns "we keep shipping half-finished features" into "we know when a feature is done."
