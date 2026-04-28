---
last_reviewed: 2026-04-24
doc_kind: architecture
domain: brain
status: active
---

# The Brain: Definitive Architecture v10

- **(a) Brain’s job (one sentence).** The Brain is the **agent runtime** for Paperwork: it **routes personas**, runs the **LLM + tool loop** in `apis/brain/app/services/agent.py`, and persists **memory** and **episodes** in Neon/Postgres with **per-response provenance** (`brain://episode/…`).

- **(b) Hard guarantees (today).** **Memory** and retrieval are org-scoped; user text is **PII-scrubbed** before the LLM and storage using `apis/brain/app/services/pii.py` (`scrub_pii`). **Persona routing** uses `apis/brain/app/personas/routing.py` and typed **`PersonaSpec`** contracts in `apis/brain/app/personas/specs/*.yaml` loaded through `apis/brain/app/personas/`. **Daily spend caps** are enforced **before** any provider call via `apis/brain/app/services/cost_tracker.py`. If **every LLM provider fails**, callers get a structured `llm_unavailable` result (`LLMUnavailableError`), not mock text. **Constitutional** checks in `apis/brain/app/services/agent.py` apply principles from `apis/brain/constitution.yaml` before a response is returned.

- **(c) What’s in motion.** Phase **D** (moving channel logic off n8n onto Brain’s HTTP surface), the **`PersonaSpec` registry** (16 personas today — see [`docs/BRAIN_PERSONAS.md`](BRAIN_PERSONAS.md)), and **doc/governance** work tracked in `docs/DOCS_STREAMLINE_2026Q2.md`.

**For the why** — refusals, trust model, and non-goals — see [`docs/philosophy/BRAIN_PHILOSOPHY.md`](philosophy/BRAIN_PHILOSOPHY.md). **For the who** (registry table, routing steps), see [`docs/BRAIN_PERSONAS.md`](BRAIN_PERSONAS.md).

The brain of Paperwork Labs — and eventually, everyone. A channel-agnostic AI life intelligence that serves two co-founders today and scales to millions of users as the meta-product of the entire venture. A wise partner that knows your entire life — finances, routines, relationships, preferences, experiences — remembers everything, connects dots, acts on your behalf, and gets smarter from corrections. Boundaries for licensed advice and refusals live in [`docs/philosophy/BRAIN_PHILOSOPHY.md`](philosophy/BRAIN_PHILOSOPHY.md) _(“Not a chatbot. Not a financial advisor.” and refusal framing moved to **Brain Philosophy** on 2026-04-24)._

**Internal**: Serves Paperwork Labs (Sankalp + Olga) from Phase 1.
**Product**: B2C personal brain, B2B team brain, Enterprise hierarchical brain with knowledge lifecycle — same backend, different org configs and UI layers.
**Meta-product** (F90): Brain IS the long-term platform. FileFree ("file your taxes"), LaunchFree ("form your LLC"), axiomfolio ("manage your portfolio") are skills/capabilities within it. The AI life intelligence that FileFree was always meant to become IS the Brain. Financial services are the trust-building entry point. The product is a partner that knows your entire life — finances, routines, relationships, preferences, experiences — and gets smarter every day. Products are the hands, Brain is the mind.
**Strategic anchors** (v10): Memory Moat (D49) — accumulated life context IS the product. Brain Fill Meter (D51) — psychology makes the moat visible and viral. Tiered Email Processing (D52) — metadata-only free tier at $0.03/mo makes the economics work at any scale. Life Intelligence System (D58) — the Brain is equally strong across all life domains, weighted by the user's own data. Contextual Intelligence Monetization (D59) — Credit Karma playbook with 5-10x the signal. Proactive Insight Delivery (D60) — five-channel system so the Brain TELLS you things.

Stress-tested from 10 review lenses: Anthropic safety (Amodei), OpenAI scaling (Altman), Perplexity retrieval (Srinivas), DeepMind intelligence (Hassabis), CTO production review, Top 5 AI Leads (Karpathy/Fan/Chase/Weng/Askell), Jony Ive/Steve Jobs B2C UX, Andrew Chen Growth/Social, brain.ai competitive analysis, McKinsey strategic architecture review. 11 rounds, 228 findings, all integrated. 60 design decisions. 16 **registered** personas in the `PersonaSpec` layer (4-tier orchestration model in §12). 7-agent automated content engine for psychology-driven GTM. This is the long-form **product + systems** spec for Brain design; companion `docs/BRAIN_PERSONAS.md` and `docs/philosophy/BRAIN_PHILOSOPHY.md` cover the **registry** and **policy** (replaces the old “no supplemental docs” claim; 2026-04-24).

### Core implementation index

| Concern | Where it lives (repo paths) |
|--------|-----------------------------|
| HTTP app / entry | `apis/brain/app/main.py` |
| Agent loop, constitution, `process()` | `apis/brain/app/services/agent.py` |
| Persona keywords / `route_persona` | `apis/brain/app/personas/routing.py` (legacy shim: `apis/brain/app/services/personas.py`) |
| Model routing & chains (incl. `ClassifyAndRoute`, `PersonaPinnedRoute`, `ExtractAndReason`) | `apis/brain/app/services/router.py` |
| Daily cost cap (Redis) | `apis/brain/app/services/cost_tracker.py` |
| Constitution principles (YAML) | `apis/brain/constitution.yaml` |
| Persona contracts (YAML) | `apis/brain/app/personas/specs/*.yaml` |
| Spec schema (Pydantic) | `apis/brain/app/personas/spec.py` |
| PII regex scrub (D11) | `apis/brain/app/services/pii.py` (log filter: `apis/brain/app/utils/pii_scrubber.py`) |
| CI / coverage for specs | `apis/brain/scripts/check_persona_coverage.py` |

---

## 1. Design Decisions (D1-D60)

### D1. Brain API is its own Render service

Service: `brain-api` on Render Standard ($25/mo from P1 — NOT Starter, F59/F68). Domain: `brain.paperworklabs.com`. Code: `apis/brain/` (greenfield). Database: Same Neon instance, `agent_*` tables. Kept warm by watchdog pings + Neon connection warmup (F7).

### D2. Agent loop in Brain API from Phase 1

No n8n intelligence. Brain API owns: input normalization, persona routing, model/chain selection, prompt assembly, LLM call, tool dispatch, iteration (max 5), response. n8n is a thin channel adapter only.

### D3. Prompt caching from day one

Static prefix (system + persona + wisdom + org personality): ~4K tokens, cached at 90% discount. Dynamic (profile + memories + thread): ~5-10K tokens, full price. Saves 30-40% on input costs. Provider-specific: Anthropic requires explicit `cache_control` breakpoints; OpenAI auto-caches. `supports_cache_control: bool` on ModelProvider protocol (F97).

### D4. Query reformulation before memory search

Mini model rewrites raw message into optimized search query. Cost: ~$0.001. Dramatically better recall.

### D5. Hybrid retrieval (vector + FTS + entity + graph + RRF)

Four paths merged with reciprocal rank fusion. Weights: vector=0.4, FTS=0.35, entity=0.15, graph=0.10. Configurable per-persona. Past 10K episodes, add cross-encoder re-ranker. 4th path (F61): 1-hop entity graph traversal from matched entities — THE differentiator from flat RAG.

### D6. Multi-user with privacy from day one

Episodes have `visibility`: `organization`, `team`, `personal`, `shared`. Defaults: public Slack=org, DMs with brain=personal, personal email=personal, work email=org. `shared` visibility (D53): episodes scoped to a Circle (couples, family, partners) — visible to all circle members but not the broader org. Recall query: user sees personal + their team(s)' + org + their circle(s)' episodes.

### D7. Cost philosophy: excellence first, track always

Use the best model for each task. Never downgrade quality. Prompt caching and model chaining save cost without touching quality. Exception (F30): Gemini Flash for structured extraction (genuinely better AND cheaper).

### D8. Smart thread management

1-10 msgs: full text. 11-20: pre-computed summary of 1-10 + full 11-20. 21+: ingest as episode, suggest new thread. Thread context never exceeds ~4K tokens.

### D9. Internal authentication

`BRAIN_API_SECRET` shared between n8n and Brain API. Every `/brain/process` requires `Authorization: Bearer <secret>`. Separate from user auth.

### D10. Request idempotency

`request_id` (Slack `ts`) checked in Redis (5-min TTL). Redis failure: skip check, accept rare duplicates (F3).

### D11. PII scrubbing on all text

SSN, EIN, CC, phone, bank routing numbers scrubbed before storage via regex. Extended patterns in P2 (F9). NER-based detection (Presidio) for enterprise at P9 (F49).

### D12. Full multi-tenant backend

`organization_id TEXT NOT NULL` on all persisted multi-tenant tables (F1: includes entities, edges, summaries; P9 circle tables below) with **no default** — app layer MUST set explicitly on every insert. Internal dogfood instance uses `'paperwork-labs'`; consumer B2C users get auto-generated org IDs; B2B API callers provide their own. This prevents accidental cross-tenant data leaks. Every query org-scoped. Dual auth: internal secret → `paperwork-labs`, external API key → lookup org. Per-org rate limiting and storage quotas (F10).

### D13. Persona .mdc caching with versioning

Redis 1-hour TTL. Cache miss: GitHub fetch. Redis failure: GitHub direct (F3). Git SHA logged per request for prompt versioning (F110).

### D14. Explicit model fallback chains

Opus → Sonnet → GPT-4o → basic mode. Sonnet → GPT-4o → Flash → basic mode. GPT-4o → Flash → Sonnet → basic mode. Basic mode saves to memory if DB reachable.

### D15. Memory fatigue

Recently-recalled episodes penalized 0.5x in RRF via Redis tracking (24hr TTL). Redis failure: skip fatigue (F3). On-topic thread exemption: if follow-up matches thread summary, don't penalize (F63).

### D16. Correction boosting

Detection: hybrid keyword matching + GPT-4o-mini confirmation. Correction stored at importance=0.95, verified=true. Corrected episode gets quality_signal=-1. Cross-founder correction conflicts surface in daily briefing (F23). When detection confidence <0.8, brain asks: "Did you mean to correct what I know, or are you telling me something new?" (F105).

### D17. Tool execution guardrails

| Tool | Tier | Timeout | Retries |
|------|------|---------|---------|
| read_file, search_code, list_prs | Tier 0 (auto) | 15s | 2 |
| recall_memory, get_entities | Tier 0 (auto) | 5s | 2 |
| web_search (20/day cap) | Tier 0 (auto) | 10s | 2 |
| remember, forget, update_memory | Tier 0 (auto) | 5s | 2 |
| ask_user (max 1/request, F92) | Tier 0 (auto) | — | 0 |
| create_task | Tier 1 (auto+notify) | 10s | 1 |
| update_doc (docs/ only) | Tier 2 (draft+approve) | 15s | 1 |
| draft_pr | Tier 2 (draft+approve) | 30s | 1 |
| merge_pr, send_email, delete_* | Tier 3 (must approve) | 30s | 1 |

Per-tool timeout via `asyncio.wait_for` (F4). Tool-level retry with exponential backoff (F91): retryable errors = 429, 503, timeouts; non-retryable = 400, 401, 403, 404. Concurrent independent tools via `asyncio.gather` in P3 (F16). Structured output mode for all tool dispatches (F106).

### D18. User-facing error messages (transparent)

Brain API timeout: "Thinking hard..." (retry once). 5xx: "Something went wrong. Logged it." Rate limit: "Busy moment. Trying again..." (auto-fallback). All down: "Having technical issues. Message saved." Injection: "I can't help with that." Neon down: "I can still chat but won't remember this conversation until my database recovers." Model fallback: "Using a backup AI model — I might be slightly less detailed than usual." (F101)

### D19. Hierarchical Brain (org → team → individual)

Three-level knowledge hierarchy. Organization brain (company-wide). Team brain (team-specific). Individual brain (personal). Knowledge flows: down (inheritance), up (promotion), lateral (cross-team via org brain), temporal (lifecycle). Schema: `team_id` (nullable) on episodes, entities, summaries. Recall query: user sees personal + their team(s)' + org episodes. Cross-org access structurally impossible — validated by integration tests (F104).

### D20. Model Chaining (5 patterns)

Not fallback (if A fails, try B). Chaining = pipeline (A does step 1, feeds to B for step 2).

**Pattern 1 — SearchAndSynthesize**: Gemini Flash + Google Search grounding → Claude Sonnet synthesis. For live data queries. Cost: ~$0.016 vs $0.034 single-model.

**Pattern 2 — ExtractAndReason**: Gemini Flash extracts → Claude Sonnet reasons. For large documents. 58% cheaper.

**Pattern 3 — ClassifyAndRoute**: Gemini Flash classifies intent + complexity → routes to optimal model. 70-80% of queries are simple (→ Mini). CoT vs. direct answer also decided here (F111). Saves ~25-46% on model costs (sensitivity-dependent, F56).

**Pattern 4 — AdversarialReview**: Sonnet generates → GPT-4o critiques → Sonnet revises. For Tier 2/3 actions.

**Pattern 5 — Consensus**: Parallel Claude + GPT-4o + Gemini → synthesize. For critical financial/legal/compliance questions.

Architecture: `ChainStrategy` protocol. ClassifyAndRoute default from P3.

### D21. Knowledge Lifecycle

**Onboarding**: Create user → link team(s) → brain auto-assembles knowledge package. User productive day 1.
**Offboarding**: Classify departing employee's episodes → institutional knowledge promoted to team scope → personal archived → brain generates handoff package.
**Role change**: Update team linkage. Personal context travels. New team knowledge immediately available.

### D22. Company Onboarding Pipeline (5 phases)

1. **Account Setup** (2 min): Sign up, create org, name brain, invite team
2. **Connect Data Sources** (5-15 min): OAuth connections (Google first for B2C, Slack first for B2B)
3. **Knowledge Seeding** (background, 1-24 hr): Gemini Flash bulk extraction, quality gate, PII scrub, entity graph build. Batch embedding in groups of 100 (F107).
4. **Brain Training Interview** (3 min, optional): Conversational Q&A to seed profile
5. **Progressive Intelligence** (immediate → 24hr): Brain useful in 5 min, fully intelligent in 24 hr. Brain communicates its knowledge state (F40).

**B2C "First 5 Minutes" Experience (F223):** The first 5 minutes must produce a LIFE wow, not just a financial summary:

| Time | Event | What User Sees |
|------|-------|---------------|
| 0:00 | Landing | "Your Brain wakes up in 60 seconds" |
| 0:30 | Google OAuth (one tap) | Gmail + Calendar + Maps start flowing |
| 1:00 | Real-time counter animates | "Learning... 47... 128... 312... 589 things" |
| 2:00 | Brain Fill Meter hits 65% | First insight: "14 subscriptions, $287/mo" |
| 3:00 | Lifestyle insight | "You eat out 3x/week. Top spot: [restaurant], 6 visits" |
| 4:00 | Relationship insight | "Date night is usually Fridays" |
| 5:00 | The hook | "I learned 847 things in 5 minutes. Want to ask me anything?" |

The wow is "Brain knows my LIFE and I didn't tell it anything." Not "Brain knows my subscriptions."

### D23. Memory Classification Framework

**GREEN (store freely)**: Decisions, project status, process docs, architecture decisions, entity relationships.
**YELLOW (store with scrubbing)**: Public Slack (quality gate + PII scrub), DMs with brain (personal scope), email summaries (never full body), calendar entries, PR summaries.
**RED (never store)**: Passwords, SSN/EIN/tax IDs, full CC/bank numbers, health info, salary, other users' private DMs, full external email bodies, biometric data.

### D24. Brain Persona System

Per-org customizable personality injected as cached prefix. Identity, voice (tone, formality, brevity, humor, emoji), values with behaviors, communication rules, forbidden zones, knowledge priorities. Customized during onboarding. Per-user adaptation within org personality. Voice selection for TTS (D29).

**Persona Platform (Phase D, 2026Q2)** — formalizes persona contracts as typed YAML specs (`apis/brain/app/personas/specs/<name>.yaml`) paired 1:1 with `.cursor/rules/<name>.mdc` written instructions. Operator routing steps and the live table are in [`docs/BRAIN_PERSONAS.md`](BRAIN_PERSONAS.md); the bullets below are the **architecture** rationale. Each spec declares `default_model`, `escalation_model`, `escalate_if` rules (compliance, tokens>N, mention:<slug>), `requires_tools`, `daily_cost_ceiling_usd`, `compliance_flagged`, `confidence_floor`, `owner_channel`, and `mode`. Enforcement at runtime:

- `PersonaPinnedRoute` skips the Gemini-Flash classifier when a spec exists and routes straight to the spec's model (saves a classifier call per request, makes the routing deterministic).
- `daily_cost_ceiling_usd` is enforced via a Redis-backed `CostTracker` that increments atomically and fails fast with a structured `cost_ceiling_exceeded` error before hitting the provider.
- Input tokens counted with `tiktoken` (not the old `len//4` heuristic) so `tokens>N` escalation is accurate.
- LLM failures raise `LLMUnavailableError` and produce a structured `llm_unavailable` response — no silent mock fallbacks.
- `compliance_flagged` + `confidence_floor` combine to stamp `needs_human_review: true` on the episode metadata and response payload; Studio surfaces the flag, and D7 will turn it into a blocking review queue.
- CI enforces three-way coverage (`apis/brain/scripts/check_persona_coverage.py`): every router-producible persona must have a YAML spec and an `.mdc` file.

Studio renders the live registry at `/admin/agents` via Brain's `GET /api/v1/admin/personas` endpoint. Full details: [docs/BRAIN_PERSONAS.md](./BRAIN_PERSONAS.md).

**Consumer Brain Personality (F225):** `personality_mode: consumer` variant — warm but not sycophantic, slightly witty, celebrates without judging, remembers like a best friend, gets noticeably better over time:

| Trait | Example | Anti-Pattern |
|-------|---------|-------------|
| Slightly witty | "8 Thai restaurants this month — I think we can call it an obsession." | "You frequently dine at Thai restaurants." |
| Celebrates | "3 trips in Q1 — someone's got wanderlust." | "You traveled 3 times." |
| Remembers like a friend | "Last time in Portland you loved that ramen place." | "Your Portland trip included dining at [restaurant]." |
| Gets better over time | Generic early (Day 1), personal by Day 30, eerily accurate by Day 90 | Same tone forever |
| Never judges | "Your food budget is up — you've been exploring!" | "Your food spending is excessive." |

### D25. Explicit Memory Tools

Memory operations as first-class tools: `remember(content, scope, importance)`, `recall(query, scope, limit)`, `forget(episode_id)`, `update(episode_id, correction)`. Background ingestion runs separately. Conversation-level memory is explicit and transparent.

### D26. Connections Architecture

OAuth framework with `Connector` protocol (authorize, sync, health_check, revoke). Sync engine: scheduler → enqueue → workers → transform → ingestion pipeline. Connection health: healthy, degraded, error, expired, revoked. Connector roadmap: 10 first-party → Zapier → Connector SDK.

### D27. Pricing Architecture

Introductory staircase model: $29 Year 1, $49 Year 2+. The moat deepens with time — by Year 2, the Brain knows 2,000+ things and switching cost is prohibitive. The $20 increase ($1.67/mo) is invisible against what you'd lose.

| Tier | Target | Year 1 Price | Year 2+ Price | Memory Retention | Brain structure | Limits |
|------|--------|-------------|---------------|------------------|-----------------|--------|
| **Free** | Individuals | $0 | $0 | 1 year | Single brain | 100 msg/mo (F70), 2 connections, 1K episodes |
| **Personal** | Power users | $29/yr | $49/yr | 5 years | Single brain | Unlimited msg, 10 connections, 50K episodes |
| **Together** | Couples | $49/yr | $79/yr | Lifetime | Personal x2 + Circle | Everything in Personal + shared calendar + joint meter + "Our Year in Review" |
| **Family** | Households | $79/yr | $129/yr | Lifetime | Together + up to 5 | Everything in Together + kid profiles + family calendar |
| **Team** | Small teams (3+) | $19/user/mo | $19/user/mo | 5 years (configurable) | Shared team + individual | Everything in Personal + team knowledge sharing |
| **Business** | Mid-market (10+) | $15/user/mo | $15/user/mo | Configurable | Org + teams + individual | Multiple teams, SSO, 1M episodes |
| **Enterprise** | Large orgs | Custom | Custom | Configurable | Full hierarchy + lifecycle | Unlimited, SOC 2, data residency, SLA |

Memory retention as conversion lever: Free = 1 year (`data_retention_days: 365`), Personal = 5 years (`1825`), Together/Family = lifetime (`unlimited`), Team = 5 years configurable. "Your Brain remembers 1 year of your life. Upgrade to remember everything, forever." Text memories are tiny (~10MB/user/year). 10 years of life = ~100MB. Nightly consolidation compresses old episodes into summaries, so raw old data sits on cold storage while summaries stay hot.

Pricing in outcomes, not technical units (F84): Free = "Your Brain wakes up." Personal = "Your Brain remembers everything, forever." Together = "Your shared Brain." Family = "Your family Brain." Team = "Your team's shared brain."

Revenue model: subscriptions are the engagement wrapper (~25% of revenue). The real revenue is contextual intelligence monetization — Credit Karma playbook with 5-10x the signal (D59, ~50% of revenue). Lifestyle intelligence at scale (~25% at 500K+ users). See D59 for full model.

### D28. Enterprise Compliance

SOC 2 Type II: 6-18 months, $30-200K. GDPR: data export, erasure, portability, rectification endpoints. DPA auto-generated for Team+. Data residency via Neon regions. Admin audit log (separate table). Remember tool consent model in ToS: org-scoped memories are organizational property (F51).

### D29. Voice Architecture

**Voice Input (STT)**: Browser Web Speech API for real-time (zero latency). OpenAI Whisper API as fallback. "Hold to record" voice notes. Phase: P8 (basic), P9 (polished).

**Voice Output (TTS)**: OpenAI TTS-1 (~$0.003/response). TTS-1-HD for emotional moments. Voice selection as part of persona config. "Read aloud" button on any response. Phase: P9.

**Voice Conversation (full duplex)**: Deferred P10+. "Voice note in, text + optional TTS out" covers 90% of mobile use cases.

### D30. Brain Technical Advisory Personas (5 AI Leads)

The Brain's self-monitoring advisory board — 5 personas that watch over the Brain's health, quality, and evolution. Complement the operational personas.

| Persona | Domain | Inspired by |
|---------|--------|-------------|
| Agent Infrastructure Lead | Loop reliability, tool execution, tracing | Jim Fan |
| ML Systems Lead | Model efficiency, latency, embeddings | Andrej Karpathy |
| Retrieval & Knowledge Lead | RAG quality, knowledge graph, memory health | Harrison Chase |
| Product AI Lead | Response quality, trust, correction rate | (composite) |
| Safety & Alignment Lead | Output safety, PII, constitutional compliance | Dario Amodei / Amanda Askell |

Weekly Brain Health Report (F65): each persona contributes a section. Intelligence Index (F66): each owns components. Nightly consolidation (P4): each runs analysis. Invocable by founders via @-mention.

### D31. Hierarchical Persona Architecture (4 tiers, 16 registered personas in `PersonaSpec`)

See Section 12 for full specification.

### D32. Social/Viral Mechanics (Brain Moments)

See Section 13 for full specification.

### D33. Automated Social Content Engine

See Section 13 for full specification.

### D34. Three-Layer Evaluation Architecture

Organize agent evaluation into three measurable layers from P1:

- **Reasoning layer**: Plan quality score (LLM-as-judge), plan adherence rate
- **Action layer**: Tool selection accuracy, argument correctness (deterministic check)
- **Execution layer**: Task completion rate, step efficiency (steps taken vs optimal)

New columns in `agent_audit_log`: `plan_quality_score`, `plan_adherence_rate`, `tool_calls_correct`, `tool_calls_total`, `argument_hallucination_count`, `task_completed`, `steps_taken`, `optimal_steps`, `step_efficiency`, `guardrail_triggers`, `user_rating`. Phase: P1 (schema), P2 (populate metrics), P5 (full eval suite).

### D35. Nightly Self-Improvement Loop

Concrete cron pattern that compounds quality: (1) Collect day's traces — failed tasks, low-confidence outputs, correction signals. (2) Analyze — LLM reviews failure patterns, identifies highest-impact improvement. (3) Implement — auto-generate candidate config change. (4) Audit — run candidate against golden test set. (5) Report — generate performance delta; if improvement > threshold, flag for promotion; if regression, discard. Implementation: n8n workflow `brain-self-improvement.json` at 2am PT. Gemini Flash for analysis. Phase: P3 (basic loop), P5 (full with golden suite + auto-promotion).

### D36. Defense-in-Depth Guardrail Architecture

Four-layer pattern, each logging independently: Input Filter (pattern scan + injection classifier) → Tool Call Guard (validate args, enforce tiers, block unauthorized) → LLM Processing → Output Filter (critique-revise loop + PII mask + fact verification). Each layer tracks `guardrail_triggers` in audit_log. Trigger rate is a weekly KPI in the Brain Health Report. Phase: P1 (input + tool + basic output), P2 (critique-revise + fact verification).

### D37. Versioned Constitutional AI

Upgrade from 5 hardcoded assertions to a versioned, auditable `apis/brain/constitution.yaml`. Each principle has id, name, rule, severity, examples. At inference: after LLM response, a critique step evaluates against the active constitution version. Violations trigger auto-revise with specific principle citation. All violations logged with `principle_id` for trend analysis. `constitution_version` column in audit_log. Phase: P1 (file + logging), P2 (critique-revise loop).

### D38. Circuit Breaker + Gateway Pattern

Explicit circuit breaker on model fallback chains: track failure rate per provider in Redis (5-min sliding window). If failure rate >50% in window, remove provider from pool for 60s. Error classification: 429 (retry after delay), 503 (skip immediately), context overflow (route to larger context model). All routing decisions logged with `routing_reason`. Gateway abstraction normalizes all providers via `ModelProvider` protocol with provider-specific error handling. Phase: P1 (circuit breaker), P3 (full gateway).

### D39. Comprehensive Connection Roadmap

**Tier 1 — Core (P9 launch)**: Plaid Link (bank accounts, credit cards, investments), Google Workspace (Gmail, Calendar, Drive), Tax Documents (W-2, 1099 via OCR), Slack (team communication), Manual Entry.

**Tier 2 — Enhanced (P9+3mo)**: Plaid Financial Insights, Plaid Investments, Apple (CalDAV/CardDAV), Microsoft 365 (Graph API), Notion, Linear, GitHub (expanded).

**Tier 3 — Advisory (P10)**: Zillow API (home value), Credit Bureau (Experian/TransUnion), Plaid Income, Insurance (Canopy Connect), Student Loans (Plaid Liabilities), Crypto (Coinbase), Vehicle Value (KBB).

**Tier 4 — Full Advisor (P10+)**: Estate planning, Business Entities (SOS filings — LaunchFree data), HSA/FSA, 529 Plans, Social Security (SSA API), Mortgage Rates.

Meta-aggregator consideration: Quiltt wraps Plaid + MX + Finicity. Evaluate at P9. Schema supports all from P1 (D26).

### D40. Procedural Memory

Third memory tier alongside episodic and semantic. Episodic = "what happened." Semantic = "what we know." Procedural = "what works" — learned procedures from compressed trajectories. Schema: `agent_procedures` table with `trigger_pattern`, `steps` JSONB, `reliability_score`, `times_executed`, `times_succeeded`, `source_episode_ids`. Example: after 5 successful W-2 → refund estimate flows, brain extracts a procedure. Low-reliability procedures deprioritized. Phase: P5 (schema + extraction), P6+ (learned optimization).

### D41. Production Observability via Langfuse

Self-hosted Langfuse on Hetzner (alongside n8n, Postiz). Unlimited traces at $0/mo. Captures: prompts, responses, tool calls, latency, token consumption per trace. Prompt versioning + A/B testing UI built in. Docker Compose addition to `infra/hetzner/`. Every agent call produces a Langfuse trace linked to `agent_audit_log.request_id`. Phase: P3 (deploy + basic), P5 (full dashboards + A/B testing).

### D42. Generative UI Pattern

LLM outputs structured JSON blocks alongside text. Frontend maps block types to interactive React components rendered inline in chat. Component registry: RefundCard (animated count-up, confetti), StatusSelector (full-width cards, not radio buttons), DocumentUpload (camera trigger, scan animation), BreakdownChart (collapsible 120px, full-screen on tap), AssumptionCard (pre-filled fields, single-tap confirmations), ActionChips (suggested next actions as tappable pills), ProcessStepper (animated phase indicator with checkmark cascade), PaymentPlanCard (interactive monthly calculator). Implementation: Vercel AI SDK `useChat` with function calling. Phase: P9 (UI), component registry designed in P1 (F106).

### D43. Trust Escalation Ladder

Progressive trust through demonstrated competence. Five rungs: (1) Zero-risk action — snap W-2, see estimate, no account, no PII. (2) Competence demonstration — extracted fields with confidence scores, green checkmarks. (3) Data trust — SSN entry ONLY after user reviews extracted data, with explicit reassurance. (4) Financial trust — bank connection offered ONLY after reviewing completed return. (5) Submission trust — swipe-to-confirm for irreversible filing. Anti-pattern: asking for SSN on screen 2 before demonstrating value. Phase: P9 (product UI), principle informs P1-P8 internal UX.

### D44. Anxiety-Reducing Financial UX

Six patterns: (1) Contextual reframing — "You owe $3K" becomes "Gap of $3K because [reason]. Here's what to do." Explain → normalize → empower. (2) Positive-first framing — lead with wins, never shame. (3) Calm metric density — 3-5 numbers max per screen, everything else behind "View Full Breakdown." (4) Progressive disclosure with emotional pacing — three-level drill-down with Framer Motion transitions. (5) Chunked response bubbles — break long AI responses into sequential chat bubbles (50-100ms delay). (6) Personality modes (Cleo-inspired) — Encouraging (default), Direct, Detailed. Same data, different emotional delivery. Phase: P9 (UI), personality modes in P4.

### D45. Tax Season Wrapped

Spotify Wrapped-style shareable experience post-filing. 6-card shareable story (1080x1920): (1) "You filed in X minutes" — speed flex. (2) "You saved $89" — TurboTax comparison. (3) "Your refund: $X,XXX" — opt-in positive only. (4) "Top X% of fast filers" — optimal distinctiveness. (5) "Tax personality: [archetype]" — Barnum Effect. (6) "Biggest win: [deduction/credit]" — celebrate smart moves. Zero PII on shared cards. One-tap share via Web Share API. QR code embedded. Launch April 15-18. LaunchFree version: "LLC Launch Wrapped." Phase: P9.

### D46. Double-Sided Referral Engine

Variable-reward mechanics (Cash App $10 CAC, Robinhood 53% lower CAC). FileFree: referrer gets $5 credit, friend gets priority + free state return, activation = completed return (not signup), variable bonus card ($1-$25, scratch-off psychology). Pre-launch waitlist: exact position visible, jump 1K spots per referral, target 50-100K signups. Anti-fraud: device fingerprinting, KYC on redemption, cap 50/user/year. Cross-product loops: FileFree → "Form LLC free" → LaunchFree → "File biz taxes free" → FileFree. Phase: waitlist at pre-launch, referral at P9.

### D47. Community Growth Flywheel

Five channels: (1) Reddit organic — 90/10 rule, founder accounts, 3-5 answers/day in r/tax + r/personalfinance. (2) TikTok — 2-3x/day tax season, hook-first, Spark Ads $20-50/day bursts. (3) Programmatic SEO — 200+ pages from packages/data/ (state calculators, LLC costs, deduction guides). (4) Discord — #tax-questions, #refund-tracking, UGC submissions. (5) UGC flywheel — post-filing social cards, user tip submissions, r/FileFree subreddit. Phase: Reddit + TikTok pre-launch, SEO at P9-3mo, Discord at tax season.

### D48. Mobile App Strategy (Expo React Native)

iOS + Android via Expo in pnpm monorepo. 60-75% code sharing with Next.js via Solito + NativeWind. NOT PWA (iOS camera bugs), NOT native Swift/Kotlin (2x maintenance), NOT Flutter (Dart, no code sharing). The Brain IS the app — one chat, all products. Structure: `apps/brain-mobile/` with Expo Router. Native-only: expo-camera, expo-notifications, expo-local-authentication (biometrics), expo-haptics, Reanimated. Costs: $99/yr Apple + $25 Google + 15% IAP commission. 6-8 week MVP. Phase: P9 parallel track.

### D49. The Memory Moat: Brain as Universal Life Vault

**The single most important design decision.** Intelligence is commodity. Accumulated personal life context is irreplaceable. The Brain's memory IS the user's vault — life context across every domain: financial identity (income, spending, tax situation, accounts), lifestyle patterns (dining preferences, travel history, fitness routines, entertainment habits), relationships and social graph (partner, family, friends, colleagues), experiences and milestones (trips, date nights, achievements, life events), routines and preferences (favorite spots, weekly patterns, seasonal habits), documents, credentials (encrypted vault column, biometric-gated), business data, professional contacts.

The moat equation: `Switching cost = Σ(accumulated memories × time × trust)`. The moat deepens across ALL life domains — not just finances.

**Individual moat timeline**: Day 0: connect Google (Gmail + Calendar + Maps). Day 7: knows subscriptions, top restaurants, commute pattern. Day 30: knows spending habits, dining preferences, fitness routine, social circle, weekly patterns. Day 90: knows lifestyle archetype (foodie? adventurer? homebody? fitness person?) without the user ever declaring it. Day 365: irreplaceable — not just your accountant, your memory. Years of accumulated life context in ~10MB/year, trivially cheap to store forever.

**The couple moat is 2x** (D53): Day 30 — shared Netflix, same restaurants, overlapping subscriptions detected. Day 90 — "Our Brain" knows shared restaurants, trips, date nights, joint spending, shared calendar. Day 180 — shared life context deeply entangled: "You two always go Italian on Fridays, tried 12 Thai places, visited Portland and Austin, work out Saturdays." BOTH people need to switch. Two people locked in, not one. Social pressure to stay is stronger in couples.

Email-first onboarding inverts the model: passive ingestion → user amazed → wants more. One Google OAuth = years of life data. Brain Fill Meter shows accumulation. Free tier: unlimited ingestion + 10 queries/month. Personal: unlimited queries + full vault. Revenue: paying to TALK TO your own accumulated life context. Phase: core concept P1, vault encryption P2, email ingestion P7, fill meter P9.

### D50. Email Ingestion Pipeline

Three-provider architecture: Gmail API (OAuth2 + Pub/Sub + history.list), Microsoft Graph (OAuth2 + webhooks + delta query), IMAP fallback (Yahoo, iCloud, ~5% of users). Gmail: 2-step fetch, 15K quota units/min, 10K emails in ~3.3 min. Microsoft: delta query returns full messages inline (better than Gmail). Google verification: restricted scope, 6-12 week CASA assessment ($540+/yr) — START IN P7. 7-phase pipeline: fetch → filter (60% killed) → fetch bodies → classify (Gemini Flash) → extract (GPT-4o-mini batch 50% off) → dedup (JWZ + entity) → store. Hybrid extraction: regex pre-extracts → LLM verifies. Top 50 sender parsers handle 80% without LLM. Email schema: parsed_emails, email_transactions, email_line_items, detected_subscriptions, vendors. Phase: P7 (Gmail + pipeline), P9 (Microsoft + IMAP + full onboarding).

### D51. Brain Fill Meter as Psychological Growth Engine

Eight stacked psychological effects: (1) Endowed Progress (Nunes & Dreze 2006, 34% vs 19%) — never start at zero, jump to 15-20%. (2) Goal Gradient (Hull 1934) — acceleration near milestones. (3) Zeigarnik (1927) — incomplete tasks remembered 90% better, meter never "done." (4) Loss Aversion (Kahneman & Tversky 1979) — 2x pain multiplier on paywall. (5) Psychological Ownership — data feels "theirs" pre-payment. (6) Variable Ratio Reinforcement (Skinner) — unpredictable insight quality = dopamine. (7) Optimal Distinctiveness (Brewer 1991) — "top 22%" = belong AND stand out. (8) Sunk Cost — every day the counter grows. Six gamification levels: Awakening (100), Awareness (250), Understanding (500), Insight (1K), Mastery (2.5K), Omniscience (5K). Duolingo-adapted notifications: curiosity → FOMO → loss aversion → social pressure → friend reactivation. Three shareable card formats: Identity, Surprise, Archetype. Seven TikTok formats. Monthly rolling Brain Report Cards. Phase: P9.

### D52. Tiered Email Processing ("See vs. Understand")

**Cost breakthrough.** Free-user onboarding: $5.45 → $0.05 (99% reduction). Metadata alone (sender, subject, timestamp, labels, snippet) contains 60-70% of knowledge value. MIT Immersion (2013): 3 metadata fields reveal "deaths, transitions, former loves." Free tier uses `gmail.metadata` scope (less scary OAuth): sender-domain classification (500+ known domains), subject-line regex (amounts, order #s), frequency analysis (subscriptions), timestamp analysis (behaviors), thread analysis (social graph). Result: 600-800 items in 30 seconds, zero LLM. Paid tier adds 5 optimization layers: metadata-first skip 40%, sender templates skip 20%, representative sampling reduces LLM 90%, Gemini Flash 33% cheaper, Batch API 50% off. Cross-user template amortization: User #1's Chase template serves Users #2-10K. Cost decreases with scale. Privacy advantage: "We never read your emails" for free tier. Upgrade prompt: "Your Brain detected 14 subscriptions. Upgrade to see what they cost." Break-even: 1.5% conversion (vs 13% before). 100K free users: $3K/month. Phase: metadata pipeline P7, tiered logic P9.

### D53. Circle Sharing (Couples, Family, Partners)

A "Circle" is a lightweight sharing group between 2+ users — couples, roommates, family, co-founders. Not an org, not a team. A personal-scope sharing primitive for B2C that creates a shared life context.

**The `shared` visibility in D6 becomes real.** Episodes with `visibility: 'shared'` and a `circle_id` are visible to all circle members. Each person's personal Brain stays private. The Circle creates a "Third Brain" — a shared entity that knows things neither individual Brain knows alone (total household spending across both accounts).

**Sharing suggestions by circle type (owner must approve every share — no auto-sharing, ever):**

| Circle Type | Suggested for Sharing | Owner Opt-In Only | Never Shared (structurally blocked) |
|-------------|----------------------|-------------------|-------------------------------------|
| Household (couple) | Calendar, contacts, subscriptions, shopping, travel, home | Bank accounts, investments | SSN, passwords, vault items |
| Family (parents+kids) | Calendar, school/activities, health | Shopping, contacts | Finances, vault |
| Roommates | Shared bills, rent, subscriptions | Calendar | Everything else |
| Business partners | Business calendar, shared tools, clients | Personal | Everything personal |

**The Brain detects, the owner decides.** No data moves between scopes without explicit human action. The Brain SUGGESTS: "I noticed you both get emails from State Farm. Want to share this?" The owner must tap to confirm. No background auto-tagging, no "smart defaults," no bulk-approve.

**Conversational interface — life, not just finances:** "Share my Amazon spending with Olga" → owner explicitly tags connection as shared. "How much did we spend on food?" → queries circle scope. "What are we doing Saturday?" → shared calendar. "Where should we go for dinner?" → uses location history + cuisine preferences from both members. "Plan our anniversary" → trip history + restaurant favorites + calendar availability. "What movies are out?" → Fandango/AMC history + preference matching. "Remember that Portland ramen place?" → instant recall from shared trip memory. In circle context, the Brain speaks as "we/us/our" — not "you." This isn't cosmetic; it validates the partnership.

**Overlap detection from email metadata:** When two Circle members both receive emails from Netflix, Amazon, State Farm, their landlord — the Brain detects the overlap and SUGGESTS sharing. Owner must approve each one individually. Detection itself is opt-in during circle setup — owner can disable it entirely. The metadata pipeline (D52) makes detection free.

**Privacy within the Circle is sacred:** Circle members see shared episodes, NEVER each other's personal data. Brain proactively reassures: "Your personal data stays private. Only shared items are visible to both."

**Circle Safety Protocol:**
- **Offboarding**: Either member can leave unilaterally. Access to shared episodes revoked immediately. Shared episodes remain for other members, marked "former." No data is deleted.
- **Anti-abuse**: No member can delete another's data. No member can see another's personal episodes. Circle creator has no admin override on privacy.
- **No auto-sharing**: All sharing requires explicit owner action. Brain suggests, never acts. First circle setup includes a consent flow explaining what detection and sharing mean.
- **Constitutional enforcement**: P006 (circle privacy) and P007 (delegate scope) — see Section 5.

**12 strategic properties of Circles:**

1. **Micro-network effect** — one person's email contribution benefits both. Olga's insurance renewal email becomes knowledge Sankalp's Brain also has.
2. **The invitation IS the viral mechanic** — "Join my Circle" is functional, not promotional. Cash App grew on "send me money via Cash App." Brain's version: "I need you on this so our Brain works for both of us." k-factor built into the product.
3. **Calendar is the trojan horse** — immediately useful Day 1 ("What are we doing Saturday?"), before financial intelligence kicks in.
4. **Kids are the lock-in multiplier** — school emails, pediatrician, activities, daycare. The Brain becomes the family operating system.
5. **Family pricing = 3x stickier** — Family plan: $39/yr for 2 ($19.50/person). Spotify Family: 10% churn vs 30% individual.
6. **Asymmetric contribution** — the "organizer" partner's work benefits both. The "disorganized" partner gets organized without effort. Both are satisfied.
7. **Overlap detection is the "wow"** — overlapping services detected from metadata, surfaced as suggestions. Owner approves each one. Zero setup required.
8. **The "we" pronoun IS the product** — "Our Brain says we spent $1,200 on food" is shared discovery. "Your Brain says you spent too much" is judgment.
9. **"Our Year in Review"** — couple Wrapped variant that covers your entire shared life, not just finances:
```
OUR YEAR TOGETHER — 2026
Trips: Portland, Austin, Napa, surprise Joshua Tree weekend
Restaurants: 47 date nights. Top cuisines: Thai (11x), Italian (8x), Japanese (7x)
Movies: 23 together. You both loved Dune 3.
Routines: Farmers market 38 Saturdays. Gym together 12x.
Financial: Saved $4,200 vs last year. Biggest win: switching insurance.
Together: 14 months. Brain fill: 2,847 things about your life together.
```
Couples love sharing their life together. Extremely viral.
10. **Circle > Household** — co-founders, freelancer + bookkeeper, roommates, parent + adult child managing elder care. `circle_type` determines sharing suggestion defaults.
11. **The Third Brain** — each person has a personal Brain. The Circle creates a third entity. It knows things neither individual knows alone.
12. **2x the moat** — two people locked in, not one. Social pressure to stay ("we have 2 years of shared history") is stronger in couples than individuals.
13. **Lifestyle is daily engagement, daily moat** — financial queries are seasonal (tax time, bill surprises). Lifestyle queries are daily ("Where should we eat?", "What are we doing Saturday?", "Remember that place in Austin?"). Daily engagement = daily moat deepening.
14. **Brain is the couple's shared memory** — "Remember that Portland ramen place?" is not a query to a database. It's a conversation with a partner who was on the trip. The Brain becomes the couple's collective memory — the thing that remembers what both of you forget.

**Pricing:** Free tier: personal brain only. Personal ($29 Y1 / $49 Y2+): personal + 1 circle. Together ($49 Y1 / $79 Y2+): personal x2 + household circle + shared calendar + joint meter + "Our Year in Review." Family ($79 Y1 / $129 Y2+): Together + up to 5 + kid profiles. Team ($19/user): org brain. Natural couple upsell: "Your Brain detected you and @olga share 3 accounts. Upgrade to see shared insights."

Phase: P9 (schema + owner-approved sharing + calendar + safety protocol), P10 (overlap detection suggestions, joint meter, "Our Year in Review").

### D54. Dual-Context Architecture (Founder Dogfood)

Same person, multiple brain contexts. Sankalp has: (1) personal Brain (B2C app) for personal life — finances, lifestyle, routines, preferences, (2) Paperwork Labs org Brain (B2B Slack) for company ops, (3) household Circle (shared with Olga) for joint life — trips, restaurants, shared finances, routines, date nights. Same backend, different org/circle scopes per request.

**Channel determines context:** Slack `#engineering` → `organization_id: 'paperwork-labs'`. App chat (default) → `organization_id: 'sankalp-personal'` (auto-created). Shared finances query → includes `circle_id` scope.

**Context switching in app:** Default is personal brain. Tap org avatar in header to switch. Or conversational: "Ask my work Brain about the deploy schedule." "Switch to our shared Brain." Brain responds with context indicator: "[Personal]" or "[Paperwork Labs]" or "[Household]".

**Strategic importance:** Sankalp and Olga are the first customers of every tier — Free (personal brain), Pro (circles), Team (org brain). They exercise every feature before any external user touches it. If it works for two co-founders who share both a business and personal expenses, it works for anyone.

Phase: Already supported by D12/D19 architecture. Context switching UI in P9.

### D55. Cross-Context Query Composition

When a question spans multiple scopes (personal + circle + org), the Brain composes intelligence from all accessible contexts via parallel retrieval and scope-aware fusion.

**Retrieval scope by active context:**

| Active Context | Retrieval Scope | Example |
|----------------|-----------------|---------|
| Personal | personal + circle(s)' shared + org visible | "What are my deductions?" |
| Circle | shared circle episodes only (privacy-safe) | "What did we spend on food?" |
| Org | org + team(s)' + personal (D19) | "What's our deploy schedule?" |
| Cross-context (auto-detected) | all accessible scopes, composed with attribution | "Can we afford to hire?" |

**Cross-context detection:** ClassifyAndRoute (D20 Pattern 3) adds a scope classifier. When a question touches 2+ scopes, the Brain: (1) Detects scope overlap via keywords + entity graph. (2) Retrieves from all relevant scopes in parallel (`asyncio.gather`). (3) Composes response with clear source attribution: "[Personal]" / "[Household]" / "[Paperwork Labs]". (4) Respects privacy boundaries — never leaks one circle member's personal data into shared context.

**Scope-aware RRF weights:**

| Context Mode | Personal Weight | Circle Weight | Org Weight |
|-------------|-----------------|---------------|------------|
| Personal | 0.55 | 0.25 | 0.20 |
| Circle | 0.20 | 0.80 | — |
| Org | 0.20 | — | 0.50 (team 0.30) |

**Five real-world scenarios:**

1. **Tax Time**: "What are my deductions?" → personal deductions + business expenses (org) + shared home office pro-rata (circle). Response: "Your personal deductions: $12,400. Business deductions through Paperwork Labs: $3,200. From your household, the home office may qualify for $1,800."
2. **Budget**: "What did we spend on food?" → circle-only. Never leaks individual spending. Response: "Your shared food spending: $440 groceries + $361 dining."
3. **Investment**: "Should we invest in better servers?" → Brain detects cross-context ambiguity, clarifies: "Are you asking about Paperwork Labs infrastructure, or a personal investment?"
4. **Overlap detection**: Both Circle members get State Farm emails → Brain SUGGESTS: "You and Olga both receive emails from State Farm. Want to share this as a household expense?" Owner must approve.
5. **Hiring**: "Can we afford to hire?" → Requires org Brain (budget) + personal awareness (runway). Response: "[Paperwork Labs] Current monthly burn: $58. [Personal] Your runway covers 18 months. A $2K/mo contractor is viable for both."

Phase: P9 (scope classifier in ClassifyAndRoute), P10 (cross-context golden test set).

### D56. Brain Identity System

Each context has a visual identity so the user always knows which Brain they're talking to at a glance.

**Visual specification:**

| Context | Avatar | Ring Color | Label |
|---------|--------|------------|-------|
| Personal | User's avatar | Product gradient (violet-purple) | "[Personal Brain]" |
| Circle | Two overlapping circles (merged member avatars) | Dual-color gradient (both members' colors) | "[Household]" or circle name |
| Org | Company logo | Org-themed ring | "[Paperwork Labs]" |
| Delegate view | Owner's avatar + lock icon | Muted gray | "[Shared with you by Sankalp]" |

**Context pill**: Below message input, small tappable pill showing the active context. Tap opens context picker with all available brains. Always visible — the user should never be confused about scope.

**Response attribution**: Each message carries a subtle context badge in the header. Cross-context responses (D55) show multiple badges: "[Personal + Household]".

**Conversational switching**: "Switch to our shared Brain" / "Ask my work Brain about the deploy." Brain confirms switch: "Switched to [Paperwork Labs]. What do you need?"

Phase: P9 (context pill + avatar + switching), P10 (delegate view, cross-context badges).

### D57. Delegated Access (Controlled Sharing)

One-directional, purpose-scoped, time-limited, fully audited sharing. You share specific knowledge FROM your Brain TO someone else (CPA, advisor, lawyer, friend), with comprehensive misuse prevention.

**Two sharing patterns coexist:**
- **Circle (D53)** = joint bank account — mutual, ongoing, bidirectional, owner-approved per item
- **Delegated Access (D57)** = power of attorney — one-way, category-scoped, time-limited, revocable, fully audited

**Three-layer anti-misuse architecture:**

**Layer 1 — Against data leaks (someone copies/exports your data):**
- No bulk export for delegates — data rendered in-app only, no download
- Watermarking: all data shown to delegates carries owner identity ("Shared by Sankalp")
- Mobile: `FLAG_SECURE` (Android) + screen capture notification (iOS) on delegate views
- Suspicious access detection: Brain monitors patterns (200+ episodes in 5 min = scraping → auto-revoke + alert owner)
- Full audit trail: every data access logged with timestamp, IP, device fingerprint
- Rate limiting: max 20 queries/day, 100 episodes viewed/day per delegate

**Layer 2 — Against over-access (they see more than intended):**
- Category-scoped: owner defines EXACTLY which categories ("tax + income + deductions" but NOT "personal + health + vault")
- Structurally impossible categories: SSN, passwords, vault items can NEVER be shared, even if owner tries to grant it
- Share preview: before activating, owner sees exactly what the delegate will see
- Progressive disclosure: delegate starts at summary level, must REQUEST detail access (owner notified + must approve)
- Never-share list enforced at the query layer — delegate queries that would return forbidden categories get filtered

**Layer 3 — Against lingering access (they keep access after you're done):**
- Mandatory expiration: every share has an expiry (default 30 days, max 1 year, no "forever" option)
- Auto-revocation triggers: purpose completed ("until return is filed"), inactivity (14 days no access), instant owner revoke
- Expiration reminders: "Sarah's access to your tax data expires in 7 days. Extend or let expire?"
- Nightly zombie detection: flags shares not accessed in 30+ days, suggests cleanup
- Grace period: ZERO — revocation is instant

**Conversational interface:**
- "Share my tax data with Sarah for 30 days" → creates delegated access, sends invite
- "What can Sarah see?" → shows current share scope + access log
- "Revoke Sarah's access" → instant revocation, Sarah notified
- "Who has access to my Brain?" → full audit view (delegates + circles)
- "Show me Sarah's access history" → timestamped log of every query and view

**Delegates cannot query the Brain conversationally** — they see a read-only dashboard of category-scoped data. Cannot create episodes, modify entities, or interact with the Brain on the owner's behalf.

Phase: P9 (basic delegated access + audit trail), P10 (progressive disclosure, suspicious pattern detection, delegate dashboard).

### D58. Life Intelligence System

**The Brain is NOT a financial advisor with memory. It is a life intelligence system that happens to monetize exceptionally well through financial products.** Financial services are the trust-building entry point. The product is a partner that knows your entire life.

**Signal sources for lifestyle intelligence:**

| Source | What It Reveals | Integration |
|--------|----------------|-------------|
| Email metadata (D52) | Subscriptions, purchases, services, travel bookings, restaurant reservations, event tickets, fitness memberships | P7 (existing pipeline) |
| Google Calendar | Date night frequency, gym schedule, travel dates, social density, routines, recurring commitments | P9 (existing connector) |
| Google Maps Location History | Restaurant visits (cuisine, frequency, neighborhood), gym visits, store visits, commute, travel destinations | P9 (D39 Tier 1 addition) |
| Plaid transactions | Spending categories confirm email/location signals, dining spend, travel spend, subscription costs | P9 (existing connector) |

**Lifestyle archetype inference:** The Brain infers identity archetypes — "foodie," "movie lover," "adventure couple," "fitness person," "homebody," "traveler," "night owl" — from behavioral signals without the user ever self-declaring. A person does not need to tell the Brain they like food — the Brain knows from 47 restaurant visits on Google Maps, 11 OpenTable confirmation emails, and $2,400/mo dining spend on Plaid.

The Brain never labels users to their face ("You're a foodie"). It simply acts on the pattern: "You've been to 4 Italian restaurants this month. There's a new one opening near your Thursday date night spot — reservations open tomorrow."

**All life domains are equal.** The Brain surfaces across finance, travel, food, fitness, hobbies, and couples with no domain hardcoded as primary. The user's data determines which domains are richest. Each domain follows the same pattern: ingest signals → infer preferences → remember across time → surface contextual insights.

| Domain | Example Insight | Signal Sources |
|--------|----------------|----------------|
| Finance | "Your subscriptions are up 20% this quarter." | Plaid + email |
| Travel | "Last time in Portland you loved that ramen place on Burnside." | Maps + email + calendar |
| Food | "You've tried 8 new restaurants this month — new record." | Maps + Plaid + email |
| Fitness | "You run more on weeks you sleep 7+ hours." | Strava/Health + calendar |
| Hobbies | "You've read 3 sci-fi books this quarter — here's what's new." | Email + purchases |
| Couples | "Last anniversary was Napa — want something different this year?" | Calendar + Maps + email (both members) |

No vertical app has cross-domain memory. Mint knows money. TripAdvisor knows places. Strava knows workouts. Yelp knows restaurants. The Brain knows YOU — across all of them, over years.

**For couples (D53), this is transformative.** The Circle Brain knows: trips together (flight/hotel confirmation emails from both members), restaurants and date nights (shared calendar + location visits + booking confirmations), movies (Fandango emails + AMC visits), shared hobbies (both get ClassPass emails = fitness couple), routines ("You two go to the farmers market every Saturday morning").

**Memory retention is trivially cheap:** Text memories are ~10MB/user/year. 10 years of someone's entire life = ~100MB (the size of 20 iPhone photos). Nightly consolidation compresses old episodes into monthly/quarterly summaries — raw data sits on cold storage, summaries stay hot. At 100K users with 5 years each: ~5TB on Neon (~$3,750/mo). At 10K users: ~300GB (~$200/mo). Memory is not a cost problem.

**Retention arc** (lifecycle engagement by domain):
- **Week 1**: Lifestyle hooks dominate — restaurants, routines, subscriptions. Daily engagement.
- **Month 1**: Financial value lands — "Your insurance went up 18%." First high-impact moment.
- **Month 3**: Circle suggestion — "You and [partner] share 4 subscriptions." Retention multiplier.
- **Year 1**: Brain Wrapped — "23 trips, 47 date nights, 156 restaurants, $4,200 saved." Irreplaceable.

Pattern: lifestyle hooks early (daily engagement from day 1), financial value mid-term (high-impact but less frequent), couple expansion in the middle (retention multiplier). This avoids the "seasonal tool" trap — the Brain stays relevant year-round because life doesn't stop after tax season.

Phase: P9 (email metadata lifestyle signals, Google Maps connector, archetype inference), P10 (Spotify/Strava/Health connectors, advanced archetype modeling).

### D59. Contextual Intelligence Monetization

Revenue model inspired by Credit Karma ($2.3B FY2025, 140M members, ~$16/member/year, $0 subscription, acquired by Intuit for $8.1B) but with 5-10x the signal per user and a conversational delivery channel.

**Three revenue layers coexist:**

**Layer 1 — Subscription (~25% of revenue):** The engagement wrapper. Keeps users active so the referral engine has signal. Introductory staircase: Free → Personal $29 Y1 → $49 Y2 → Together $49 Y1 → $79 Y2 → Family $79 Y1 → $129 Y2 → Team $19/user/mo.

**Layer 2 — Financial product referrals (~50% of revenue):** Credit Karma playbook. Brain notices something about your financial life and mentions it in conversation — like a smart friend, not an ad. Insurance comparison (CPA $50-100), banking/savings referral (CPA $100-200), credit card referral (CPA $100-300), tax filing (FileFree, $30-50/return), LLC formation (LaunchFree, $20-100).

| What Brain Notices | What It Says | Tone | Revenue |
|-------------------|-------------|------|---------|
| Insurance renewal up 15% | "Your car insurance renewed at $180, up 15%. Want to check if you could pay less?" | Concerned friend | $50-100 CPA |
| $15/mo checking, $0 interest | "Your Chase checking charges $15/mo. Fee-free accounts earn 4% APY." | Financial advisor | $100-200 CPA |
| 1% cashback, heavy dining | "A dining card could earn $960/yr instead of $240." | Smart friend who did the math | $100-300 CPA |
| Freelance income, no LLC | "$85K freelancing. An LLC could save $3-5K in self-employment tax." | Business advisor | $20-100 |
| W-2 arrived, hasn't filed | "Your W-2 arrived last week. 5 minutes to file?" | Personal assistant | $30-50 |
| Unused subscriptions | "3 subscriptions unused in 60+ days, $87/mo." | Frugal friend | $0 (trust builder) |

**Layer 3 — Lifestyle intelligence (~25% at scale):** Activates at 500K+ users when signal density justifies partner integrations. Subscription optimization ("3 streaming services overlap — here's a bundle"), dining deals (OpenTable/Resy partnerships), travel deals (contextual, not generic), experience recommendations.

**7 "not recommendy" design principles:**

1. **Earn before you recommend** — Brain demonstrates value 5+ times before any monetized recommendation. First 2 weeks = pure helpful insights.
2. **Insight-first, product-second** — "Your insurance went up 15%" (the insight) before "want to compare?" (the action). Never lead with the product.
3. **User controls the volume** — settings toggle: Financial suggestions On / Occasional / Off. Default: Occasional.
4. **Math shown** — every recommendation shows the calculation. "You'd save $720/yr" with the work visible.
5. **Celebrate the save, not the switch** — "You saved $60/mo!" not "Congrats on signing up for [Partner]!"
6. **Some insights are free** — subscription audit, spending trends, deadline reminders generate zero revenue. They build trust. Trust converts to revenue downstream.
7. **Transparency badge** — "Brain Suggestion" label on any recommendation that generates a referral. Honest about the business model.

**Targeted acquisition strategy (not spray-and-pray):** Focus on 10K high-intent users, not 100K random:

| Cohort | Entry Point | Why They Convert | Target |
|--------|------------|-----------------|--------|
| Tax season filers (Jan-Apr) | "File your taxes free" (FileFree) | Already trusting with W-2 + SSN. Brain is the upsell. | 3,000 |
| New LLC formers | "Form your LLC free" (LaunchFree) | Need compliance reminders, tax planning. Brain = business OS. | 2,000 |
| Freelancers/self-employed | TikTok/Reddit deduction content | Pain is constant (quarterly taxes). Brain solves it permanently. | 2,500 |
| Couples moving in together | "Manage your shared life" (Together) | Immediate need: who pays what? Shared subscriptions? | 1,500 |
| New grads with first W-2 | "File your first return free" | Lifetime customer at 22. Brain grows with their life. | 1,000 |

Expected 15-25% conversion (not 2.5%) because they have active need when they arrive. At 20% conversion on 10K: ~2,000 paid users Year 1 — comparable to 2,500 from 100K random, with 10x fewer free users to support. Cost savings: $112K/yr.

Phase: P9 (referral partnerships, recommendation engine, "Brain Suggestion" UI), P10 (lifestyle partnerships, advanced CPA optimization).

### D60. Proactive Insight Delivery

Five-channel system for the Brain to TELL users things without waiting for them to ask. The Brain is not a search bar — it's a partner that notices things and brings them up.

**Insight pipeline:** Nightly consolidation (2am PT) analyzes new emails, spending changes, upcoming deadlines, insurance renewals, subscription changes, lifestyle patterns, anomalies. Generates ranked "Insight Queue" per user (impact × urgency). Channels deliver based on impact + urgency + user preferences.

**Five delivery channels:**

1. **In-app proactive message** (default: ON) — When user opens app, Brain has a message waiting: "Hey, I found 3 things while you were away." Notification dot on Brain icon. First message = highest-impact insight.

2. **Push notification** (default: ON for high-impact) — Threshold: insights worth >$50/yr savings or deadlines <7 days. Max 1 push/day. "Your quarterly taxes are due in 5 days. Want me to estimate?" NEVER push product recommendations — push is for YOUR data, not partner products.

3. **Weekly Brain Brief** (email digest, default: ON) — Every Monday: "Your Brain Brief — 3 things from this week." Top 3 insights, brain fill progress, one recommendation. Clean, mobile-optimized React Email template. This is the HABIT LOOP (D51): Cue = Monday email, Action = check insights, Reward = peace of mind or surprising save.

4. **Real-time alerts** (rare, high-urgency only) — Triggered immediately, not nightly: "Your LLC annual report is due TODAY." "Your bank flagged unusual activity" (Plaid webhook). Push + in-app + email simultaneously.

5. **Circle notifications** (Together/Family tiers) — "Your shared Brain detected a new subscription: Disney+ $13.99." Sent to both circle members simultaneously. "Together you spent $1,200 more than last month. Want a breakdown?"

**Notification escalation** (connects D51 psychology to delivery channels):

| Day Since Last Open | Channel | Message Type | Psychology |
|--------------------|---------|-------------|-----------|
| 0 (same day) | In-app only | Proactive insight waiting | Curiosity |
| 1 (23.5 hours) | Push | "Your Brain found something interesting" | FOMO |
| 3 | Push + email | "Your Brain learned 12 things while you were away" | Loss aversion |
| 5 | Push + email | "Your Brain is 67% full. Slowing down without you." | Sunk cost |
| 7+ | Email only | Friend reactivation nudge | Social pressure |
| 14+ | Stop notifications | Respect the user's choice | Integrity |

**What the Brain NEVER does:**
- Never wakes you up for non-urgent insights (respects `active_hours` from user profile)
- Never sends more than 1 push/day
- Never recommends a financial product via push (recommendations only in-app or email)
- Never shares circle insights without both members' consent
- Never sends notifications about things the user explicitly dismissed

Phase: P6 (basic notification architecture), P9 (full 5-channel delivery, Weekly Brain Brief, escalation), P10 (advanced personalization, optimal send time).

### D61. Per-User Encrypted Vault

Separate from memory (D23 RED classification = "never store passwords/keys"). The vault is a secure sidecar for credentials the Brain uses on behalf of the user — API keys, OAuth tokens, service passwords.

Schema: `brain_user_vault` table with AES-256-GCM encryption (same pattern as Studio's `secrets` table). Fields: `user_id`, `organization_id`, `name`, `encrypted_value`, `iv`, `auth_tag`, `service`, `description`, `expires_at`, `last_rotated_at`, `created_at`.

The Brain knows you HAVE a key (stored as a GREEN episode: "User has OpenAI API key"). The actual key lives in vault, never enters LLM context. Brain accesses vault via tool: `vault_get(name)` — Tier 0 auto tool. Value returned to tool execution layer only, never injected into prompt. Vault access requires user auth (not just Brain API secret). Biometric gate in mobile app (Phase 11-full). Vault items are structurally blocked from Circle sharing (D53) and Delegated Access (D57) — even if an owner tries to grant it.

Phase: P1 (schema), P2 (Brain tool integration), P9 (mobile biometric gate).

### D62. Platform Brain and Skill Registry

The "Super Brain" / "Brain of all Brains" implemented as a reserved organization, not a separate service. The existing D12 multi-tenant architecture supports a three-level platform hierarchy with zero additional infrastructure:

```
organization_id = 'platform'              — Platform Brain (root)
  ├── Skill registry (brain_skills table)
  ├── Cross-user learned templates (D52 amortization)
  ├── World knowledge (aggregated, anonymized)
  └── Platform procedures (D40)

organization_id = 'paperwork-labs'        — Org Brain (venture ops)
  ├── Venture decisions, tasks, architecture
  ├── Layer 1 skills (tax-filing, llc-formation, compliance)
  └── Team/individual brains for co-founders

organization_id = 'user-{uuid}'           — Personal Brains
  ├── Inherited skills from platform (gated by plan tier)
  ├── Personal connections (Gmail, Plaid, Chrome extension)
  └── Circle memberships (D53)
```

Schema addition to `agent_organizations`: `parent_organization_id TEXT` (nullable). NULL for `'platform'` (root), `'platform'` for all org and personal brains. Establishes parentage without a separate service.

Skill registry: `brain_skills` table with `skill_id`, `name`, `description`, `category`, `tier` (free/personal/team/enterprise), `connector_id` (nullable, links to D26 connector), `tools` JSONB, `knowledge_domains` JSONB, `requires_connection` boolean, `owner_organization_id` (default `'platform'`), `status`.

Skill enablement: `brain_user_skills` table. Users "install" a skill by creating a row. The `tier` column on `brain_skills` is the single gate — when a free user tries to enable a `personal`-tier skill, the system returns "upgrade to unlock." One column, not separate tables or separate brains per tier. The platform brain determines availability via one query:

```sql
SELECT s.* FROM brain_skills s
JOIN brain_user_skills us ON us.skill_id = s.skill_id
  AND us.user_id = :user_id AND us.organization_id = :org_id
WHERE s.tier <= :user_plan AND s.status = 'active';
```

Initial skill registry:

| skill_id | name | tier | category | connector_id |
|---|---|---|---|---|
| tax-filing | Tax Filing | free | financial | null (built-in) |
| llc-formation | LLC Formation | free | financial | null (built-in) |
| financial-calculators | Financial Calculators | free | financial | null (built-in) |
| email-metadata | Email Intelligence | free | financial | google-workspace |
| calendar-insights | Calendar Insights | free | lifestyle | google-workspace |
| email-full | Deep Email Analysis | personal | financial | google-workspace |
| location-history | Location Intelligence | personal | lifestyle | google-maps |
| bank-transactions | Bank Transactions | personal | financial | plaid |
| browser-context | Shopping and Browsing | personal | shopping | chrome-extension |
| couple-brain | Shared Circle | personal | lifestyle | null (built-in) |

How skills grow over time: (1) Paperwork Labs builds Layer 1 skills as products ship. (2) Connections-as-skills via D26/D39 — each OAuth toggle is a new skill. (3) Procedural memory (D40) learns procedures for existing skills. (4) Nightly self-improvement (D35) optimizes quality. (5) Future: Zapier/Make integration at 100K+ users opens 5,000+ connections. Third-party Connector SDK only if developer ecosystem justifies it.

Phase: P1 (schema + platform org seed), P2 (skill enablement logic), P9 (consumer skill marketplace UI).

### D63. Browser Context Connector

Added to D39 Connection Roadmap as Tier 2.5 (P10, paid tier only). A Chrome Extension (Manifest V3) that captures browsing context for real-time intent signals — the difference between knowing what happened last week (email metadata) and knowing what is happening right now.

**Captures:**
- Page visits (URL + title + timestamp, NOT page content)
- User-triggered screenshots (hotkey, NOT auto-capture). Visual context processed via GPT-4o vision / Gemini Pro Vision.
- Shopping signals (product pages via schema.org/Product detection, price tracking)
- Search queries (opt-in subcategory, off by default)

**Connector:** `BrowserConnector` following D26 protocol (authorize, sync, health_check, revoke).

**Privacy design (the line between wow and creepy):**
1. Paid tier only — user pays Paperwork Labs, not the other way around
2. Granular opt-in — "Enable shopping assistant" / "Enable travel assistant" as separate toggles, not blanket access
3. Personal-scope only — browser data NEVER enters org or circle raw data. Insights derived from browsing can be shared ("she's been looking at these shoes") but raw history cannot.
4. Full transparency — user can view everything captured and delete any item
5. "Brain noticed" framing — "I noticed you've been looking at flights" not "I tracked your browsing"

**Killer use cases (cross-referencing browser context with existing memory):**
- Flight shopping + Maps history: "Flights to Portland are $89 cheaper on Southwest. Last time you were there, you loved that ramen place on Burnside."
- Partner birthday + Circle calendar: "Olga's birthday is in 12 days. She's been looking at [product]. It's $40 off at [store]."
- Repeated product views: "Those Nikes you looked at 3 times this week are 30% off."

**Schema addition:** Optional `visual_context_url TEXT` on `agent_episodes` for screenshot references.

**Trinket Factory candidate:** The Chrome extension can start life as a Trinket (Phase 1.5 candidate) — a standalone "deal finder" browser extension at `tools.filefree.ai`. Standalone value (finds deals), feeds the Brain when connected. Users install it for deals; it becomes a Brain data source.

Phase: Trinket v1 (Phase 1.5 candidate), Brain connector (P10, paid tier only).

---

## 2. Memory Schema

All fixes applied. Full schema created in P1 Alembic migration (CTO-1). `agent_conversations` added at P9 (CTO-6).

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Organization
CREATE TABLE agent_organizations (
    id SERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL UNIQUE,
    parent_organization_id TEXT, -- D62: NULL for 'platform' (root), 'platform' for all others
    name TEXT NOT NULL,
    industry TEXT,
    size_band TEXT,
    brain_name TEXT DEFAULT 'Brain',
    persona_config JSONB DEFAULT '{}',
    data_retention_days INT DEFAULT 365, -- Free=365, Personal=1825, Together/Family=NULL (unlimited), Team=1825
    pii_policy JSONB DEFAULT '{}',
    ingestion_policy JSONB DEFAULT '{}',
    onboarding_status TEXT DEFAULT 'setup',
    features_enabled JSONB DEFAULT '{}',
    plan TEXT DEFAULT 'free',
    data_region TEXT DEFAULT 'us-west',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Teams (D19)
CREATE TABLE agent_teams (
    id SERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(organization_id, name)
);

CREATE TABLE agent_team_members (
    id SERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    team_id INT REFERENCES agent_teams(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_id, user_id)
);

-- Episodes (core memory)
CREATE TABLE agent_episodes (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,  -- no default: app layer MUST set explicitly (internal='paperwork-labs', consumer=user org ID)
    team_id INT REFERENCES agent_teams(id),
    circle_id INT,  -- D53/D55: nullable, set for shared circle episodes
    user_id TEXT,
    visibility TEXT DEFAULT 'organization',
    verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source TEXT NOT NULL,
    source_ref TEXT,
    channel TEXT,
    persona TEXT,
    persona_tier TEXT,
    product TEXT,
    summary TEXT NOT NULL,
    full_context TEXT,
    embedding VECTOR(1536),
    embedding_model TEXT DEFAULT 'text-embedding-3-small',
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', summary || ' ' || COALESCE(full_context, ''))
    ) STORED,
    importance FLOAT DEFAULT 0.5,
    freshness FLOAT DEFAULT 1.0,
    quality_signal SMALLINT,
    model_used TEXT,
    tokens_in INT,
    tokens_out INT,
    confidence FLOAT,
    visual_context_url TEXT, -- D63: optional screenshot/image reference for browser context episodes
    metadata JSONB DEFAULT '{}'
);

-- Entities (knowledge graph nodes)
CREATE TABLE agent_entities (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    team_id INT REFERENCES agent_teams(id),
    circle_id INT,  -- D53/D55: nullable, set for shared circle entities
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    canonical_name TEXT,
    description TEXT,
    status TEXT,
    priority TEXT,
    deadline DATE,
    freshness FLOAT DEFAULT 1.0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    mention_count INT DEFAULT 1,
    embedding VECTOR(1536),
    embedding_model TEXT DEFAULT 'text-embedding-3-small',
    metadata JSONB DEFAULT '{}',
    UNIQUE(organization_id, name)
);

-- Entity edges (knowledge graph relationships)
CREATE TABLE agent_entity_edges (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    circle_id INT,  -- D53/D55: nullable, set for shared circle edges
    source_entity_id BIGINT REFERENCES agent_entities(id) ON DELETE CASCADE,
    target_entity_id BIGINT REFERENCES agent_entities(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    relationship_type TEXT,  -- associative, causal, temporal, hierarchical (F64)
    direction TEXT,          -- bidirectional, source_to_target (F64)
    weight FLOAT DEFAULT 1.0,
    episode_id BIGINT REFERENCES agent_episodes(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, source_entity_id, target_entity_id, relationship)
);

-- User profiles
CREATE TABLE agent_user_profiles (
    id SERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    slack_user_id TEXT,
    display_name TEXT,
    role TEXT,
    domains TEXT[],
    gmail_accounts TEXT[],
    life_domains JSONB DEFAULT '{}',
    communication_prefs JSONB DEFAULT '{}',
    priority_signals JSONB DEFAULT '{}',
    decision_patterns JSONB DEFAULT '{}',
    corrections_log JSONB DEFAULT '[]',
    detected_patterns JSONB DEFAULT '{}',
    active_hours JSONB DEFAULT '{}',
    persona_overrides JSONB DEFAULT '{}',
    autonomy_config JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

-- Summaries (periodic consolidation)
CREATE TABLE agent_summaries (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    team_id INT REFERENCES agent_teams(id),
    period TEXT NOT NULL,
    period_start DATE NOT NULL,
    user_id TEXT,
    persona TEXT,
    product TEXT,
    summary TEXT NOT NULL,
    key_decisions TEXT[],
    key_entities TEXT[],
    open_threads TEXT[],
    contradictions_detected TEXT[],
    model_performance JSONB,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Costs
CREATE TABLE agent_costs (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    date DATE NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    chain_strategy TEXT,
    input_tokens BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    cost_usd NUMERIC(10,6) DEFAULT 0,
    workflow TEXT,
    persona TEXT,
    user_id TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Audit log (brain requests)
CREATE TABLE agent_audit_log (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,  -- no default: app layer MUST set explicitly
    created_at TIMESTAMPTZ DEFAULT NOW(),
    request_id UUID DEFAULT gen_random_uuid(),
    n8n_execution_id TEXT,
    user_id TEXT,
    persona TEXT,
    persona_tier TEXT,
    persona_mdc_sha TEXT,       -- prompt versioning (F110)
    model TEXT,
    chain_strategy TEXT,
    model_selection_reason TEXT,
    memories_recalled JSONB,
    tool_results_summary JSONB, -- truncated tool outputs (F103)
    trace JSONB,                -- full execution trace (F108)
    confidence FLOAT,
    emotional_state TEXT,
    iterations INT,
    tokens_in INT,
    tokens_out INT,
    cost_usd NUMERIC(10,6),
    latency_ms INT,
    source TEXT,
    channel TEXT,
    source_ref TEXT,
    experiment_id TEXT,
    experiment_variant TEXT,
    -- Three-layer eval (D34)
    plan_quality_score FLOAT,
    plan_adherence_rate FLOAT,
    tool_calls_correct INT,
    tool_calls_total INT,
    argument_hallucination_count INT,
    task_completed BOOLEAN,
    steps_taken INT,
    optimal_steps INT,
    step_efficiency FLOAT,
    guardrail_triggers INT,
    user_rating INT,
    -- Constitutional AI (D37)
    constitution_version TEXT,
    principle_violations JSONB
);

-- Admin audit log (D28/F47)
CREATE TABLE agent_admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details JSONB DEFAULT '{}',
    ip_address TEXT
);

-- API keys (multi-tenant auth)
CREATE TABLE agent_api_keys (
    id SERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT,
    rate_limit INT DEFAULT 100,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

-- Connections (D26) — instance_id for multi-workspace enterprise (F54, P9)
CREATE TABLE agent_connections (
    id SERIAL PRIMARY KEY,
    organization_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    instance_id TEXT DEFAULT 'default',
    status TEXT DEFAULT 'pending',
    oauth_token_encrypted TEXT,
    scopes TEXT[],
    channels_selected TEXT[],
    last_sync_at TIMESTAMPTZ,
    sync_frequency_minutes INT DEFAULT 60,
    episodes_ingested INT DEFAULT 0,
    health TEXT DEFAULT 'healthy',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, provider, instance_id)
);

-- P9 addition: conversation threading for product UI (CTO-6)
-- CREATE TABLE agent_conversations (
--     id BIGSERIAL PRIMARY KEY,
--     organization_id TEXT NOT NULL,
--     user_id TEXT NOT NULL,
--     title TEXT,
--     pinned BOOLEAN DEFAULT false,
--     created_at TIMESTAMPTZ DEFAULT NOW(),
--     updated_at TIMESTAMPTZ DEFAULT NOW(),
--     metadata JSONB DEFAULT '{}'
-- );

-- P5 addition: procedural memory (D40)
-- CREATE TABLE agent_procedures (
--     id BIGSERIAL PRIMARY KEY,
--     organization_id TEXT NOT NULL,
--     name TEXT NOT NULL,
--     trigger_pattern TEXT,
--     steps JSONB NOT NULL,
--     reliability_score FLOAT DEFAULT 0.5,
--     times_executed INT DEFAULT 0,
--     times_succeeded INT DEFAULT 0,
--     last_executed_at TIMESTAMPTZ,
--     source_episode_ids BIGINT[],
--     created_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- P9 addition: circles for couples/family/partner sharing (D53)
-- CREATE TABLE agent_circles (
--     id SERIAL PRIMARY KEY,
--     organization_id TEXT NOT NULL,
--     name TEXT NOT NULL,
--     circle_type TEXT DEFAULT 'household',  -- household, family, roommates, business
--     created_by TEXT NOT NULL,
--     auto_share_config JSONB DEFAULT '{}',  -- per-type defaults
--     created_at TIMESTAMPTZ DEFAULT NOW()
-- );
--
-- CREATE TABLE agent_circle_members (
--     id SERIAL PRIMARY KEY,
--     organization_id TEXT NOT NULL,
--     circle_id INT REFERENCES agent_circles(id) ON DELETE CASCADE,
--     user_id TEXT NOT NULL,
--     role TEXT DEFAULT 'member',  -- owner, member
--     sharing_config JSONB DEFAULT '{}',  -- per-connection sharing overrides
--     joined_at TIMESTAMPTZ DEFAULT NOW(),
--     UNIQUE(circle_id, user_id)
-- );

-- P9 addition: delegated access for controlled sharing with external parties (D57)
-- CREATE TABLE agent_delegated_access (
--     id SERIAL PRIMARY KEY,
--     owner_user_id TEXT NOT NULL,
--     owner_org_id TEXT NOT NULL,
--     delegate_email TEXT NOT NULL,
--     delegate_user_id TEXT,           -- populated when delegate creates account
--     purpose TEXT NOT NULL,           -- tax_preparation, financial_planning, legal_review
--     categories TEXT[] NOT NULL,      -- scoped: ["tax", "income", "deductions"]
--     never_share TEXT[] DEFAULT ARRAY['ssn', 'passwords', 'vault'],
--     access_level TEXT DEFAULT 'read_summary',  -- read_summary, read_detail
--     expires_at TIMESTAMPTZ NOT NULL,
--     revoked_at TIMESTAMPTZ,
--     revoked_reason TEXT,
--     access_count INT DEFAULT 0,
--     last_accessed_at TIMESTAMPTZ,
--     created_at TIMESTAMPTZ DEFAULT NOW(),
--     metadata JSONB DEFAULT '{}'
-- );
--
-- CREATE TABLE agent_access_audit_log (
--     id BIGSERIAL PRIMARY KEY,
--     delegated_access_id INT REFERENCES agent_delegated_access(id),
--     circle_id INT REFERENCES agent_circles(id),
--     accessed_by TEXT NOT NULL,
--     access_type TEXT NOT NULL,       -- view_episode, view_entity, query, export_attempt
--     resource_type TEXT,
--     resource_id TEXT,
--     ip_address TEXT,
--     device_fingerprint TEXT,
--     flagged BOOLEAN DEFAULT false,   -- suspicious access pattern detected
--     created_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- Per-User Encrypted Vault (D61) — secrets/API keys, NOT memory
CREATE TABLE brain_user_vault (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    name TEXT NOT NULL,
    encrypted_value TEXT NOT NULL,
    iv TEXT NOT NULL,
    auth_tag TEXT NOT NULL,
    service TEXT,
    description TEXT,
    expires_at TIMESTAMPTZ,
    last_rotated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, organization_id, name)
);

-- Skill Registry (D62) — skills the platform offers
CREATE TABLE brain_skills (
    id SERIAL PRIMARY KEY,
    skill_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    tier TEXT DEFAULT 'free',          -- free, personal, team, enterprise
    connector_id TEXT,                 -- links to D26 connector (nullable for built-in skills)
    tools JSONB DEFAULT '[]',          -- tool IDs this skill grants
    knowledge_domains JSONB DEFAULT '[]',
    requires_connection BOOLEAN DEFAULT false,
    owner_organization_id TEXT DEFAULT 'platform',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skill Enablement (D62) — which skills a user has "installed"
CREATE TABLE brain_user_skills (
    user_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    skill_id TEXT NOT NULL REFERENCES brain_skills(skill_id),
    enabled_at TIMESTAMPTZ DEFAULT NOW(),
    config JSONB DEFAULT '{}',
    PRIMARY KEY (user_id, organization_id, skill_id)
);

-- Indexes
CREATE INDEX ON brain_user_vault (user_id, organization_id);
CREATE INDEX ON brain_skills (tier, status);
CREATE INDEX ON brain_user_skills (organization_id);
CREATE INDEX ON agent_episodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON agent_entities USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON agent_summaries USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON agent_episodes USING gin(search_vector);
CREATE INDEX ON agent_episodes (organization_id, team_id, user_id, created_at DESC);
CREATE INDEX ON agent_episodes (organization_id, visibility, created_at DESC);
CREATE INDEX ON agent_episodes (organization_id, source, created_at DESC);
CREATE INDEX ON agent_episodes (importance) WHERE importance > 0.3;
CREATE INDEX ON agent_entities (organization_id, entity_type, status);
CREATE INDEX ON agent_entities (organization_id, team_id);
CREATE INDEX ON agent_entity_edges (organization_id);
CREATE INDEX ON agent_summaries (organization_id, period, period_start);
CREATE INDEX ON agent_costs (organization_id, date, provider);
CREATE INDEX ON agent_audit_log (organization_id, created_at DESC);
CREATE INDEX ON agent_audit_log (experiment_id) WHERE experiment_id IS NOT NULL;
CREATE INDEX ON agent_connections (organization_id, provider);
CREATE INDEX ON agent_admin_audit_log (organization_id, created_at DESC);
-- D53/D55: circle-scope indexes for shared episodes and entities
CREATE INDEX ON agent_episodes (circle_id, created_at DESC) WHERE circle_id IS NOT NULL;
CREATE INDEX ON agent_entities (circle_id) WHERE circle_id IS NOT NULL;
-- D57: delegated access audit trail
-- CREATE INDEX ON agent_access_audit_log (delegated_access_id, created_at DESC);
-- CREATE INDEX ON agent_access_audit_log (circle_id, created_at DESC) WHERE circle_id IS NOT NULL;
-- CREATE INDEX ON agent_delegated_access (owner_user_id, expires_at);

-- Seed
INSERT INTO agent_organizations (organization_id, parent_organization_id, name, industry, plan) VALUES
  ('platform', NULL, 'Platform Brain', 'platform', 'enterprise'),       -- D62: root of hierarchy
  ('paperwork-labs', 'platform', 'Paperwork Labs', 'technology', 'enterprise');
INSERT INTO agent_user_profiles (organization_id, user_id, display_name, role, domains, gmail_accounts) VALUES
  ('paperwork-labs', 'sankalp', 'Sankalp', 'founder_product_eng',
   ARRAY['engineering','product','infrastructure','tax','design'],
   ARRAY['sankalp@paperworklabs.com']),
  ('paperwork-labs', 'olga', 'Olga', 'founder_partnerships_revenue',
   ARRAY['partnerships','revenue','operations','legal'],
   ARRAY['olga@paperworklabs.com']);

-- D62: Initial skill registry
INSERT INTO brain_skills (skill_id, name, category, tier, requires_connection) VALUES
  ('tax-filing',             'Tax Filing',              'financial',  'free',     false),
  ('llc-formation',          'LLC Formation',           'financial',  'free',     false),
  ('financial-calculators',  'Financial Calculators',   'financial',  'free',     false),
  ('email-metadata',         'Email Intelligence',      'financial',  'free',     true),
  ('calendar-insights',      'Calendar Insights',       'lifestyle',  'free',     true),
  ('email-full',             'Deep Email Analysis',     'financial',  'personal', true),
  ('location-history',       'Location Intelligence',   'lifestyle',  'personal', true),
  ('bank-transactions',      'Bank Transactions',       'financial',  'personal', true),
  ('browser-context',        'Shopping and Browsing',   'shopping',   'personal', true),
  ('couple-brain',           'Shared Circle',           'lifestyle',  'personal', false);
```

---

## 3. Model Routing Matrix

| Task class | Primary | Fallback | Chain? |
|-----------|---------|----------|--------|
| Query classification | Gemini 2.5 Flash | GPT-4o-mini | No |
| Simple conversation | GPT-4o-mini | Gemini Flash | No |
| Standard conversation | Claude Sonnet | GPT-4o → Flash | No |
| Complex/strategic | Claude Opus | Sonnet → GPT-4o | No |
| Code generation | Claude Sonnet | GPT-4o | No |
| Live web data | Gemini Flash (grounded) → Sonnet | Brave + Sonnet | SearchAndSynthesize |
| Entity extraction | Gemini 2.5 Flash | GPT-4o-mini | No |
| Quality gate | Gemini 2.5 Flash | GPT-4o-mini | No |
| Long doc processing | Gemini Pro (1M ctx) → Sonnet | Sonnet alone | ExtractAndReason |
| Tier 2/3 actions | Sonnet → GPT-4o → Sonnet | Single-model | AdversarialReview |
| Critical decisions | Claude + GPT-4o + Gemini parallel | Single-model | Consensus |
| Thread summarization | GPT-4o-mini | Gemini Flash | No |
| Query reformulation | GPT-4o-mini | Gemini Flash | No |
| Correction detection | Keywords then GPT-4o-mini | Keywords only | No |
| Image/screenshot | Gemini Pro Vision | GPT-4o Vision | No |
| Voice transcription (P8) | Browser Web Speech API | Whisper API | No |
| Voice output TTS (P9) | OpenAI TTS-1 | Browser SpeechSynthesis | No |
| Content generation (D33) | GPT-4o-mini (volume) / Sonnet (quality) | Flash | No |
| Trend analysis (D33) | Gemini Flash + web search | GPT-4o-mini | No |

All model references use pinned versions via `model_registry.py` (F95). Pre-flight token counting truncates context if >80% of model limit (F96).

---

## 4. Scale-Ready Abstractions

```python
# Illustrative Protocol stubs (interfaces distributed across services today)
class VectorStore(Protocol):
    async def search(self, embedding: list[float], filters: dict, limit: int) -> list[SearchResult]: ...
    async def upsert(self, id: str, embedding: list[float], metadata: dict) -> None: ...

class MessageQueue(Protocol):
    async def enqueue(self, task_type: str, payload: dict) -> str: ...

class EmbeddingService(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...  # F107

class CacheService(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...

class ModelProvider(Protocol):
    supports_cache_control: bool       # F97
    supports_structured_output: bool   # F106
    async def complete(self, messages: list[dict], tools: list | None) -> ModelResponse: ...
```

Phase 1: PgVectorStore, InProcessQueue, OpenAIEmbeddings, UpstashCache. Scale: Pinecone, SQS/RedisQueue, BatchEmbeddings, RedisCluster. Brain API is stateless — horizontal scaling via N instances with zero code changes.

---

## 5. Safety Layer

Two auth paths (internal secret + external API key). PII scrubbing (regex P1, hybrid regex+Presidio NER from P2 — F113). Prompt injection regex + system prompt hardening. Emergency brake: `/brain/admin/freeze` (F24). Self-modification guardrails: compliance .mdc files IMMUTABLE.

**Defense-in-Depth (D36)**: Four-layer guardrail architecture, each logging independently:

```
User Input → [Input Filter] pattern scan + injection classifier
           → [Tool Call Guard] validate args, enforce tiers, block unauthorized
           → [LLM Processing]
           → [Output Filter] critique-revise loop + PII mask + fact verification → User
```

Each layer tracks `guardrail_triggers` count in audit_log. Trigger rate is a weekly KPI in Brain Health Report.

**Versioned Constitutional AI (D37)**: `apis/brain/constitution.yaml` (git-versioned):

```yaml
version: "1.0.0"
principles:
  - id: P001
    name: no_tax_advice
    rule: "Use education framing, not directives"
    severity: high
    examples: ["'many taxpayers...' not 'you should...'"]
  - id: P002
    name: ssn_never_in_output
    rule: "Never include full SSN in any output"
    severity: critical
  - id: P003
    name: no_guarantees
    rule: "Never guarantee specific refund amounts or outcomes"
    severity: high
  - id: P006
    name: circle_privacy
    rule: "Never expose Circle member personal data to another member. Never auto-share — all sharing requires explicit owner action."
    severity: critical
  - id: P007
    name: delegate_scope
    rule: "Never allow delegate access outside granted categories. SSN/passwords/vault structurally blocked."
    severity: critical
```

At inference: after LLM generates response, critique step evaluates against active constitution version. Violations trigger auto-revise with principle citation. All violations logged with `principle_id`. Phase: P1 (file + logging), P2 (critique-revise loop).

**Output monitoring (F102)**: Lightweight filter in response pipeline — regex for dangerous financial/legal/medical advice without citations. System prompt: "Never recommend specific financial products without citing a source. Frame as information not advice."

**Constitutional principles** (7 testable assertions monitored by Safety Lead):
1. Never prioritize one user's interests over another without transparency
2. Never claim certainty when evidence is thin — communicate confidence
3. Never take irreversible actions (Tier 3) without explicit approval
4. Never access data outside the user's authorized scope — enforce structurally
5. Always preserve the option to undo
6. **(P006 — Circle privacy, D53)**: Never expose one Circle member's personal data to another, even if explicitly requested. Never auto-share data — all sharing requires explicit owner action. The Brain detects, the owner decides.
7. **(P007 — Delegate scope, D57)**: Never allow a delegate to access categories outside their granted scope, even if the owner's query context would normally include them. SSN, passwords, and vault items are structurally impossible to share.

Wisdom behaviors (cached prefix): RESTRAINT, CONVICTION, HUMILITY (with confidence calibration — F100), CONNECTION, LEARNING, ANTICIPATION, SILENCE (acknowledge AND offer when uncertain — F53), CITATION, PROVENANCE.

---

## 6. Degradation Matrix

| Dependency | Failure | Brain behavior |
|-----------|---------|----------------|
| Neon (DB) | Down | "I can still chat but won't remember this until my database recovers." |
| Redis (Upstash) | Down | Skip idempotency, fatigue, persona cache. Functional but degraded. |
| Anthropic | 429/500 | Fallback chain. "Using a backup AI model — might be slightly less detailed." |
| GitHub | 403/timeout | Code tools unavailable. Other tools work. |
| Brave Search | Rate limit | Fall back to Gemini grounded search. |
| n8n (Hetzner) | Down | No Slack adapter. Brain API works via direct calls. Watchdog alerts. |

---

## 7. Token Budget

Per-request: ~9,200 tokens input (3K cached, 6.2K full), ~500-1,500 output. With Sonnet: ~$0.034/request. With ClassifyAndRoute: ~$0.018/request average. At 30 req/day: ~$0.55/day with chaining.

---

## 8. Studio Dashboard

Pages under `/admin/brain`: Overview (health, stats, recent), Conversations (thread explorer), Memory (episode browser, entity graph), Costs (charts), Audit (request log), Approvals (Tier 2/3 queue), Keys (API key management). Build: P5 (Overview, Costs, Audit, Memory), P6 (Conversations, graph), P8 (Approvals, Keys, PWA).

---

## 9. Brain Product UI

**Design philosophy (F79-F85)**: Chat-first. One input box. Everything else discovered through conversation. Mobile-first (375px primary). Dark mode default.

**First message (F80)**: "Hey! I'm [brain_name]. I learn your finances, your routines, your favorite spots — everything that makes your life yours. Want to connect your Google account so I can start learning?"

**Surfaces**: Chat (primary, always visible), Progressive sidebar (after 3+ conversations), Connections (in-chat first, dedicated page for power users), Settings (conversational first, dedicated for admin).

**Brain Moments (D32)**: Shareable insight cards when Brain provides surprising value. Covers all life domains — financial ("saved $847 on insurance"), lifestyle ("12 new restaurants this month — new record"), travel ("3 trips in Q1"), couple ("47 date nights this year"). Dark background, product-gradient, JetBrains Mono for dollar amounts. Aspect ratios: 9:16 (TikTok/Stories), 1:1 (X/feed), 4:5 (Instagram). One-tap share. Exclusively celebratory — never judgmental.

**Meta-product (F90)**: Brain surfaces products as capabilities: "Your taxes are due — want me to file with FileFree?" / "Your LLC annual report is due — LaunchFree can handle it." / "Your anniversary is next week — want me to find something special?"

---

## 10. Go-to-Market Strategy

### Phase 1 — Launch (PLG + Automated Social)

**Target**: Solopreneurs, freelancers, creators, side hustlers, couples managing shared lives (40M+ self-employed Americans, 2M+ couples moving in together annually). NOT "everyone." Specific personas who need personal life organization + tax filing + LLC formation + business expenses in one place.

**Entry point**: Free tax filing via FileFree. One Google OAuth = emails, calendar, Maps, orders. Brain learns 847 things about your life in 5 minutes — finances, routines, restaurants, subscriptions, travel patterns.

**GTM channel**: Automated social content at scale (D33). 7-agent content pipeline running on n8n + Postiz. Psychology-driven content aligned with life events — tax season, moving in together, starting a business, New Year financial planning, summer travel. See Section 13 for full specification.

**Viral mechanic**: Brain Moments (D32). Shareable insight cards across all life domains. Spotify Wrapped model — continuous, not annual. Monthly Brain Report with shareable lifestyle + financial stats.

**Targeted 10K strategy** (not spray-and-pray 100K): Focus on high-intent cohorts — tax season filers (3K), new LLC formers (2K), freelancers (2.5K), couples moving in together (1.5K), new grads (1K). Expected 15-25% conversion vs 2.5% from random users. Same revenue, 10x fewer free users to support (D59).

### Phase 1.5 — Lifestyle Expansion (Post Tax Season)

Pivot from seasonal tax content to year-round lifestyle engagement. Brain shifts from "file your taxes" to "know your life." Travel content for summer. Restaurant/dining content for date nights. Fitness content for New Year. The Brain stays relevant year-round because life doesn't stop after April 15.

### Phase 2 — Growth

Referral: invite partner to Circle, both get 1 month free Together tier. Content marketing compounding (Reddit posts rank in AI search). Google Workspace Marketplace for B2C reach. Slack App Directory for B2B. Together tier drives organic growth — the Circle invitation IS the acquisition mechanic.

### Phase 3 — Enterprise

Inbound from PLG usage. Case studies. SOC 2. Knowledge lifecycle as killer feature.

### Phase 4 — Meta-product (F90)

Brain surfaces Paperwork Labs products as capabilities. Revenue compounds: brain subscription + product-specific revenue + contextual intelligence monetization (D59).

---

## 11. Competitive Positioning

| Capability | Origin | Monarch | Copilot | Poe | Dust | Glean | **Brain** |
|-----------|--------|---------|---------|-----|------|-------|-----------|
| AI financial advisor | SEC-regulated | Basic AI | Basic AI | No | No | No | **Holistic** |
| Connected accounts | Plaid/MX | Plaid | Plaid | No | No | No | **Plaid** |
| Free tax filing | No | No | No | No | No | No | **FileFree** |
| LLC formation | No | No | No | No | No | No | **LaunchFree** |
| Business compliance | No | No | No | No | No | No | **Yes** |
| Email/calendar | No | No | No | No | Per-user | Search | **Google** |
| Persistent memory | No | No | No | No | Per-user | Search | **Hierarchical** |
| Learns from corrections | No | No | No | No | No | No | **Yes** |
| **Lifestyle intelligence** | No | No | No | No | No | No | **Dining, travel, fitness, routines, hobbies** |
| **Couple/household** | No | Basic shared | No | No | No | No | **Circle: auto-detect, shared memory, joint meter, "Our Year"** |
| Social/viral | None | None | None | No | No | No | **Brain Moments** |
| Solopreneur lifecycle | Finance only | Finance only | Finance only | No | No | No | **Full stack** |
| Price | ~$15/mo | $15/mo | $13/mo | $20/mo | $29/user | Enterprise | **Free + $29/yr Personal** |

**Positioning**: "Origin does finance. Yelp does restaurants. TripAdvisor does travel. Strava does workouts. Brain knows your finances, your restaurants, your trips, your routines — all of it, in one conversation, connected, with memory that spans years."

**The solopreneur wedge**: Nobody serves the self-employed persona holistically. Origin does personal finance. LegalZoom does LLCs. TurboTax does taxes. Brain does all of it in one conversation — PLUS it knows your lifestyle, your routines, your preferences. It's not a financial tool that bolted on lifestyle. It's a life intelligence system where financial services happen to be the highest-value domain.

**The trust gradient**: W-2 + SSN for free tax filing = deeper trust exchange than connecting a bank account. From there, each product "skill" deepens the relationship.

**Cross-product + lifestyle data moat (F125)**: FileFree (tax data) + LaunchFree (entity data) + Plaid (banking data) + Distill (compliance data) + lifestyle data (email + calendar + location) = a dataset no single competitor assembles. Origin has banking but not tax. Monarch has banking but not entities. LegalZoom has entities but not finances. Yelp has restaurants but not spending. TripAdvisor has travel but not your budget. We have all of it, connected in one knowledge graph.

**brain.ai cautionary tale (F164)**: brain.ai raised $51.5M (Emerson Collective, Scott Cook) to build a horizontal "generative interface." Result: no vertical depth, no data moat. Deutsche Telekom partnership replaced by ElevenLabs in 2026. App Store rating: 4.7 → 2.4. Lesson: vision without vertical depth fails even with $50M. The Brain avoids every mistake: vertical wedge (taxes), genuine switching cost (email + financial data + accumulated memory), own distribution (consumer-direct), infrastructure IS the product.

**The "See vs. Understand" moat (D52)**: Free tier uses metadata-only email processing — 847 things learned without reading a single email. No competitor offers this. The privacy claim ("We never read your emails") is both technically true and competitively unique.

**Couples/household moat (D53)**: No AI life intelligence handles couples natively. Origin: no couples. Monarch: basic shared accounts (manual). Peas/Smoov/Opto: manual splitting, no memory, no tax, no email. Brain: auto-detects shared accounts from email metadata, conversational sharing, joint Brain Meter, shared calendar, shared trip memory, shared dining preferences, plus tax + LLC. The Circle creates a "Third Brain" that knows things neither individual Brain knows alone — trips together, date night patterns, shared routines, combined finances. The invitation ("Join my Circle") is a built-in viral mechanic with functional motivation.

---

## 12. Hierarchical Persona Architecture (D31)

<!-- STALE 2026-04-24: The tier-0/1/2 `.mdc` tree below is a strategic design story; the **operational** source of truth for which personas exist, models, and ceilings is the `PersonaSpec` registry in `apis/brain/app/personas/specs/*.yaml` and the generated table in `docs/BRAIN_PERSONAS.md`. Reconcile names/tiers in a future edit. -->

### Tier 0: The Substrate

**Founder's Mind** (`founder-mind.mdc`) — always active, shapes every response. Knows: Sankalp (engineer, builds solo, prefers direct answers, reads on phone), Olga (partnerships, time-constrained, needs actionable outputs in 5-10 min), venture state, interaction context. Every persona inherits from this.

### Tier 1: Executive Council (3 orchestrators)

**Chief of Staff** (`cos.mdc`) — absorbs EA + Strategy + Workflows. Calm, organized. Default persona. Designed tension: pushes back on scope creep.

**Chief Technology Officer** (`cto.mdc`) — absorbs Engineering + QA + Agent Ops + Git Workflow. Opinionated, direct, allergic to over-engineering. Designed tension: pushes back on premature optimization AND sloppy shortcuts.

**Chief Revenue Officer** (`cro.mdc`) — absorbs Growth + Social + Brand + Partnerships. Provocative, story-driven. Designed tension: pushes for bolder claims vs Legal's caution. Owns automated social GTM (D33).

### Tier 2: Domain Specialists (5 experts)

**Tax Intelligence** (`tax-intelligence.mdc`) — Tax Domain + CPA. Meticulous, cites sources.
**Legal & Compliance** (`legal-compliance.mdc`) — evolves Legal. Cautious but practical.
**Financial Operations** (`financial-ops.mdc`) — evolves CFO. The skeptic who justifies every dollar.
**UX & Product Design** (`ux-design.mdc`) — evolves UX. Opinionated about simplicity.
**Product Intelligence** (`product-intelligence.mdc`) — NEW. Cross-product dot-connector. Owns meta-product vision.

### Tier 3: Technical Advisory Board (D30)

Agent Infra Lead, ML Systems Lead, Retrieval & Knowledge Lead, Product AI Lead, Safety & Alignment Lead.

### Collaboration Protocol

Question → Founder's Mind (context) → ClassifyAndRoute to Tier 1 → Tier 1 consults Tier 2 if needed → SYNTHESIZES into ONE answer. User gets a single coherent recommendation, not a committee report. "Show your work" (F86) reveals specialist inputs.

### Persona Memory

Episodes tagged with `persona` field. Each persona recalls its own history. The Legal persona remembers every compliance decision it's made for this org. The CTO remembers every architecture choice.

### Context-Mode Persona Adaptation (D55)

The Brain's personality shifts by active context — not just pronouns, but emotional register:

| Context | Pronouns | Tone | Example |
|---------|----------|------|---------|
| Personal | "your", "you" | Warm, encouraging, celebratory | "Your refund estimate: $2,100!" |
| Circle | "we", "us", "our" | Inclusive, partnership-validating | "Our shared spending this month: $3,200" |
| Org | "the team", company name | Professional, direct, efficient | "[Paperwork Labs] Deploy succeeded. 3 services updated." |
| Delegate view | "Sankalp's", owner attribution | Neutral, factual, read-only | "Sankalp's tax deductions: 12 items, $14,200 total" |

Implementation: `context_mode` field injected into system prompt prefix alongside persona. The cached prefix (D3) includes context-appropriate voice rules. Switching context mid-conversation triggers a prefix swap.

---

## 13. Automated Social Content Engine (D33)

### 7-Agent Content Pipeline

Runs on n8n (Hetzner) + Postiz (32+ platforms). Orchestrated by CRO persona.

1. **Trend Scout** (Gemini Flash) — monitors Reddit, TikTok, X, YouTube, Google Trends. Daily scan 6am PT.
2. **Audience Psychologist** (GPT-4o-mini) — maps opportunities to 5 psychological triggers (below).
3. **Content Strategist** (GPT-4o-mini) — format per platform. Genuinely different content per channel.
4. **Writer** (Sonnet/GPT-4o-mini) — platform-native content. FileFree = casual Gen Z. Brain = intelligent warmth.
5. **Compliance Reviewer** (Legal persona, GPT-4o) — reviews ALL financial content. Non-negotiable.
6. **Visual Designer** (template system) — Brain Moments cards, thumbnails, infographics.
7. **Publisher** (n8n → Postiz API) — schedules, tracks, feeds analytics back to Trend Scout.

### 6 Psychological Triggers

**1. Loss Aversion** (losses feel 2.5x worse than gains): "You're LOSING $X" > "You could save $X." Content: "The $800 California franchise tax nobody warns new LLC owners about." Share driver: digital altruism.

**2. Social Currency** (insider knowledge): "The trick your CPA charges $300 to tell you." Content: "The home office deduction hack most freelancers miss." Share driver: sharer looks smart.

**3. Identity Signaling** (tribe membership): "Things smart solopreneurs do before tax season." Content: "If you're self-employed and not doing this, you're leaving money on the table." Share driver: tribe alignment.

**4. Urgency/Scarcity** (deadline anxiety, 240% more shares): "Quarterly taxes due in 3 days." Aligned with tax calendar: Jan 15, Apr 15, Jun 15, Sep 15, plus state LLC annual report dates.

**5. Achievement/Celebration** (Spotify Wrapped effect): "Brain saved me $4,870 this year." Brain Moments share cards. CRITICAL: exclusively celebratory. Never judgmental. "You saved $X" never "You spent $X."

**6. Lifestyle Discovery** (curiosity + self-knowledge): "My Brain says I'm a foodie — 47 restaurants this year." / "3 trips in Q1 — someone's got wanderlust." / "You run more on weeks you sleep 7+ hours." Share driver: self-discovery is inherently shareable, identity-affirming. This trigger keeps engagement year-round (not just tax season). Content: "Things my Brain knows about me that I didn't realize."

### Platform Playbooks

**TikTok** (primary B2C): 15-30s hooks, 60-90s tutorials. Completion rate >80%. 5-7x/week. @dukelovestaxes (3.5M followers) proves the tax TikTok niche is massive. We educate AND solve.

**Reddit** (trust + SEO): r/personalfinance (18M), r/tax, r/smallbusiness. 10:1 help-to-promotion ratio. Reddit comments now surface in ChatGPT/Perplexity/Google AI Overviews. Users 34% more likely to trust peer recommendations. ~10 hrs/week.

**YouTube** (authority, $15-50 RPM): "How to [X] as a freelancer" tutorials. Long-tail keywords. Finance is the highest-paying niche. 1-2x/week, peak 2-3x during tax season.

**X/Twitter** (distribution): Brain Moments share cards + threads. Build in public. 2-3x/day.

**LinkedIn** (B2B for Distill): Professional insights with data. CPAs, accountants, fintech developers. 3x/week.

### Content Calendar

| Month | Event | Theme | Primary Trigger |
|-------|-------|-------|-----------------|
| Jan | Q4 estimated taxes due, tax season begins, New Year goals | Tax season prep + "Your Brain's 2025 Life Report" | Urgency + Achievement |
| Feb | 1099 forms arrive, Valentine's Day | "Found money" + couples Brain content | Social Currency + Lifestyle Discovery |
| Mar | Filing peak, LLC annual reports | LLC compliance alerts | Urgency + Identity |
| Apr | Tax deadline (Apr 15) | "It's not too late" + Brain Wrapped | Urgency (peak) + Achievement |
| May | Post-tax, LLC formation season | "Start your business" + summer travel planning | Achievement + Identity |
| Jun | Q2 estimated taxes, summer trips | Quarterly tax + "Brain knows your travel style" | Urgency + Lifestyle Discovery |
| Jul | Mid-year check-in, peak travel | Brain Moments H1 lifestyle report — trips, restaurants, fitness | Achievement + Lifestyle Discovery |
| Aug | LLC formation spike, back-to-school | State-by-state guides + Family Brain content | Identity + Lifestyle Discovery |
| Sep | Q3 estimated taxes, fall routines | Year-end planning + "Your Brain knows your routine" | Urgency + Lifestyle Discovery |
| Oct | Open enrollment, tax planning | ACA + optimization + "Brain saves you on insurance" | Loss Aversion |
| Nov | Black Friday, holiday planning | Subscription tracking + gift/travel Brain insights | Loss Aversion + Lifestyle Discovery |
| Dec | Year-end planning, holiday season | Brain Wrapped annual life report (not just financial) | Achievement (peak) + Lifestyle Discovery |

### Habit Loop Design

Cue: Monday notification ("Your weekly Brain brief is ready"). Action: check insights, review deadlines. Reward: peace of mind or surprising save. Variable reward: anticipation that this week MIGHT have a dramatic insight keeps users checking (dopamine peaks during anticipation, not consumption). Apps using personalized habit loops retain 2.3x longer.

---

## 14. Connection Roadmap (D39)

Four-tier integration strategy. Schema supports all from P1 (D26 Connections Architecture).

### Tier 1 — Core (P9 Launch)

- **Plaid Link**: Bank accounts, credit cards, investments. Single integration = 12,000+ institutions.
- **Google Workspace**: Gmail (metadata free, body paid — D52), Calendar, Drive, Contacts.
- **Google Maps Location History**: Restaurant visits (cuisine type, frequency, neighborhood), gym visits, store visits, commute patterns, travel destinations. Location + email + calendar = lifestyle fingerprint. This is the single most powerful lifestyle signal source — user doesn't need to tell Brain they're a foodie, Brain knows from 47 restaurant visits (D58).
- **Tax Documents**: W-2, 1099 via existing OCR pipeline (Cloud Vision + GPT).
- **Slack**: Team communication (existing adapter).
- **Manual Entry**: Assets/liabilities not in aggregators.

### Tier 2 — Enhanced (P9+3mo)

- **Plaid Financial Insights**: Enriched transaction categorization.
- **Plaid Investments**: Holdings, cost basis, gains/losses.
- **Google Maps Saved Places**: Favorites, want-to-go lists, labeled locations.
- **Apple**: Calendar, Contacts, Reminders (CalDAV/CardDAV).
- **Microsoft 365**: Outlook, Calendar, OneDrive (Graph API). Email (D50 pipeline).
- **Spotify / Apple Music** (P10): Listening history, playlists, genres — entertainment archetype.
- **Strava / Apple Health** (P10): Workout history, fitness patterns, sleep data.
- **Notion**: Knowledge base sync.
- **Linear**: Project management.
- **GitHub**: Repo activity, issues (expand existing).

### Tier 3 — Advisory (P10)

- **Zillow API**: Home value tracking.
- **Credit Bureau**: Credit score (Experian/TransUnion API).
- **Plaid Income**: Verify income, predict paychecks.
- **Insurance**: Policy data via Canopy Connect.
- **Student Loans**: Plaid Liabilities.
- **Crypto**: Coinbase API.
- **Vehicle Value**: Kelley Blue Book API.

### Tier 4 — Full Advisor (P10+)

- Estate planning (beneficiary tracking).
- Business Entities (SOS filings — LaunchFree data, already ours).
- HSA/FSA health savings.
- 529 Plans education savings.
- Social Security (SSA API benefit estimates).
- Mortgage rate comparison.

**Meta-aggregator**: Quiltt wraps Plaid + MX + Finicity in a single API. Evaluate at P9 for best per-institution coverage.

**Cross-product + lifestyle knowledge graph moat (F125)**: Tax data (FileFree) + banking data (Plaid) + business entity data (LaunchFree) + compliance data (Distill) + lifestyle data (email metadata + calendar + Google Maps location history) = unique dataset no competitor assembles. Origin has banking but not tax. Monarch has banking but not entities. Yelp has restaurants but not your spending. TripAdvisor has travel but not your budget. We have all of it — financial + lifestyle — connected in one knowledge graph.

---

## 15. UX/Design Architecture (D42-D44)

### Generative UI (D42)

LLM outputs structured JSON blocks alongside text. Frontend maps block types to interactive React components inline in the chat stream.

**Component registry:**

| Component | Trigger | Behavior |
|-----------|---------|----------|
| RefundCard | Refund calculated | Animated count-up $0 → final, gradient bg, confetti |
| StatusSelector | Filing status needed | Full-width cards (not radio buttons), 44px min touch |
| DocumentUpload | Doc needed | Camera trigger + scan animation, drag-drop desktop |
| BreakdownChart | Financial breakdown | 120px compact, tap for full-screen interactive |
| AssumptionCard | Pre-filled fields | Green checkmarks, "Edit" per field, 80% single-tap |
| ActionChips | After any response | Suggested next actions as tappable pills |
| ProcessStepper | Background task | "Scanning → Extracting → Calculating" + checkmarks |
| PaymentPlanCard | Payment due | Interactive monthly amount calculator |
| RestaurantCard | Dining recommendation/history | Cuisine tag, distance, visit count badge, "Book" action chip, map pin |
| TripCard | Travel memory/planning | Destination, dates, weather widget, Circle shared indicator, photo prompt |
| RoutineCard | Detected pattern | "You [do X] every [day/time]" with edit/confirm actions, streak counter |
| LifestyleInsightCard | Archetype/pattern insight | Archetype badge (foodie/traveler/etc), evidence list, share button |

Implementation: Vercel AI SDK `useChat` with function calling. LLM returns `{ type: "refund_card", data: { amount: 2100 } }`. Frontend `ComponentRouter` maps type → React component. All share Zustand state layer.

### Trust Escalation Ladder (D43)

Five rungs, each earned by the previous:

1. **Zero-risk**: Snap W-2, see estimate. No account, no PII. Value in <60 seconds.
2. **Competence**: Show extracted fields with confidence scores. Green checkmarks build trust.
3. **Data trust**: SSN entry ONLY after user reviews/confirms extracted data. Lock icon. "Never shared with AI."
4. **Financial trust**: Bank connection ONLY after reviewing completed return.
5. **Submission trust**: Swipe-to-confirm (not button tap). Ceremonial gesture for irreversible action.

Anti-pattern: SSN on screen 2 before demonstrating value. TurboTax does this. We never will.

### Anxiety-Reducing Financial UX (D44)

| Pattern | Example | Research |
|---------|---------|----------|
| Contextual reframing | "Gap of $3K because [reason]. Here's what to do." | Explain → normalize → empower |
| Positive-first | "Effective rate 18.4% — lower than your bracket avg" | +25% engagement |
| Calm metric density | 3-5 numbers per screen, rest behind "View Breakdown" | Cutting metrics 50% reduces stress |
| Progressive disclosure | Summary → Category → Line Items → Source Docs | Framer Motion layoutId transitions |
| Chunked bubbles | Long responses → sequential 50-100ms bubbles | One semantic unit per bubble |
| Personality modes | Encouraging / Direct / Detailed | Cleo: 20x engagement vs banking apps |

### Micro-Interactions

- **Swipe-to-confirm** (F135): High-stakes actions (filing, payment). Prevents accidental taps.
- **Document scan cascade**: Camera → scan line → field extraction animations → checkmarks.
- **Confidence glow**: Color transitions (red → yellow → green) on extracted fields.
- **Refund count-up**: $0 → final amount with JetBrains Mono, gradient bg, confetti at completion.
- **Brain orb**: Pulsing gradient indicator during AI processing. Product-themed color.
- **Memory greeting**: "Welcome back! Last time you uploaded your W-2 from [Employer]. 4 minutes to filing."

---

## 16. Growth Engine (D45-D47)

### Tax Season Wrapped (D45)

Spotify Wrapped for tax filing. 6-card shareable story (1080x1920, Instagram Stories format):

1. "You filed in X minutes" — speed flex (vs 3 hours on TurboTax)
2. "You saved $89" — money saved by filing free
3. "Your refund: $X,XXX" — opt-in, positive only
4. "Top X% of fast filers" — optimal distinctiveness trigger
5. "Tax personality: [archetype]" — Barnum Effect ("The Maximizer", "The Early Bird")
6. "Biggest win: [deduction/credit]" — celebrate smart moves

Design: product gradient backgrounds, JetBrains Mono for numbers, one-tap share (Web Share API), QR code embedded. Zero PII on shared cards. Launch April 15-18. LaunchFree version: "LLC Launch Wrapped."

### Double-Sided Referral Engine (D46)

| Mechanic | FileFree | LaunchFree |
|----------|----------|------------|
| Referrer reward | $5 credit toward Tax Optimization Plan | Free RA credit (1 year) |
| Friend reward | Priority processing + free state return | Priority filing + compliance setup |
| Activation | Completed + submitted return | Completed LLC submission |
| Variable bonus | $1-$25 scratch-off credit | — |

**Pre-launch waitlist** (Robinhood model): Exact position visible (#4,291 of 12,847). Jump 1K spots per referral. Target: 50-100K signups before launch. Anti-fraud: device fingerprinting, KYC on redemption, 50 referrals/user/year cap. Cross-product loops: FileFree → "Form LLC free" → LaunchFree → "File biz taxes free" → FileFree.

### Community Growth Flywheel (D47)

**Reddit** (highest ROI): 90/10 help-to-promotion. Founder accounts warmed 3 weeks. r/personalfinance (17M), r/tax (300K), r/smallbusiness (1.2M). Reddit threads surface in ChatGPT/Google AI Overviews.

**TikTok** (cheapest Gen Z reach): 2-3x/day tax season. Hook-first 0.5s. Spark Ads $20-50/day bursts (kill at CPC >$0.50). Film as founder, phone-recorded. Trending sounds +50% reach.

**Programmatic SEO** (compounding): 200+ pages from packages/data/ JSON configs via tools.filefree.ai. State tax calculators, LLC cost guides, deduction guides. FAQ schema markup. NerdWallet: $63M/mo traffic value from this pattern.

**Discord** (community hub): #tax-questions, #refund-tracking, #feedback, #show-your-refund. 2-7% free → paid conversion. UGC submissions for content pipeline.

**UGC flywheel**: Post-filing "I filed in X min" social cards. User tip submissions → featured content. r/FileFree subreddit.

---

## 17. Brain Fill Meter (D51)

### The Psychology Stack

Eight named effects that make the meter compulsive:

| # | Effect | Study | Application |
|---|--------|-------|-------------|
| 1 | Endowed Progress | Nunes & Dreze 2006 (34% vs 19%) | Start at 15-20%, never zero |
| 2 | Goal Gradient | Hull 1934 | "3 facts from 500" converts 2-3x |
| 3 | Zeigarnik | 1927 (90% better recall) | Meter is never "done" |
| 4 | Loss Aversion | Kahneman & Tversky 1979 (2x pain) | Paywall feels like LOSING access |
| 5 | Psychological Ownership | Endowment effect | Data feels "theirs" before paying |
| 6 | Variable Ratio Reinforcement | Skinner | Unpredictable insight quality = dopamine |
| 7 | Optimal Distinctiveness | Brewer 1991 | "Top 22% of tax-optimized Americans" |
| 8 | Sunk Cost / Switching Cost | — | Every day the counter grows. Day 365: irreplaceable. |

### Gamification Levels

| Level | Things Learned | Unlock | Share Card |
|-------|----------------|--------|------------|
| Awakening | 100 | Basic personality profile | "My Brain just woke up" |
| Awareness | 250 | Communication style analysis | "My Brain is learning fast" |
| Understanding | 500 | Relationship map | "My Brain knows 500 things" |
| Insight | 1,000 | Financial behavior patterns | "Knows me better than my accountant" |
| Mastery | 2,500 | Predictive capabilities | "My Brain predicts things now" |
| Omniscience | 5,000 | "Knows you better than you" | "My Brain is scary good" |

### Notification Escalation (Duolingo-Adapted)

| Day | Notification | Trigger |
|-----|-------------|---------|
| 0 (23.5hr) | "Your Brain found something interesting. Tap to see." | Curiosity |
| 2 | "Your Brain learned 12 new things while you were away." | FOMO |
| 3 | "Your Brain is 67% full. It's slowing down without you." | Loss aversion |
| 5 | "Your Brain hasn't grown in 5 days. @sarah's passed yours." | Social pressure |
| 7+ | Trigger friend re-activation ("Send @sarah a nudge") | Social reactivation |

Rule: Insight-led, never feature-led. Bad: "Open FileFree." Good: "Your Brain just realized you might qualify for the Earned Income Credit — that's up to $7,430."

### Shareable Card Formats

**Format 1 — Identity Card**: Fill meter bar (81%), fact count (1,247), highlighted insight ("3 tax credits worth $4,200"), CTA link.

**Format 2 — Surprise Card**: "Things my Brain knows that I didn't: I've been overpaying insurance for 14 months."

**Format 3 — Archetype Card**: "My Brain says I'm The Optimizer. It found 7 deductions I was missing." Most shareable — identity signaling, not data sharing.

All cards: 1080x1920 for Stories, product gradient, JetBrains Mono for numbers, zero PII, QR code.

### TikTok Content Formats

1. **"Watch My Brain Fill Up"** — satisfying progress bar animation as it scans emails (ASMR-adjacent)
2. **"Things My Brain Knows About Me"** — creator reads insights, reacts (finance + lifestyle mix)
3. **"Brain vs. Brain"** — couples/friends compare meters (drives duets/stitches)
4. **"My Brain Predicted My Refund"** — prediction vs actual IRS refund (proof of value)
5. **"POV: Day 1 vs Day 30"** — time-lapse of Brain growing (transformation content)
6. **"The Brain Character"** — Duolingo-style mascot energy, slightly unhinged personality
7. **Demographic hooks** — "POV: you're a freelancer and your Brain finds $4K in deductions"
8. **"My Brain Knows My Taste"** — Brain reveals lifestyle archetypes: "Apparently I'm a foodie. 47 restaurants this year." / "My Brain says I go to Thai restaurants more than my apartment." Self-discovery content, extremely shareable.
9. **"Date Night by Brain"** — couples ask Brain where to go for dinner, plan anniversary, recall trips. Reaction content. "Our Brain remembers our first restaurant better than we do."

### Joint Circle Meter (D53)

When two users share a Circle, the fill meter becomes three bars:

| Meter | Source | Psychology |
|-------|--------|-----------|
| Your Brain | Your personal data only | Individual progress |
| Partner's Brain | Their count (no detail) | Competitive motivation |
| Our Brain | Union of shared items | Always highest — motivates the person who's behind |

"Together you know 1,847 things." The combined number is always larger than either individual's, reinforcing that the Circle adds value. The partner who's behind sees the gap and is motivated to connect more sources. Shareable card: "Our Brain knows 1,847 things about our life together."

**Circle milestone notifications**: "Your shared Brain just hit 500 things learned! Here are 3 insights about your household." Sent to both members simultaneously.

### Monthly Brain Report Card

```
YOUR BRAIN — MARCH 2026
Facts learned this month: 89
Brain fill: 73% → 81%

FINANCES
Biggest insight: $847/mo in subscriptions (3 unused)
Tax impact: HSA could save you $1,200

LIFESTYLE
Dining: 12 restaurants this month. Top cuisine: Thai (4x). New favorite: Siam Garden.
Travel: Portland trip (Mar 8-11). Average trip spend: $1,847.
Fitness: Gym 14x this month. You run more on weeks you sleep 7+ hours.
Entertainment: 3 movies, 2 concerts. You're in a documentary phase.
Routines: Farmers market 4 Saturdays straight. Coffee at Blue Bottle every Monday.

Top 22% of Brain users in California

OUR BRAIN — MARCH 2026 (Household)
Shared facts this month: 34
Household fill: 61% → 68%
Date nights: 5 this month. Favorite: that new Italian place on 3rd.
Shared subscriptions: $287/mo across 12 services
Trips planned: Austin in April (flights booked, no hotel yet)
Routines: Farmers market together 4/4 Saturdays
Biggest joint insight: You both overpay for car insurance ($720/yr savings available)
```

Rolling cadence, not annual. Spotify Wrapped got 500M shares in 24 hours (2025). Rolling captures demand year-round.

### Cost Model (D52 Numbers)

| Metric | Free Tier | Paid Tier |
|--------|-----------|-----------|
| Onboarding (10K emails) | $0.05 (metadata only) | $0.25-0.50 (5 optimization layers) |
| Monthly ongoing | $0.03 | $0.39 |
| Pro price | — | $2.42/mo ($29/yr) |
| Break-even conversion | — | ~1.5% |
| 100K free users monthly | $3,000 | — |
| Margin at 5% conversion | — | 96% |
| Margin at 10% conversion | — | 98% |

Frontloading: 5 queries in week 1 (hook fast), 5 across weeks 2-4 (create scarcity). Target: 60-70% of engaged users hit the wall.

---

## 18. Email Ingestion Pipeline (D50, D52)

### Three-Provider Architecture

```
User connects email
        |
        +-- Gmail? ----------> Gmail API (OAuth2 + Pub/Sub + history.list)
        +-- Outlook/365? ----> Microsoft Graph (OAuth2 + webhooks + delta query)
        +-- Other? ----------> IMAP adapter (app password + polling)
                                +-- Yahoo, iCloud, AOL, Zoho, custom domains
```

Gmail: `gmail.metadata` (free), `gmail.readonly` (paid). 2-step fetch, 15K quota/min, 10K emails ~3.3 min. Microsoft: delta query returns full messages inline (better). IMAP: ~5% of users, polling-based.

### Tiered Processing: "See vs. Understand" (D52)

**Free Tier — "See" (`gmail.metadata` scope, zero LLM):**

| Analysis | Method | LLM Cost |
|----------|--------|----------|
| Vendor/service classification | Sender-domain lookup (500+ known domains) | $0 |
| Transaction detection | Subject-line regex (`\$[\d,]+`) | $0 |
| Subscription detection | Recurring sender frequency + List-Unsubscribe header | $0 |
| Behavioral patterns | Timestamp clustering (night owl, work hours) | $0 |
| Social graph | From/To/CC personal email matching | $0 |
| Life events | New corporate domain = job change, new utility = move | $0 |
| Financial accounts | Known bank/fintech sender domains | $0 |

Result: **600-800 "things learned" in 30 seconds. Brain Fill Meter: 60-75%. Cost: ~$0.05.**

**Paid Tier — "Understand" (`gmail.readonly` scope):**

Everything above PLUS five optimization layers:

1. **Metadata-first classification**: Skip 40% newsletters/social/spam. $0 LLM.
2. **Sender-domain templates**: Top 100 senders via regex (Chase, Amazon, Uber). $0 LLM.
3. **Representative sampling**: Cluster by sender, extract 3-5 per cluster. 90% LLM reduction.
4. **Model routing**: Gemini Flash for extraction (33% cheaper than GPT-4o-mini).
5. **Batch API**: Off-peak processing (50% discount from OpenAI).
6. **Cross-user template amortization**: User #1's Chase template serves Users #2-10K.

Result: **1,200+ "things learned" with deep understanding. Brain Fill Meter: 95%+. Cost: $0.25-0.50.**

### Cross-User Template Amortization (F183)

| Users Onboarded | Template Hit Rate | Avg Paid User Cost |
|-----------------|-------------------|--------------------|
| 10 | ~10% | $0.45 |
| 100 | ~40% | $0.30 |
| 1,000 | ~60% | $0.20 |
| 10,000 | ~70% | $0.15 |

Cost per user DECREASES with growth. Traditional SaaS: flat. Brain: drops. Infrastructure-as-moat.

### Email Schema

Core tables: `parsed_emails` (metadata + classification + extraction status), `email_transactions` (vendor, amount_cents, date, tax_relevant), `email_line_items` (itemized receipts), `detected_subscriptions` (service, amount, billing_period, annual_cost), `vendors` (entity resolution: AMZN = Amazon.com = Amazon Marketplace), `email_processing_queue` (batch tracking + cost monitoring). Key: `dedup_key` generated column, `raw_extraction` JSONB for re-parsing without re-calling LLM.

### Google Verification (Critical Path)

`gmail.readonly` is restricted → full OAuth verification + CASA Tier 2 assessment. Cost: $540-1,500/yr. Timeline: 6-12 weeks. START IN P7. Requirements: privacy policy, app demo video, data handling docs. `gmail.metadata` requires separate verification — easier approval, faster track.

### Privacy Advantage

Free tier: "We never read your emails." Honest claim. TikTok hook: "My AI knows 847 things about me and it never read a single email." This INVERTS the trust model: competitors ask for everything upfront. Brain earns trust first. Body reading becomes the upsell: "Let your Brain read deeper."

---

## 19. All Findings Index (F1-F210)

### Rounds 1-3 (F1-F48)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F1 | Missing org_id on entities/edges/summaries | Crit | P1 |
| F2 | Wrong UNIQUE on user_profiles | Crit | P1 |
| F3 | Redis failure = brain failure | Crit | P1 |
| F4 | No per-tool timeout | Crit | P1 |
| F5 | Thread summarization timing | High | P1 |
| F6 | Correction detection undefined | High | P2 |
| F7 | Neon cold start | High | P0 |
| F8 | Bootstrap noise | High | P2 |
| F9 | PII patterns narrow | Med | P2 |
| F10 | No storage quotas | Med | P5 |
| F11 | GitHub PAT scopes | Med | P1 |
| F12 | Embedding migration strategy | Med | P2 |
| F13 | Structured logging (structlog) | Med | P1 |
| F14 | Request tracing (n8n_execution_id) | Med | P1 |
| F15 | Health check depth | Med | P1 |
| F16 | Concurrent tool execution | Med | P3 |
| F17 | 512MB memory budget | Low | P1 |
| F18 | Brave Search limits | Low | P1 |
| F19 | deploy-n8n root cause | Low | P0 |
| F20 | Token budget docs | Low | P1 |
| F21 | Degradation matrix docs | Low | P1 |
| F22 | Backup strategy | Low | P2 |
| F23 | Correction feedback loop risk | Med | P2 |
| F24 | Emergency brake | High | P1 |
| F25 | Memory budget (OOM at concurrency) | Med | P3 |
| F26 | Concurrency limit (per-org semaphore) | High | P1 |
| F27 | Connection pooling | Med | P1 |
| F28 | Quality gate too coarse | Med | P2 |
| F29 | Eval framework | Med | P5 |
| F30 | Gemini underutilized | Med | P2 |
| F31 | Gemini search grounding | Med | P3 |
| F32 | Scale abstraction layer | Med | P1 |
| F33 | Brain product UI | Med | P9 |
| F34 | A/B testing framework | Med | P5 |
| F35 | Rate limiting (slowapi) | Med | P1 |
| F36 | Memory ops as explicit tools | Med | P2 |
| F37 | @-mention persona forcing | Low | P1 |
| F38 | Stricter onboarding quality gate | Med | P2 |
| F39 | External email bodies never stored | Med | P7 |
| F40 | Brain communicates knowledge state | Med | P9 |
| F41 | Sub-processor documentation | Low | P9 |
| F42 | SOC 2 timeline | Low | P10 |
| F43 | Data residency via Neon regions | Low | P10 |
| F44 | Connection health monitoring | Med | P9 |
| F45 | Connector SDK | Low | P10 |
| F46 | Nightly retention enforcement | Med | P9 |
| F47 | Admin audit log | Med | P1 |
| F48 | Free tier must be genuinely useful | Med | P9 |

### Round 4: Board Review (F49-F71)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F49 | NER-based PII detection (Presidio) | High | P9 |
| F50 | OAuth token encryption key management (HKDF) | Crit | P9 |
| F51 | Remember tool consent model (ToS) | Med | P9 |
| F52 | Correction conflict escalation (enterprise) | Med | P9 |
| F53 | SILENCE behavior: acknowledge AND offer | Low | P1 |
| F54 | agent_connections UNIQUE blocks multi-workspace | Crit | P9 |
| F55 | SSE streaming endpoint | Crit | P1/P9 |
| F56 | ClassifyAndRoute cost savings unvalidated | Med | P3 |
| F57 | Semantic cache for repeated queries | Med | P5/P9 |
| F58 | Sync worker must be separate process | Med | P9 |
| F59 | Render Starter OOM at P1 | High | P1 |
| F60 | Hierarchical recall perf (Redis cache) | Med | P2 |
| F61 | Entity graph not traversed during recall | High | P2-P3 |
| F62 | No deduplication at ingestion | Med | P2 |
| F63 | Memory fatigue backfires on follow-ups | Med | P2 |
| F64 | No causal edges in knowledge graph | Med | P2/P5 |
| F65 | Weekly Brain Health Report from P1 | High | P1 |
| F66 | Intelligence Index | Med | P2 |
| F67 | Chain selector doesn't learn | Med | P5 |
| F68 | Render Standard from P1 ($25/mo) | High | P1 |
| F69 | No webhook architecture for product Slack | Crit | P9 |
| F70 | Free tier 50→100 msg/mo | Med | P9 |
| F71 | Go/no-go gate at P8→P9 | High | P8 |

### Round 5: AI Lead + Jony Ive/Steve Jobs UX (F72-F90)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F72 | No latency budget (p50 <2s, p95 <5s, abort >8s) | Crit | P1 |
| F73 | No output fact-checking against knowledge graph | High | P2-P3 |
| F74 | No source attribution in responses | High | P1 |
| F75 | No notification architecture | High | P6/P9 |
| F76 | No async response pattern (>15s → background) | Med | P1 |
| F77 | Slack streaming gap (chunked posting) | Med | P1 |
| F78 | Intelligence demonstration moments undefined | Med | P6/P9 |
| F79 | Four pages is three too many — chat-first | High | P9 |
| F80 | No first message design | Crit | P9 |
| F81 | No emotional design language | High | P9 |
| F82 | Information density nightmare on Everything page | Med | P9 |
| F83 | No progressive disclosure | Med | P9 |
| F84 | Pricing in technical units not outcomes | Low | P9 |
| F85 | No mobile-first mandate | High | P9 |
| F86 | No "show your work" transparency | Med | P2/P9 |
| F87 | No conversation threads/history | High | P9 |
| F88 | No search in product UI | Med | P1/P9 |
| F89 | Google Account as primary B2C connection | High | P9 |
| F90 | Brain as meta-product / venture layer | Strategic | All |

### Round 6: CTO + Top 5 AI Leads (F91-F112)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F91 | Tool retry policy (backoff, retryable errors) | High | P1 |
| F92 | ask_user escape hatch (max 1/request) | Med | P1 |
| F93 | Golden test set from P1 (10 queries + smoke script) | High | P1 |
| F94 | Embedding dimensionality (keep 1536, benchmark P2) | Med | P2 |
| F95 | Model version pinning (model_registry.py) | High | P1 |
| F96 | Pre-flight token counting (truncate if >80%) | Med | P1 |
| F97 | Provider-specific cache control on protocol | Med | P1 |
| F98 | Temporal decay function for freshness | Med | P2 |
| F99 | Query decomposition for complex questions | Low | P3 |
| F100 | Confidence calibration visible in responses | Med | P1 |
| F101 | Transparent degradation messages | Low | P1 |
| F102 | Output monitoring (regex + prompt hardening) | High | P1 |
| F103 | Tool results in audit log (500 char, scrubbed) | Med | P2 |
| F104 | Cross-org data leakage integration test | High | P2 |
| F105 | Correction confidence check (<0.8 → ask user) | Med | P2 |
| F106 | Structured output for tool dispatch | Med | P1 |
| F107 | Batch embedding at ingestion (groups of 100) | Med | P2 |
| F108 | Agent loop tracing (structured trace in audit_log) | High | P1 |
| F109 | Retrieval precision measurement (correction proxy) | Med | P2 |
| F110 | Prompt versioning (log .mdc git SHA) | Med | P1 |
| F111 | Chain-of-thought control in ClassifyAndRoute | Low | P3 |
| F112 | Constitutional AI principles (5 testable assertions) | Med | P1/P2 |

### Round 7: A+ Push — Technical (F113-F126)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F113 | Pull hybrid PII (Presidio NER) from P9 to P2 — regex misses composite PII | High | P2 |
| F114 | Three-layer eval columns in audit_log from P1 | High | P1 |
| F115 | Nightly self-improvement cron from P3 | High | P3 |
| F116 | Critic agent: cheaper model audits traces async post-response | Med | P2 |
| F117 | Circuit breaker on model fallback chains (Redis sliding window) | High | P1 |
| F118 | Langfuse self-hosted on Hetzner ($0/mo, unlimited traces) | Med | P3 |
| F119 | Procedural memory — compressed trajectories with reliability scores | Med | P5 |
| F120 | Financial entity types on knowledge graph | Med | P2 |
| F121 | Versioned constitution.yaml with critique-revise at inference | High | P1/P2 |
| F122 | Guardrail trigger rate as weekly KPI | Med | P1 |
| F123 | Plaid as Tier 1 connection at P9 | High | P9 |
| F124 | 4-tier connection roadmap: 40+ integrations | Med | P9-P10 |
| F125 | Cross-product knowledge graph moat (tax + banking + entity + compliance) | High | P9 |
| F126 | Apple/Microsoft/Notion/Linear connectors in Tier 2 | Med | P9+3mo |

### Round 7: A+ Push — UX/Design (F127-F140)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F127 | Generative UI: LLM outputs JSON blocks, frontend maps to React components | High | P1/P9 |
| F128 | Action chips: tappable pills reduce cognitive load 60% | High | P9 |
| F129 | Pre-filled assumptions: 80% become single-tap confirmations | High | P9 |
| F130 | Process transparency: animated stepper with checkmark cascade | Med | P1/P9 |
| F131 | Contextual reframing: explain → normalize → empower | High | P9 |
| F132 | Positive-first framing: wins above attention-needed, never shame | Med | P9 |
| F133 | Chunked response bubbles (50-100ms delay) for mobile | Med | P9 |
| F134 | Collapsible inline visualizations (120px, full-screen on tap) | Med | P9 |
| F135 | Swipe-to-confirm for high-stakes (filing, payment) | High | P9 |
| F136 | Shareworthy first impression: screenshot-worthy refund screen | Med | P9 |
| F137 | Trust escalation: zero-risk → competence → data → financial → submission | High | P9 |
| F138 | Personality modes: Encouraging, Direct, Detailed | Med | P4/P9 |
| F139 | 60-second value delivery: refund estimate before account creation | Crit | P9 |
| F140 | Dynamic memory greeting with action chip | Med | P9 |

### Round 7: A+ Push — Growth/Social (F141-F148)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F141 | Tax Season Wrapped: 6-card shareable story post-filing | High | P9 |
| F142 | Robinhood-style pre-launch waitlist: 50-100K target | Crit | Pre-launch |
| F143 | Double-sided referral: activation = completed return | High | P9 |
| F144 | Reddit organic: 90/10 rule, founder accounts | Med | Pre-launch |
| F145 | Programmatic SEO: 200+ pages from packages/data/ JSON | High | P9-3mo |
| F146 | TikTok 2-3x/day with Spark Ads burst ($20-50/day) | High | Pre-launch |
| F147 | Cross-product referral loops: FileFree ↔ LaunchFree | Med | P9 |
| F148 | Discord community + UGC flywheel | Med | P9 |

### Round 8: Memory Moat + Mobile + Email Pipeline (F149-F163)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F149 | `apps/brain-mobile/` via Expo. Brain IS the app. 6-8 week MVP. | High | P9 |
| F150 | Memory IS the moat. Intelligence is commodity. Switching cost = memories × time × trust. | Crit | ALL |
| F151 | Vault-classified memories: encrypted, excluded from embeddings, biometric-gated | High | P2/P9 |
| F152 | Universal capture via chat: photos, API keys, life events → entities forever | High | P2/P9 |
| F153 | Proactive intelligence from memory: deadlines, anomalies, predictions | High | P6/P9 |
| F154 | Email-first onboarding: Gmail OAuth is Day 0, not tax filing | Crit | P7/P9 |
| F155 | Brain Fill Meter: animated "847 things learned," FOMO drives conversion | High | P9 |
| F156 | Free tier: unlimited ingestion + 10 queries/month | High | P9 |
| F157 | Gmail verification takes 6-12 weeks + CASA ($540+/yr). START P7. | Crit | P7 |
| F158 | Three-provider email: Gmail + Microsoft Graph + IMAP fallback | High | P7/P9 |
| F159 | Hybrid extraction: regex pre-extracts, LLM verifies. Top 50 parsers. | High | P7 |
| F160 | Email cost: ~$5.45/user onboard, ~$0.30/mo ongoing (pre-D52) | High | P7/P9 |
| F161 | 7-phase pipeline: fetch → filter → classify → extract → dedup → store | High | P7 |
| F162 | Email schema: parsed_emails + transactions + subscriptions + vendors | Med | P7 |
| F163 | Gmail Pub/Sub push (7d renewal), Microsoft webhooks (3d), IMAP polling | Med | P7/P9 |

### Round 8: Brain Fill Meter Psychology + brain.ai Lessons (F164-F175)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F164 | brain.ai ($51.5M) failed: horizontal, no moat, replaced by ElevenLabs | Med | — |
| F165 | 8 psychological effects stack for Brain Fill Meter | High | P9 |
| F166 | 6 gamification levels: Awakening → Omniscience | Med | P9 |
| F167 | Duolingo-adapted notification escalation (5-rule ladder) | High | P9 |
| F168 | 3 shareable card formats: Identity, Surprise, Archetype | High | P9 |
| F169 | 7 TikTok formats: "Watch Brain Fill Up," reactions, "Brain vs Brain" | High | Pre-launch/P9 |
| F170 | Endowed progress: NEVER start at zero, jump to 15-20% | High | P9 |
| F171 | Cost: $0.0009/query, $0.08-0.38/mo per free user (pre-D52) | High | P9 |
| F172 | Monthly Brain Report Card (rolling, not just annual) | High | P9 |
| F173 | Shareable Brain card = highest-leverage viral mechanic | High | P9 |
| F174 | Frontloading: 5 queries week 1, 5 across weeks 2-4 | Med | P9 |
| F175 | Data Portability Paradox: inferred data is non-portable moat | Med | P9 |

### Round 8: Tiered Email Processing (F176-F187)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F176 | `gmail.metadata` scope: headers + snippet WITHOUT body. "We never read your emails." | Crit | P7 |
| F177 | MIT Immersion (2013): 3 metadata fields reveal life transitions | High | — |
| F178 | Stanford (2016): 57% medical, 40% financial detectable from metadata | High | — |
| F179 | Free-tier metadata: 600-800 items in 30 seconds, zero LLM | Crit | P7/P9 |
| F180 | Subject-line regex: 70-80% transaction detection, 40-60% amounts | High | P7 |
| F181 | Subscription detection from metadata frequency + List-Unsubscribe | High | P7 |
| F182 | Sender-domain database (500-1K domains): 60-70% of automated email | High | P7 |
| F183 | Cross-user template amortization: costs DECREASE with scale | Crit | P9 |
| F184 | 5 optimization layers: combined $5.45 → $0.25-0.50 | High | P7/P9 |
| F185 | Progressive/lazy processing: 80%+ emails never queried | High | P7 |
| F186 | "See vs Understand" upgrade prompt: shows value gap, not feature gate | High | P9 |
| F187 | Privacy-as-marketing: "847 things, never read a single email" TikTok hook | High | Pre-launch |

### Round 9: Circle Sharing + Dual-Context (F188-F195)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F188 | Circle sharing: lightweight B2C sharing primitive for couples/family/partners (D53) | High | P9 |
| F189 | Auto-detection of shared services from overlapping email metadata across Circle members | High | P10 |
| F190 | Calendar auto-sharing is Day 1 value for Circles — more frequent than financial queries | High | P9 |
| F191 | Kids/family lock-in: school, pediatrician, activities, daycare = family OS | Med | P10 |
| F192 | Family plan pricing ($39/yr for 2): Spotify Family proves 10% churn vs 30% individual | High | P9 |
| F193 | "Our Year in Review": couple Wrapped variant, extremely shareable | High | P9 |
| F194 | Dual-context architecture: same person in personal Brain + org Brain + household Circle (D54) | High | P9 |
| F195 | The "we" pronoun: circle context uses "we/us/our" language, validates partnership | Med | P9 |

### Round 10: Brain Interaction Model + Delegated Access (F196-F210)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F196 | Cross-context query composition: questions spanning personal + circle + org need parallel retrieval + scope-aware RRF fusion (D55) | High | P9 |
| F197 | Scope classifier needed in ClassifyAndRoute to detect multi-scope queries automatically | High | P9 |
| F198 | Brain Identity System: visual context indicators (avatar rings, context pill, response badges) so user always knows which brain they're talking to (D56) | High | P9 |
| F199 | Delegated access: one-way, category-scoped, time-limited sharing with CPAs/advisors/lawyers (D57) | High | P9 |
| F200 | Anti-data-leak: no export for delegates, watermarking, FLAG_SECURE on mobile, scraping detection (200+ episodes in 5 min = auto-revoke) | Critical | P9 |
| F201 | Anti-over-access: category scoping, structurally impossible categories (SSN/vault never sharable), share preview before activation | Critical | P9 |
| F202 | Anti-lingering: mandatory expiration (max 1 year), auto-revoke on inactivity (14 days), zombie detection in nightly consolidation | High | P9 |
| F203 | Delegates see read-only dashboard, cannot query Brain conversationally or modify data | High | P9 |
| F204 | No auto-sharing in circles — Brain detects overlaps and SUGGESTS, owner must approve every share individually | Critical | P9 |
| F205 | Circle offboarding: either member leaves unilaterally, access revoked immediately, shared episodes marked "former" | High | P9 |
| F206 | Constitutional principles P006 (circle privacy) and P007 (delegate scope enforcement) added to constitution.yaml | Critical | P1 |
| F207 | Entity merge protocol: two personal entities resolve to shared entity with circle_id when owner approves overlap | Med | P10 |
| F208 | Joint Circle Meter: three bars (yours, partner's, "Our Brain") — combined always highest, motivates the person behind | High | P9 |
| F209 | Context-mode persona adaptation: pronouns + emotional register shift by active context (personal/circle/org/delegate) | Med | P9 |
| F210 | Access audit log: every delegate and circle data access logged with timestamp, IP, device fingerprint, suspicious pattern flagging | High | P9 |

---

## 20. Phased Execution Plan

### P0: Infra Healing (~30 min)

Branch: `feat/brain-phase-0-infra-healing`

Fix `deploy-n8n.yaml` + `scripts/deploy-n8n-workflows.sh`:
1. Keep `docker exec ... n8n import:workflow` (CLI-only)
2. Keep `docker exec ... n8n publish:workflow` (CLI-only)
3. Remove `docker restart "$CONTAINER"` (root cause of F19)
4. Remove `sleep 15`
5. Replace CLI verification with REST API: `GET http://localhost:5678/api/v1/workflows?limit=250` via SSH+curl
6. Auto-activate inactive: `POST http://localhost:5678/api/v1/workflows/{id}/activate`

Create `workflow-watchdog.json`: 5-min cron, auto-activate + alert to #alerts, Neon warmup. Open PR, Copilot review.

### P1: Brain API Core (~5-7 days)

Branch: `feat/brain-phase-1-core`

- Create `apis/brain/` — full service structure
- Alembic migration: full schema from Section 2 (all tables, populated in P2+)
- Create 16 `PersonaSpec` YAMLs + `.mdc` files (D31) + `route_persona` coverage per `docs/BRAIN_PERSONAS.md`
- Agent loop with max 5 iterations, idempotency, ask_user tool (D2/D10/F92)
- Safety: auth, PII scrub, injection defense, emergency brake, output monitoring, constitutional assertions (D9/D11/F24/F102/F112)
- Tool executor with retry policy (F91), structured output (F106), timeouts (D17)
- Prompt assembly: caching (D3/F97), reformulation (D4), thread windowing (D8), pre-flight token counting (F96)
- Model service with fallback chains (D14), model version pinning (F95)
- SSE streaming: POST /brain/stream (F55)
- Persona router: hierarchical Tier 0→1→2 with collaboration protocol (D31)
- Scale abstractions: protocols.py (F32)
- Agent loop tracing: structured trace in audit_log (F108)
- Prompt versioning: log .mdc git SHA (F110)
- Redis safe wrappers (F3), structlog (F13), n8n_execution_id (F14)
- Deep health check (F15), concurrency semaphore (F26), connection pooling (F27)
- Rate limiting via slowapi (F35)
- Confidence calibration in HUMILITY wisdom + prompt template (F100)
- Transparent degradation messages (F101)
- Latency budget: p50 <2s, p95 <5s, abort >8s (F72)
- Source attribution in responses (F74)
- Async response pattern: >15s → background task (F76)
- Slack adapter: chunked response posting (F77)
- Search endpoint: GET /brain/search (F88)
- Weekly Brain Health Report SQL with 5 AI Lead persona sections (F65/D30)
- Golden test set: 10 queries in tests/golden_queries.json (F93)
- @-mention persona forcing (F37)
- Brain API health monitoring in `brain_infra_health` (legacy export: `infra/hetzner/workflows/retired/infra-health-check.json`)
- Three-layer eval columns in audit_log schema (D34/F114)
- Defense-in-depth: 4-layer guardrail architecture (D36)
- `constitution.yaml` file with initial principles + logging (D37)
- Circuit breaker on model fallback chains (D38/F117)
- Guardrail trigger rate tracking in Brain Health Report (F122)
- Generative UI component registry definition (F127)
- Process transparency SSE events (F130)
- Render Standard ($25/mo) from day one (F59/F68)
- Add to render.yaml, compose.dev.yaml, Makefile
- Rewrite agent-thread-handler.json as thin Slack adapter

### P2: Memory + Profiles + Olga's EA (~4-6 days)

Branch: `feat/brain-phase-2-memory`

- Alembic migration: add relationship_type, direction to entity_edges (F64)
- Hybrid retrieval with RRF weights (D5)
- 4th retrieval path: 1-hop entity graph traversal (F61)
- Memory fatigue with on-topic thread exemption (D15/F63)
- Correction boosting with hybrid detection + confidence check (D16/F6/F105)
- Explicit memory tools (D25/F36)
- Extended PII patterns (F9), quality gate with density check (F28)
- Gemini Flash for extraction + quality gate (F30)
- Temporal decay: freshness = exp(-lambda * days), lambda per source type (F98)
- Cache user→team_id in Redis (F60)
- Ingestion deduplication: embedding similarity >0.9 → merge (F62)
- Batch embedding: groups of 100 via embed_batch (F107)
- Bootstrap: KNOWLEDGE.md + TASKS.md only, stricter quality gate (F8/F38)
- Retrieval precision measurement via correction proxy (F109)
- Cross-org leakage integration test (F104)
- Tool results summary in audit_log (F103)
- Intelligence Index baseline (F66)
- Response metadata for "show your work" (F86)
- Output fact-checking against knowledge graph (F73)
- Embedding migration documented (F12), backup strategy (F22)
- Admin audit log (F47), A/B columns in audit_log (F34)
- Pull Presidio NER to P2 — hybrid PII detection (F113)
- Critique-revise loop on output filter via constitution.yaml (D37)
- Critic agent: async post-response audit using GPT-4o-mini (F116)
- Financial entity types added to extraction (F120)
- Olga's EA live

### P3: Tasks + Cursor Bridge + Chaining (~2-3 days)

- Task tools (create_task, update_doc)
- Concurrent tool execution (F16)
- ClassifyAndRoute with CoT control (D20/F111)
- SearchAndSynthesize with Gemini grounding (D20/F31)
- ExtractAndReason (D20)
- Query decomposition for complex questions (F99)
- Validate ClassifyAndRoute savings vs actual distribution (F56)
- Nightly self-improvement cron: `brain-self-improvement.json` (D35/F115)
- Full circuit breaker + gateway pattern with smart routing (D38)
- Deploy Langfuse on Hetzner (D41/F118)

### P4: Delegation + Sleep Cycles (~2 days)

- Multi-persona composition (consult_persona)
- Per-user autonomy tiers
- AdversarialReview chain for Tier 2/3 (D20)
- Nightly consolidation: profile extraction, contradiction detection, entity GC, knowledge decay
- AI Lead personas run nightly analysis steps
- Personality mode system prompts: Encouraging/Direct/Detailed (D44/F138)

### P5: Cost + Self-Improvement + Studio Dashboard (~2-3 days)

- Cost collector with chain_strategy tracking
- A/B testing framework (F34)
- Chain selector auto-tuning from A/B data (F67)
- Eval framework: golden scenarios + correction rate + recall precision (F29)
- Populate causal/temporal relationship_type on entity edges (F64)
- Consensus chain (D20)
- Semantic cache protocol (F57, activate P9)
- Per-org storage quotas (F10)
- Persona evolution: Retrieval Lead runs weekly persona health checks
- Procedural memory: `agent_procedures` table + pattern extraction (D40/F119)
- Langfuse full dashboards + A/B testing integration (D41)
- Studio: Overview, Costs, Audit, Memory

### P6: Proactive Intelligence (~1-2 days)

- Nightly analysis: stale entities, sprint drift, knowledge decay
- Per-user briefings, cross-founder notifications
- Notification architecture: email digest, push, in-app (F75)
- Intelligence demonstration moments (F78)
- Studio: Conversations, entity graph

### P7: Gmail + Email Ingestion + Calendar (~5-7 days)

- **START Gmail OAuth verification for BOTH scopes**: `gmail.metadata` (free tier) AND `gmail.readonly` (paid tier) — 6-12 week timeline (F157/F176)
- **Build metadata-first pipeline FIRST** (D52): sender-domain classifier (500+ known domains), subject-line regex, frequency analyzer, timestamp analyzer, social graph builder
- Email ingestion pipeline: `apis/brain/services/email_ingestion/` (D50)
- Gmail API integration: OAuth2, batch fetch, Pub/Sub push notifications
- 7-phase processing: fetch → filter → classify → extract → dedup → store (F161)
- Sender-specific regex parsers for top 50-100 financial senders (F159)
- Hybrid extraction for paid tier: templates → sampling → Gemini Flash batch → on-demand (D52/F184)
- Email schema migration: parsed_emails, email_transactions, detected_subscriptions, vendors (F162)
- Cross-user template registry: cache extraction schemas per sender domain (F183)
- Thread dedup (JWZ) + entity-level dedup (F161)
- Gmail watch() + Pub/Sub for ongoing processing (F163)
- Calendar integration
- OpenAI Batch API for 50% cost reduction on bulk extraction

### Pre-Launch: Growth Foundation

- Robinhood-style referral waitlist with position number + referral jumping (D46/F142)
- Reddit organic presence: warm founder accounts, 3-5 helpful answers/day (D47/F144)
- TikTok content at 2-3x/day with hook-first format + Spark Ads burst (D47/F146)
- AI content pipeline on n8n (D33) generating drafts for Postiz scheduling
- Brain.ai competitive lessons integrated into positioning (F164)

### P8: Personal Life + Multimodal + PWA (~3 days)

- Personal Gmail, personal life entities
- Image/screenshot processing (Gemini Pro Vision)
- Voice transcription via Whisper (D29)
- Studio PWA
- **GO/NO-GO GATE (F71)**: Intelligence Index >0.7, correction rate <5%, p95 <8s, zero critical bugs 30 days

### P9: Brain-as-a-Product MVP (~5-7 days)

- `apps/brain/` Next.js: chat-first, progressive sidebar, Brain Moments share UI (F79-F88)
- First message design (F80), emotional design (F81), mobile-first (F85)
- SSE streaming frontend integration (F55)
- Google Workspace connector #1 B2C (F89), Slack connector for B2B
- Fix agent_connections UNIQUE (F54), NER PII via Presidio (F49)
- Per-org OAuth key derivation via HKDF (F50)
- Consent model + ToS (F51), enterprise correction escalation (F52)
- Knowledge lifecycle: onboarding seed, offboarding extraction (D21)
- GDPR endpoints (D28), Free/Pro/Team tiers (D27)
- Free tier: 100 msg/mo or 500 episode cap (F70)
- Voice output TTS (D29), conversation threads (F87, agent_conversations table)
- Slack App Directory submission (F69), separate sync worker (F58)
- Semantic cache activation (F57), connection health (F44), retention enforcement (F46)
- **Brain Fill Meter** (D51): 8 psychological effects, 6 gamification levels, notification escalation, 3 shareable card formats, endowed progress (never start at zero)
- Brain Fill Meter UI: animated orb, category counts, level system, milestone celebrations, FOMO paywall
- Generative UI: full component library — RefundCard, StatusSelector, DocumentUpload, BreakdownChart, AssumptionCard, ActionChips, ProcessStepper, PaymentPlanCard (D42)
- Trust escalation ladder: zero-risk → competence → data → financial → submission (D43/F137)
- 60-second value delivery: refund estimate before account creation (F139)
- Anxiety-reducing patterns: reframing, positive-first, calm metrics, disclosure, chunked bubbles, personality modes (D44)
- Micro-interactions: swipe-to-confirm (F135), scan cascade, confidence glow, refund count-up + confetti
- Tax Season Wrapped: 6-card shareable story (D45)
- Double-sided referral program (D46)
- Cross-product referral loops: FileFree ↔ LaunchFree (F147)
- Discord community launch + UGC flywheel (D47/F148)
- Plaid Link as Tier 1 connection (D39/F123)
- Microsoft Graph email + IMAP fallback (D50/F158)
- Cross-user template amortization from launch (D52/F183)
- Tiered "See vs Understand" processing logic (D52)
- **Mobile app**: `apps/brain-mobile/` via Expo + NativeWind + Solito (D48/F149)
- **Circle sharing** (D53/F188): circle schema, invitation flow, per-connection sharing controls, "we/us/our" pronoun in circle context
- Calendar auto-sharing for household circles (F190)
- Family plan pricing tier: $39/yr for 2 (F192)
- "Our Year in Review" couple Wrapped variant (F193)
- Dual-context UI: context switching between personal/org/circle brains (D54/F194)
- **Cross-context query composition** (D55/F196): scope classifier in ClassifyAndRoute, parallel retrieval, scope-aware RRF weights, source attribution in responses
- **Brain Identity System** (D56/F198): avatar rings per context, context pill, response badges, conversational switching
- **Delegated access** (D57/F199): category-scoped sharing with CPAs/advisors, three-layer anti-misuse (no export, watermarking, scraping detection, mandatory expiry, auto-revoke), read-only delegate dashboard
- Access audit log for all circle and delegate data access (F210)
- No auto-sharing enforcement: overlap detection as suggestions only, owner-approved (F204)
- Circle offboarding: unilateral leave, immediate access revocation (F205)
- Joint Circle Meter: three-bar visualization (F208)
- Context-mode persona adaptation: pronoun and tone switching (F209)
- Brain Moments infrastructure (D32): insight detection, card generation, share UI (all life domains)
- 7-agent content pipeline on n8n (D33): Trend Scout, Writer, Compliance, Visual, Publisher
- Postiz integration for multi-platform publishing
- Landing page, Product Hunt prep
- Cross-product tool definitions (F90)
- **Life Intelligence System** (D58/F211-F213): Google Maps Location History connector (Tier 1), lifestyle archetype inference from email + Maps + Plaid + calendar, retention arc (lifestyle early → finance mid → couples late)
- **Contextual Intelligence Monetization** (D59/F215-F220): referral partnership integrations (insurance, banking, credit cards), recommendation engine, "Brain Suggestion" UI with transparency badge, 7 design principles
- **Proactive Insight Delivery** (D60/F221-F222): nightly insight queue, 5-channel delivery (in-app, push, weekly Brain Brief via React Email, real-time alerts, circle notifications), notification escalation
- **Consumer Brain Personality** (D24/F225): warm, slightly witty consumer persona mode
- **Lifestyle Generative UI** (D42/F223): RestaurantCard, TripCard, RoutineCard, LifestyleInsightCard
- **First 5 Minutes Lifestyle Wow** (D22/F223): Google OAuth → real-time counter → lifestyle insight at 3:00
- **Staircase pricing** (D27/F218-F219): $29 Y1 → $49 Y2 Personal, Together/Family tiers, memory retention per tier

### P9-3mo: Programmatic SEO

- 200+ pages via Trinkets (tools.filefree.ai) from packages/data/ JSON configs (D47/F145)
- State tax calculators, LLC cost guides, LLC vs Sole Prop, profession deductions

### P10: Enterprise + Scale (~ongoing)

- Business/Enterprise tiers (D27)
- SOC 2 prep (F42), data residency (F43)
- Connector SDK (F45), additional connectors
- Voice conversation mode (D29)
- Creator outreach program, SEO content engine at scale
- Enterprise admin controls, SSO, custom DPA
- Scale: swap Protocol implementations as needed

---

## 21. Monthly Cost Model

| Component | P0-P2 | P3+ | Product Launch |
|-----------|-------|-----|----------------|
| Brain API (Render Standard) | $25 | $25 | $25+ |
| Claude Sonnet (cached) | ~$13 | ~$8 | per-org |
| Claude Opus (cached) | ~$10 | ~$6 | per-org |
| GPT-4o | ~$7 | ~$4 | per-org |
| GPT-4o-mini | ~$1.50 | ~$2 | per-org |
| Gemini Flash | ~$0.50 | ~$2 | per-org |
| Embeddings | ~$0.50 | ~$0.50 | per-org |
| **Internal total** | **~$58/mo** | **~$48/mo** | — |
| **Per-org COGS** | — | — | **~$6-10/user/mo** |

### Cost Sensitivity (F56)

| Simple/Med/Complex | Monthly model cost | COGS/user |
|--------------------|-------------------|-----------|
| 75/20/5 (optimistic) | $16.50 | ~$6-8 |
| 60/25/15 (moderate) | $22.00 | ~$9-12 |
| 50/30/20 (conservative) | $27.00 | ~$12-15 |

At conservative, Team tier ($19/user) margin = 21%. Still viable but validate against 2 weeks of actual classification data.

### Email Ingestion COGS (D52)

| Metric | Free Tier | Paid Tier |
|--------|-----------|-----------|
| Onboarding (10K emails) | $0.05 (metadata only) | $0.25-0.50 |
| Monthly ongoing | $0.03 | $0.39 |
| 100K free users/month | $3,000 | — |
| Break-even conversion | — | ~1.5% |

Cross-user template amortization: cost per paid user decreases with scale (10 users: $0.45, 1K users: $0.20, 10K users: $0.15). See Section 18 for full model.

### Referral Revenue Model (D59 — Contextual Intelligence Monetization)

Subscriptions are the engagement wrapper (~25% of revenue). The real business is the Credit Karma playbook: know enough about someone's life to make contextual, high-value recommendations.

**Credit Karma proof point**: $2.3B revenue FY2025. 140M members. ~$16/member/year. $0 subscription. 100% from financial product referrals. Acquired by Intuit for $8.1B.

**Brain's advantage**: Credit Karma knows your credit score. The Brain knows your income, spending, tax situation, business structure, banking relationships, insurance, life events, dining habits, travel patterns, fitness routines, and lifestyle preferences. 5-10x the signal = better recommendations = higher conversion = higher CPA.

| Revenue Stream | Users Who See It | Conversion | Avg CPA | Notes |
|---------------|------------------|------------|---------|-------|
| Insurance comparison | 30% of paid users | 8% | $75 | "Your insurance went up 15%" |
| Banking/savings referral | 25% of paid users | 5% | $150 | "Fee-free accounts earn 4% APY" |
| Credit card referral | 20% of paid users | 4% | $150 | "A dining card could earn $960/yr" |
| Tax filing (FileFree) | 60% of all users | 40% | $35 | "W-2 arrived — 5 minutes to file" |
| LLC formation (LaunchFree) | 10% of paid users | 15% | $60 | "$85K freelancing → LLC saves $3-5K" |
| Compliance-as-a-Service | LLC formers | 30% | $74 | Annual report reminders → upsell |

**Year 1 (10K users, 2K paid)**: Subscriptions ~$70K + tax filing referrals ~$210K + financial product referrals ~$10K = **~$294K total**. Subscriptions are 24%. Referrals are 76%.

**Year 2 (50K users, 8K paid at Y2 pricing)**: ~$1.54M. **Year 3 (200K users, 25K paid)**: ~$6.8M. At scale, subscription revenue is gravy — the referral engine is the business.

---

## 22. Render Blueprint

```yaml
  - type: web
    name: brain-api
    runtime: python
    region: oregon
    plan: standard
    buildCommand: cd apis/brain && pip install -r requirements.txt
    preDeployCommand: cd apis/brain && alembic upgrade head
    startCommand: >-
      cd apis/brain && gunicorn app.main:app
      -k uvicorn.workers.UvicornWorker
      --bind 0.0.0.0:$PORT
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: GOOGLE_AI_API_KEY
        sync: false
      - key: BRAVE_SEARCH_API_KEY
        sync: false
      - key: GITHUB_TOKEN
        sync: false
      - key: BRAIN_API_SECRET
        generateValue: true
      - key: ALLOWED_USER_IDS
        value: "sankalp,olga"
      - key: ENVIRONMENT
        value: production
      - key: PYTHON_VERSION
        value: "3.11.0"
```

---

## 23. Completeness Scorecard

| Dimension | Status |
|-----------|--------|
| Channel abstraction | COMPLETE (D2) |
| Multi-user + hierarchy | COMPLETE (D6, D12, D19) |
| Safety + compliance | COMPLETE (D9, D11, D28, F49-F53, F102, F112) |
| Retrieval quality | COMPLETE (D5, D15, D16, F60-F63, F98, F109) |
| Model intelligence | COMPLETE (D14, D20, F56, F95-F97, F106) |
| Cost management | COMPLETE (D3, D7, D20, F59/F68) |
| Reliability | COMPLETE (D10, D14, D18, F3, F4, F26, F91) |
| Observability | COMPLETE (F13, F14, F65, F66, F93, F108, F110) |
| Persona architecture | COMPLETE (D30, D31 — 16 `PersonaSpec` personas, 4 tiers, collaboration protocol) |
| Knowledge lifecycle | COMPLETE (D21, F51) |
| Connections | COMPLETE (D26, F54, F69) |
| Pricing + GTM | COMPLETE (D27, D32, D33, F70, F90) |
| Competitive positioning | COMPLETE (Origin, Monarch, Copilot analysis) |
| Enterprise compliance | COMPLETE (D28, F50) |
| Scale readiness | COMPLETE (protocols.py, F57, F58) |
| Streaming | COMPLETE (F55) |
| Latency management | COMPLETE (F72, F76) |
| Source attribution | COMPLETE (F74, F86) |
| Output quality | COMPLETE (F73, F100, F102) |
| Notifications | COMPLETE (F75, F78) |
| B2C UX | COMPLETE (F79-F85, chat-first) |
| Voice | COMPLETE (D29) |
| Search | COMPLETE (F88) |
| Social/viral mechanics | COMPLETE (D32, D33, 7-agent pipeline) |
| Go/No-Go gate | COMPLETE (F71) |
| Meta-product vision | COMPLETE (F90) |
| Brain-as-a-Product | DESIGNED (P9) |
| **UX/Design** | **COMPLETE (D42-D44, F127-F140 — generative UI, trust ladder, anxiety patterns)** |
| **Growth/Social** | **COMPLETE (D45-D47, D51, F141-F148, F165-F174 — Wrapped, referral, Brain Fill Meter, SEO)** |
| Connection roadmap | COMPLETE (D39, F123-F126 — 4 tiers, 40+ integrations) |
| Email ingestion | COMPLETE (D50, D52, F157-F163, F176-F187 — tiered processing) |
| Memory moat | COMPLETE (D49, F150-F156 — vault, email-first, fill meter) |
| Mobile strategy | COMPLETE (D48, F149 — Expo React Native) |
| Evaluation framework | COMPLETE (D34-D35, F114-F115 — three-layer eval, self-improvement) |
| Constitutional AI | COMPLETE (D36-D37, F121 — defense-in-depth, versioned constitution) |
| Production observability | COMPLETE (D38, D41, F117-F118 — circuit breaker, Langfuse) |
| Procedural memory | COMPLETE (D40, F119) |
| **Circle/household sharing** | **COMPLETE (D53, F188-F193 — auto-detection, calendar, family plan, couple Wrapped)** |
| Dual-context architecture | COMPLETE (D54, F194 — personal + org + circle) |
| **Cross-context query composition** | **COMPLETE (D55, F196-F197 — scope classifier, parallel retrieval, scope-aware RRF)** |
| Brain Identity System | COMPLETE (D56, F198 — avatar rings, context pill, response badges) |
| **Delegated access + anti-misuse** | **COMPLETE (D57, F199-F203 — three-layer anti-misuse, category scoping, audit trail)** |
| No-auto-share enforcement | COMPLETE (F204 — owner approves every share, detection opt-in) |
| Access audit trail | COMPLETE (F210 — full audit log for circle + delegate access) |
| **Life Intelligence System** | **COMPLETE (D58, F211-F213, F226-F227 — all domains equal, archetype inference, Google Maps Tier 1, memory trivially cheap)** |
| **Contextual Intelligence Monetization** | **COMPLETE (D59, F215-F220 — three-layer revenue, Credit Karma playbook, targeted 10K, staircase pricing)** |
| **Proactive Insight Delivery** | **COMPLETE (D60, F221-F222 — five channels, weekly Brain Brief, notification escalation)** |
| Lifestyle Generative UI | COMPLETE (F223 — RestaurantCard, TripCard, RoutineCard, LifestyleInsightCard) |
| Consumer Brain personality | COMPLETE (D24/F225 — warm, witty, celebrates, remembers like a friend) |
| First 5 minutes lifestyle wow | COMPLETE (D22/F223 — Google OAuth → 847 things → restaurant insight at 3:00) |
| Memory retention pricing lever | COMPLETE (D27/F228 — Free 1yr, Personal 5yr, Together/Family lifetime) |

---

## 24. Brain-as-a-Service Viability

### Market Position

Brain is an AI life intelligence system — not a search bar, not a budgeting app, not a financial advisor. It occupies a new category: a partner that knows your entire life (finances, routines, restaurants, trips, fitness, relationships) and gets smarter every day. No competitor combines persistent hierarchical memory + free tax filing + free LLC formation + email knowledge extraction + lifestyle intelligence + couples/household sharing. The closest is Origin ($156/yr) with 2 of 7. Brain offers all 7, starting at $0.

### Financial Viability — Three-Layer Revenue Model

Revenue is NOT just subscriptions. Three layers coexist (D59):

**Layer 1 — Subscriptions (~25% of revenue)**: Personal $29 Y1 → $49 Y2 / Together $49 Y1 → $79 Y2 / Family $79 Y1 → $129 Y2 / Team $19/user/mo. The engagement wrapper that keeps users active so the referral engine has signal.

**Layer 2 — Financial product referrals (~50% of revenue)**: Credit Karma playbook. Insurance comparison (CPA $50-100), banking referral (CPA $100-200), credit card referral (CPA $100-300), tax filing (FileFree, $30-50/return), LLC formation (LaunchFree). Brain has 5-10x the signal Credit Karma has.

**Layer 3 — Lifestyle intelligence (~25% at scale)**: Subscription optimization, dining deals, travel deals, experience recommendations. Activates at 500K+ users.

At Team tier ($19/user/mo) with 1000 orgs (avg 10 users): COGS ~$5-8/org/mo, revenue ~$190/org/mo, gross margin ~94-97%. Break-even: ~8-10 paying users covers internal infra ($58/mo). Path to $1M ARR: ~3,000 Personal users OR ~5,000 Team users OR (more likely) ~2,000 paid users + referral revenue from all active users.

### Operational Risks

Support burden (mitigated by Brain Knowledge State communication, F40). Model cost spikes (mitigated by per-org limits, ClassifyAndRoute). Connector maintenance (mitigated by F44, start with 3 connectors). SOC 2 timeline (build audit-ready from P2, formal certification P10).

### Go-to-Market Path

1. Internal dogfood (P1-P8)
2. Go/No-Go gate (F71, end of P8)
3. Closed beta — 10-20 hand-picked users from target cohorts: freelancers, couples (early P9)
4. Tax Season 2027 launch with introductory pricing ($29 Personal Y1, $49 Together Y1) — target 3,000 tax filers via TikTok + Reddit
5. Post-tax-season lifestyle expansion — Brain stays relevant year-round
6. Year 2 renewal at full pricing — Brain Fill Meter shows 1,500+ things learned, switching cost is prohibitive
7. Enterprise sales (P10)

---

## 25. Review Rounds Summary

**Round 1-3**: Anthropic safety + OpenAI scaling + Perplexity retrieval + DeepMind intelligence + Opus synthesis. 48 findings.

**Round 4**: Board review — Amodei (B+→A-), Altman (B+→A-), Srinivas (A-→A), Hassabis (B→A-). 23 findings. All enterprise-blocking items correctly deferred to P9.

**Round 5**: AI Lead product intelligence + Jony Ive/Steve Jobs B2C UX review. 19 findings. Strategic reframing: Brain as meta-product, Google-first B2C onboarding, chat-first single-page UX.

**Round 6**: CTO production review (7 items: schema boundary, time estimates, deploy fix precision, watchdog, brain health monitoring, conversations table, F90 confirmation) + Top 5 AI Leads deep dive (Karpathy ML Systems, Fan Agent Infra, Chase Retrieval, Weng Prompt/Safety, Amodei/Askell Constitutional AI). 22 findings (F91-F112). Hierarchical persona architecture (D31). Automated social content engine (D33). Origin competitive analysis. Solopreneur wedge GTM.

**Round 7**: A+ grade push across 7 dimensions. Added Jony Ive (Design/UX) and Andrew Chen (Growth/Social) as formal reviewers. 36 findings (F113-F148). D34-D47: three-layer eval, nightly self-improvement, defense-in-depth guardrails, versioned constitutional AI, circuit breaker, connection roadmap, procedural memory, Langfuse, generative UI, trust ladder, anxiety-reducing UX, Tax Season Wrapped, double-sided referral, community growth flywheel.

**Round 8**: Memory Moat + Email Ingestion + Brain Fill Meter deep dive. 39 findings (F149-F187). D48-D52: mobile app strategy (Expo), Memory Moat as strategic anchor, email ingestion pipeline (3 providers), Brain Fill Meter psychology engine (8 named effects), tiered email processing "See vs Understand" (cost breakthrough: free tier $0.05 onboard via metadata-only). brain.ai competitive analysis. Cross-user template amortization. Privacy-as-marketing angle.

### v10 Grades (7 Dimensions)

| Dimension | Reviewer | v7 | v8 | v9 | v10 | Key Lever |
|-----------|----------|----|----|-----|-----|-----------|
| Intelligence | Hassabis | B | A- | A+ | **A+** | Three-layer eval + self-improvement + procedural memory + lifestyle archetype inference |
| Retrieval | Srinivas | A- | A | A+ | **A+** | 4-path hybrid + graph traversal + procedural + cross-product + lifestyle graph |
| Design/UX | Ive | — | B+ | A | **A+** | Brain Identity System + lifestyle Generative UI + first 5 min wow + consumer personality |
| Growth/Social | Chen | — | B | A | **A+** | Life intelligence reframe + Credit Karma revenue + targeted acquisition + proactive delivery |
| Safety | Amodei | B+ | A- | A | **A+** | Three-layer anti-misuse + P006/P007 + delegated access + "not recommendy" principles |
| Scaling | Altman | B+ | A- | A | **A+** | Circuit breaker + Langfuse + gateway + memory retention at scale (10yr = 100MB) |
| Product/GTM | Composite | — | A- | A | **A** | 40+ connections + "See vs Understand" + lifestyle moat (assumptions untested) |

**Overall: A+ (6x A+, 1x A, zero below A).** Up from 5x A+, 2x A after Round 10. Design/UX A→A+ (lifestyle UI + consumer personality + first 5 min). Growth A→A+ (life intelligence positioning + Credit Karma revenue + targeted acquisition). Safety A→A+ (7 "not recommendy" principles). Scaling A→A+ (memory retention trivially cheap at scale). Product/GTM held at A — life intelligence thesis and referral revenue model are compelling but unvalidated.

**Strategic throughline (D49 + D51 + D52 + D58 + D59 + D60)**: Memory Moat (accumulated life context is the switching cost) + Brain Fill Meter (psychology makes the moat visible and viral) + Tiered Processing (metadata-only free tier makes economics work at any scale) + Life Intelligence System (all domains equal, data-determined) + Contextual Intelligence Monetization (Credit Karma playbook, subscriptions are the engagement wrapper) + Proactive Insight Delivery (Brain TELLS you things, five channels). D52 is the cost unlock. D58 is the product unlock. D59 is the revenue unlock.

**Round 9**: Circle Sharing + Dual-Context. 8 findings (F188-F195). D53 Circle sharing: lightweight B2C sharing primitive for couples/family/partners with auto-detection from email metadata, calendar auto-sharing, "we/us/our" pronoun design, family plan pricing, "Our Year in Review" couple Wrapped. D54 Dual-Context: same person in personal Brain + org Brain + household Circle. The couple moat is 2x the individual moat.

**Round 10**: Brain Interaction Model + Delegated Access. 15 findings (F196-F210). D55 Cross-context query composition: scope classifier in ClassifyAndRoute, parallel retrieval, scope-aware RRF weights. D56 Brain Identity System: visual context indicators (avatar rings, context pill, response badges). D57 Delegated Access: three-layer anti-misuse architecture (anti-leak, anti-over-access, anti-linger), category-scoped, time-limited, fully audited. No auto-sharing — Brain detects, owner decides. P006 + P007 constitutional principles. Joint Circle Meter. Context-mode persona adaptation.

**Round 11**: McKinsey Strategic Architecture Review + Life Intelligence. 18 findings (F211-F228). D58 Life Intelligence System: Brain reframed from financial advisor to life intelligence — all domains (finance, travel, food, fitness, hobbies, couples) equal, weighted by user data. Google Maps Tier 1. Lifestyle archetype inference. Memory ~10MB/user/year. Retention arc: lifestyle early, finance mid, couples late. D59 Contextual Intelligence Monetization: three-layer revenue (subscription 25%, Credit Karma 50%, lifestyle 25%). 7 "not recommendy" principles. Targeted 10K acquisition. Staircase pricing. Together/Family tiers with lifetime memory. D60 Proactive Insight Delivery: five-channel system. Consumer personality. First 5 min lifestyle wow. 4 lifestyle Generative UI components.

### Round 11: McKinsey Strategic Architecture Review + Life Intelligence (F211-F228)

| # | Finding | Sev | Phase |
|---|---------|-----|-------|
| F211 | Life intelligence reframe: Brain is not a financial advisor with memory — it's a life intelligence system. Financial services are the trust-building entry point (D58) | Strategic | ALL |
| F212 | Lifestyle archetype inference from behavioral signals (email + Maps + Plaid + calendar) without user self-declaration. "Foodie," "traveler," "fitness person" detected from data (D58) | High | P9 |
| F213 | Google Maps Location History added to Tier 1 connections — restaurant visits, gym, commute, travel. The single most powerful lifestyle signal source (D39/D58) | High | P9 |
| F214 | Couple life beyond bills: trips, restaurants, date nights, movies, routines, shared hobbies. Circle conversational examples expanded beyond financial (D53) | High | P9 |
| F215 | Contextual Intelligence Monetization: three-layer revenue model (subscription 25%, financial referrals 50%, lifestyle 25% at scale). Credit Karma playbook with 5-10x the signal (D59) | Crit | P9 |
| F216 | Three revenue layers coexist: subscriptions are the engagement wrapper, referral is the business, lifestyle is the scale play. At 100K users, referral rev is 4.8x subscription rev (D59) | Crit | P9 |
| F217 | 7 "not recommendy" design principles: earn before recommend, insight-first, user controls volume, math shown, celebrate save, some insights free, transparency badge (D59) | High | P9 |
| F218 | Staircase pricing: $29 Y1 → $49 Y2 for Personal. $49 → $79 Together. $79 → $129 Family. Year 1 prices get 67% more users, Year 2 moat justifies full price (D27) | High | P9 |
| F219 | Together ($49 Y1) and Family ($79 Y1) tiers added with lifetime memory retention. Memory retention as conversion lever (D27) | High | P9 |
| F220 | Targeted 10K acquisition strategy: 5 high-intent cohorts (tax filers 3K, LLC formers 2K, freelancers 2.5K, couples 1.5K, new grads 1K). 15-25% conversion vs 2.5% from random. Same revenue, 10x less free user cost (D59) | Crit | Pre-launch |
| F221 | Proactive insight delivery: five-channel system (in-app, push, weekly Brain Brief, real-time alerts, circle notifications). Brain TELLS you things. (D60) | High | P9 |
| F222 | Weekly Brain Brief: Monday email digest with top 3 insights, brain fill progress, one recommendation. React Email. This is the habit loop cue (D60/D51) | High | P9 |
| F223 | First 5 minutes lifestyle wow: Google OAuth → real-time counter → 847 things → first restaurant insight at 3:00 → "I learned your life in 5 minutes" (D22/D58) | Crit | P9 |
| F224 | Retention arc: lifestyle hooks early (daily engagement), financial value mid-term (high-impact), couple expansion mid-funnel (retention multiplier). Avoids seasonal tool trap (D58) | High | P9 |
| F225 | Consumer Brain personality: warm, slightly witty ("8 Thai restaurants — that's an obsession"), celebrates without judging, remembers like a friend, gets better over time (D24) | Med | P4/P9 |
| F226 | Life Companion Domains: Brain is equally strong across finance, travel, food, fitness, hobbies, couples. No domain is weighted — user's data determines richness. Same pattern per domain: ingest → infer → remember → surface (D58) | Strategic | ALL |
| F227 | Memory retention is trivially cheap: ~10MB/user/year. 10 years = 100MB = 20 photos. Consolidation compresses old episodes. Storage is not a constraint for years of memory (D58) | Med | ALL |
| F228 | Memory retention as pricing lever: Free = 1 year, Personal = 5 years, Together/Family = lifetime. "Upgrade to remember everything, forever." Time-depth is a conversion driver (D27/D58) | High | P9 |

All 228 findings integrated. No finding dismissed.

---

## 26. Superseded Documents

This v10 document is the single source of truth for Brain architecture. Earlier Cursor IDE plan exports lived under **`.cursor/plans/`** locally (gitignored; absent from CI checkouts). Treat those snapshots as superseded by this section — do not resurrect historical plan filenames as canonical paths.

