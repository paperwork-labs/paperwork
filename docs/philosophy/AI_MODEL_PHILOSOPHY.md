---
owner: agent-ops
last_reviewed: 2026-04-24
doc_kind: philosophy
domain: ai-models
status: active
---

# AI Model Philosophy

**Companion (mutable list + slugs):** [`docs/AI_MODEL_REGISTRY.md`](../AI_MODEL_REGISTRY.md)

## TL;DR

- **When we use a cheap model:** High volume, well-bounded text, or persona defaults on `gpt-4o-mini` / `o4-mini` (tax math); pre-processing in `ExtractAndReason` uses Flash-class extraction before a larger model answers.
- **When we MUST escalate:** Persona `escalate_if` hits (e.g. `compliance`, `tokens>N`, `mention:…`) so `escalation_model` (usually `claude-opus-4-20250618`); `requires_tools: true` forces MCP-capable paths; user/system passes `strategy=extract_reason` or `classify_route` for explicit chain behavior.
- **Cost ceilings & refusal:** Each persona can set `daily_cost_ceiling_usd` (enforced in `apis/brain/app/services/agent.py` via `cost_tracker`); on breach, respond with a structured “daily cap” error — not a silent model swap. **STALE below:** per-call defaults and org-wide `BRAIN_ORG_DAILY_COST_USD` — **not found in `apis/brain` code search 2026-04-24**; treat as design intent until implemented.

Immutable rules for choosing, chaining, and budgeting LLM calls. Edits require founder + `agent-ops` persona ack, plus `cfo` persona ack for any cost-cap change.

---

## 1. Multi-vendor mandatory

**Implemented today:** Provider fallback and circuit breaking live in `apis/brain/app/services/router.py` (`FALLBACK_MAP`, `CircuitBreaker`). Example: Anthropic down → map Sonnet/Opus to `gpt-4o` for some paths; Google down → `gpt-4o-mini`.

| Class                    | Primary (code)                    | Fallback (code)                                                                                |
|--------------------------|-----------------------------------|------------------------------------------------------------------------------------------------|
| Tool / MCP orchestration | `claude-sonnet-4-20250514`        | `gpt-4o` (per `FALLBACK_MAP`)                                                                  |
| Cheap text / classify    | `gemini-2.5-flash`, `gpt-4o-mini` | Cross-provider map in `FALLBACK_MAP`                                                           |
| Tax / reasoning slice    | `o4-mini`                         | `claude-sonnet-4-20250514` via map                                                             |
| PR review (no MCP)       | `claude-haiku-4-5-20251001`       | **STALE** — code escalates to `claude-sonnet-4-20250514` on critical paths; see `pr_review.py` |

**STALE (aspirational — not implemented as stated in Brain):** Prior text named “GPT-5.5 medium,” “Composer-2-fast,” and “Cohere” as fallbacks. **No such vendors appear in `apis/brain` routing.** If we add a second vendor for a class, document it in `FALLBACK_MAP` + `AI_MODEL_REGISTRY.md` in the same PR.

We do **not** add a third vendor “just in case” without an explicit cost/benefit review.

---

## 2. Model selection rules

**STALE — `PersonaSpec.model_tier`:** The field is **not** in `apis/brain/app/personas/spec.py`. Selection is driven by:

1. **Persona YAML** — `default_model`, `escalation_model`, `escalate_if`, `requires_tools`, `compliance_flagged` (see `PersonaPinnedRoute` and `registry.resolve_model`).
2. **No silent tier jump** — **STALE as “model_tier”** but intent holds: pinned persona uses `escalation_model` only when `escalate_if` matches; otherwise stays on `default_model`.
3. **Persona pin** — When the caller supplies a persona, the spec’s models and tool path override the classifier’s suggested model for that request.
4. **Chain: `extract_and_reason`** — **Partially STALE** — `prefer_chain` is not a PersonaSpec field. **`strategy=extract_reason`** (query param) selects `ExtractAndReason` in `agent.py` (two-hop: Flash extract → Sonnet). **STALE** — “CPA, QA only” is not enforced in code; any caller can pass the strategy if wired through.

---

## 3. Cost ceilings

**Implemented:** `PersonaSpec.daily_cost_ceiling_usd` — before a paid call, `agent.py` calls `cost_tracker.check_ceiling`; on exceed, return an error response (no silent upgrade).

**STALE (not found in `apis/brain` as named):**

- Per-call `PersonaSpec.max_cost_usd` with defaults $0.05 / $0.50
- `PersonaSpec.daily_cost_usd_cap` (name in older doc — actual field is `daily_cost_ceiling_usd`)
- Org-wide daily cap `BRAIN_ORG_DAILY_COST_USD_CAP` and “degrades to cheaper model first”

**Intended policy (when implemented):** A request that would breach a cap should **refuse or degrade explicitly** — never silently upgrade to a pricier model.

---

## 4. When chaining is justified

We chain (multiple LLM calls for one user-visible outcome) when:

- The first step is materially cheaper and produces **structured, validated** output for the second (see `ExtractAndReason` in `router.py`).
- **STALE** — “≥5×” rule: **not encoded** as a hard check; use judgment and cost estimates from `model_registry.json`.

We do **not** chain only to be thorough. One capable call often beats two mediocre ones on latency and total cost.

---

## 5. Caching

**STALE** — `BRAIN_LLM_CACHE_TTL_SECONDS` and per-user cache tags are **not found** in a quick `apis/brain` grep (2026-04-24). If in-memory or Redis caching is added, update this section with file paths.

**Intended policy:** No cross-user cache hits for sensitive content; any cache must be safe for the persona and org boundary.

---

## 6. Eval & golden suites

**STALE** — The prior text referenced `apis/brain/tests/golden/` and `brain-golden-suite.yaml`. **That path does not exist in this repo snapshot.** Tests exist under `apis/brain/tests/` (e.g. `test_golden_scenarios.py`).

**Intent:** Personas with compliance or routing complexity should have automated coverage so routing drift is caught in CI.

---

## 7. What we will NOT do

- We will **not** train models on user data, ever.
- We will **not** use a model that is not on the approved registry (`docs/AI_MODEL_REGISTRY.md` + `model_registry.json`) for production Brain paths.
- We will **not** add per-user “model pickers” that bypass the persona spec for customer-facing product surfaces. **STALE** — `gpt-5.3-codex-thinking-xhigh` style slugs in older text were examples of disallowed ad-hoc picks; the rule is about **governance**, not a specific model name.
- We will **not** let an LLM execute tools outside the persona’s allowed set (enforced in router/agent layers).
- We will **not** ship a raw ungoverned “chat to OpenAI” endpoint for end users; calls go through persona + policy.

---

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. **2026-04-24:** Crispness pass — aligned headings with `apis/brain` where verified; **STALE** markers for unimplemented or renamed fields. Append-only.

### Amendments

- **2026-04-24** — Reconciled with Brain `spec.py` / `router.py` / `agent.py`; marked aspirational subsections **STALE**.

---

## Appendix — prior subsections (retained, **STALE**)

The following is the pre-2026-04-24 body text, kept so nothing is “lost” in the archive. **Superseded** by numbered sections above where those sections are marked **STALE** or corrected. Do not treat this appendix as code-truth.

### Multi-vendor (original table)

| Class                               | Primary                 | Fallback                              |
|-------------------------------------|-------------------------|---------------------------------------|
| Reasoning (Sonnet-class)            | Anthropic Claude Sonnet | OpenAI GPT-5.5 medium                 |
| Cheap chat / classify (Haiku-class) | Anthropic Claude Haiku  | OpenAI GPT-5.5 mini / Composer-2-fast |
| Cheap extract / OCR                 | Google Gemini Flash     | Anthropic Claude Haiku                |
| Embeddings                          | OpenAI text-embedding-3 | Cohere                                |

If the primary is down, the fallback handles within 30 seconds (circuit breaker auto-trip in `app/services/router.py`). We do NOT add a 3rd vendor "just in case" — the maintenance tax is real.

### Model selection (original `model_tier` narrative)

The `PersonaSpec.model_tier` field gates model selection. Rules:

1. **Cheap by default.** New persona specs default to `model_tier=fast`. Only specs with explicit reasoning needs (CPA tax analysis, QA root-cause, engineering architectural reviews) request `tier=reasoning`.
2. **No silent upgrades.** A persona pinned to `tier=fast` may NEVER be auto-upgraded to `tier=reasoning` mid-conversation. If the persona spec needs reasoning, change the spec and ship a PR.
3. **Persona pin overrides classification.** When a caller pins a persona (slash commands, n8n workflows that know which employee they want), the persona's tier wins over the classifier's heuristic.
4. **Chain strategies are opt-in.** `extract_and_reason` (P3 two-hop) costs ~2x. It runs only when:
   - Caller explicitly passes `strategy=extract_reason`, OR
   - Persona spec has `prefer_chain=extract_and_reason` (currently CPA, QA only)

### Cost ceilings (original three items)

1. **Per-call cap** (`PersonaSpec.max_cost_usd`, default $0.05 for fast / $0.50 for reasoning) — call refuses when projected to exceed
2. **Per-day per-persona cap** (`PersonaSpec.daily_cost_usd_cap`) — persona returns a "daily ceiling reached, retry tomorrow or escalate" envelope
3. **Org-wide daily cap** (env `BRAIN_ORG_DAILY_COST_USD_CAP`) — when crossed, Brain enters cost-aware mode (see Brain Philosophy §3)

A request that would breach a cap **degrades to a cheaper model first**, then refuses. Never silently upgrade.

### Caching (original)

- Identical persona+prompt within `BRAIN_LLM_CACHE_TTL_SECONDS` (default 60s) returns the cached response. This is for retries, not for "cheap by repetition."
- Cached responses are tagged `cached=true` in the audit log. Cost ledger records $0 for the call.
- Cache is per-user, per-persona, per-model. No cross-user cache hits.

### Eval (original)

- Every persona ships with at least 3 golden test prompts in `apis/brain/tests/golden/`.
- The nightly golden suite (`brain-golden-suite.yaml`) runs them all under both primary and fallback vendors, with mocked LLM responses to catch routing/schema drift (NOT to evaluate model quality — that's a different exercise).
- A persona that fails golden 2 nights in a row gets auto-pinned to `tier=fast` until a human reviews. Better to be cheap-and-known than expensive-and-broken.

---
