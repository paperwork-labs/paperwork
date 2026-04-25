---
owner: agent-ops
last_reviewed: 2026-04-23
doc_kind: philosophy
domain: ai-models
status: active
---

# AI Model Philosophy

Immutable rules for choosing, chaining, and budgeting LLM calls. Edits require founder + `agent-ops` persona ack, plus `cfo` persona ack for any cost-cap change.

Companion: [`docs/AI_MODEL_REGISTRY.md`](../AI_MODEL_REGISTRY.md) (mutable "which models, what tier, what cost").

## 1. Multi-vendor mandatory

We always have a working code path for at least 2 vendors per model class:

| Class | Primary | Fallback |
|---|---|---|
| Reasoning (Sonnet-class) | Anthropic Claude Sonnet | OpenAI GPT-5.5 medium |
| Cheap chat / classify (Haiku-class) | Anthropic Claude Haiku | OpenAI GPT-5.5 mini / Composer-2-fast |
| Cheap extract / OCR | Google Gemini Flash | Anthropic Claude Haiku |
| Embeddings | OpenAI text-embedding-3 | Cohere |

If the primary is down, the fallback handles within 30 seconds (circuit breaker auto-trip in `app/services/router.py`). We do NOT add a 3rd vendor "just in case" — the maintenance tax is real.

## 2. Model selection rules

The `PersonaSpec.model_tier` field gates model selection. Rules:

1. **Cheap by default.** New persona specs default to `model_tier=fast`. Only specs with explicit reasoning needs (CPA tax analysis, QA root-cause, engineering architectural reviews) request `tier=reasoning`.
2. **No silent upgrades.** A persona pinned to `tier=fast` may NEVER be auto-upgraded to `tier=reasoning` mid-conversation. If the persona spec needs reasoning, change the spec and ship a PR.
3. **Persona pin overrides classification.** When a caller pins a persona (slash commands, n8n workflows that know which employee they want), the persona's tier wins over the classifier's heuristic.
4. **Chain strategies are opt-in.** `extract_and_reason` (P3 two-hop) costs ~2x. It runs only when:
   - Caller explicitly passes `strategy=extract_reason`, OR
   - Persona spec has `prefer_chain=extract_and_reason` (currently CPA, QA only)

## 3. Cost ceilings

Every call has THREE ceilings that all must pass:

1. **Per-call cap** (`PersonaSpec.max_cost_usd`, default $0.05 for fast / $0.50 for reasoning) — call refuses when projected to exceed
2. **Per-day per-persona cap** (`PersonaSpec.daily_cost_usd_cap`) — persona returns a "daily ceiling reached, retry tomorrow or escalate" envelope
3. **Org-wide daily cap** (env `BRAIN_ORG_DAILY_COST_USD_CAP`) — when crossed, Brain enters cost-aware mode (see Brain Philosophy §3)

A request that would breach a cap **degrades to a cheaper model first**, then refuses. Never silently upgrade.

## 4. When chaining is justified

We chain models (run multiple LLM calls in one user-facing response) ONLY when:

- The first call is materially cheaper (≥ 5x) than the second
- The first call's output is structured and validated before feeding the second
- The total cost is still within the persona's per-call cap

We do NOT chain "just to be thorough." A single Sonnet call beats Haiku→Sonnet for most reasoning tasks because the chain doubles latency and cost without clear quality gains.

## 5. Caching

- Identical persona+prompt within `BRAIN_LLM_CACHE_TTL_SECONDS` (default 60s) returns the cached response. This is for retries, not for "cheap by repetition."
- Cached responses are tagged `cached=true` in the audit log. Cost ledger records $0 for the call.
- Cache is per-user, per-persona, per-model. No cross-user cache hits.

## 6. Eval & golden suites

- Every persona ships with at least 3 golden test prompts in `apis/brain/tests/golden/`.
- The nightly golden suite (`brain-golden-suite.yaml`) runs them all under both primary and fallback vendors, with mocked LLM responses to catch routing/schema drift (NOT to evaluate model quality — that's a different exercise).
- A persona that fails golden 2 nights in a row gets auto-pinned to `tier=fast` until a human reviews. Better to be cheap-and-known than expensive-and-broken.

## 7. What we will NOT do

- We will **not** train models on user data, ever.
- We will **not** use a model that is not on the approved registry.
- We will **not** add per-user "model preferences" that let users pick `gpt-5.3-codex-thinking-xhigh` because they want fancier output. The persona spec decides.
- We will **not** let an LLM call execute a tool that wasn't pre-allowlisted in the persona's `allowed_tools`. The router enforces this; bypassing it is a refusal trigger.
- We will **not** ship a "raw chat" endpoint to the user that bypasses persona routing. Every user-facing LLM call goes through a persona spec.

## Lineage & amendments

Authored 2026-04-23 as part of Docs Streamline 2026 Q2. Append-only.

### Amendments

_None yet._
