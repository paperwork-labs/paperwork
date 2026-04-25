---
owner: agent-ops
last_reviewed: 2026-04-24
doc_kind: reference
domain: ai-models
status: active
---

# Paperwork Labs — AI Model Registry

**Companion (why / policy):** [`docs/philosophy/AI_MODEL_PHILOSOPHY.md`](philosophy/AI_MODEL_PHILOSOPHY.md)

## TL;DR

- **Tiers:** *cheap* — `gpt-4o-mini`, `gemini-2.5-flash`, `gemini-2.0-flash-exp` (ExtractAndReason only), `claude-haiku-4-5-20251001` (PR review default); *capable* — `claude-sonnet-4-20250514`, `gpt-4o`, `o4-mini`; *critical / escalation* — `claude-opus-4-20250618`.
- **Routing rule:** Pinned persona → `apis/brain/app/personas/specs/<persona>.yaml` (`default_model` / `escalation_model` + `escalate_if`). No pin → `ClassifyAndRoute` with Gemini Flash classification (`llm.classify_query` in `apis/brain/app/services/llm.py`). Optional `strategy=extract_reason` → `ExtractAndReason` (Flash extract → Sonnet) in `apis/brain/app/services/router.py`.
- **Latest review (2026-04-24):** Roster reconciled with `apis/brain/app/model_registry.json` and Brain code; rows below that are not in that JSON are called out inline. Persona→model table added from YAML.

**Owner**: AI Operations Lead (`agent-ops.mdc`)

**Code sources of truth:** `apis/brain/app/model_registry.json` (pricing + approved slugs for cost math), persona contracts `apis/brain/app/personas/specs/*.yaml`, router `apis/brain/app/services/router.py`, LLM execution `apis/brain/app/services/llm.py`.

This document is updated when model slugs or persona defaults change.

---

## Model Roster (Brain-approved slugs)

Pricing below matches `apis/brain/app/model_registry.json` (`2026-03-29`).

| # | Model slug | Input/1M | Output/1M | Context | Role |
|---|---|---:|---:|---:|---|
| 1 | `gemini-2.5-flash` | $0.075 | $0.30 | 1M | Classifier + cheap text (`llm` defaults) |
| 2 | `gpt-4o-mini` | $0.15 | $0.60 | 128K | Bulk text, many persona defaults |
| 3 | `o4-mini` | $1.10 | $4.40 | 200K | Tax / financial reasoning (`tax-domain` default) |
| 4 | `gpt-4o` | $2.50 | $10.00 | 128K | OpenAI MCP path, Anthropic fallback |
| 5 | `claude-sonnet-4-20250514` | $3.00 | $15.00 | 200K | Primary Sonnet — tools/MCP, most “serious” personas |
| 6 | `claude-opus-4-20250618` | $15.00 | $75.00 | 200K | Escalation model in specs — legal, CPA, QA, etc. |

<!-- MISSING IN REGISTRY: gemini-2.0-flash-exp used in apis/brain/app/services/router.py (ExtractAndReason.EXTRACTION_MODEL) -->
<!-- MISSING IN REGISTRY: claude-haiku-4-5-20251001 used in apis/brain/app/services/pr_review.py (DEFAULT_MODEL) -->

### Non-chat

| Slug | Role |
|---|---|
| `text-embedding-3-small` | Episode / memory embeddings (`apis/brain/app/services/embeddings.py`) |
| `mock` | No API keys — `llm.py` test path |

---

## STALE — Documented elsewhere or not in Brain `model_registry.json`

The following appeared in older registry versions or planning docs. They are **not** first-class rows in `model_registry.json` today. Do not assume pricing or routing without re-verifying.

| Name / claim | Notes |
|---|---|
| GPT-5.4, o3, Gemini 2.5 Pro | **STALE** — not in `model_registry.json` or Brain routing defaults in this repo snapshot. |
| “GPT-4o is the default” for Brain personas | **STALE** — many personas default to `claude-sonnet-4-20250514` or `gpt-4o-mini` per YAML; see Persona map below. |
| “n8n picks the model” as sole routing | **STALE** for Brain API — Brain uses persona YAML + `router.py` / `llm.py`. External n8n workflows may still use their own env vars (separate from this table). |
| “Composer-1 cheap tier” | **STALE** — not a Brain `model_registry.json` slug. |

---

## Persona → default model → escalation → cost

Source: `apis/brain/app/personas/specs/*.yaml`. **Override conditions** = `escalate_if` (see `resolve_model` in `apis/brain/app/personas/registry.py`). **Cost** = `daily_cost_ceiling_usd` (per-org daily, USD). **Per-call / monthly caps:** _TBD per persona spec_ (not in YAML today).

| Persona | default_model | escalation_model | Override (`escalate_if`) | Daily $ cap |
|---|---|---|---|---:|
| agent-ops | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `tokens>5000` | 5.0 |
| brand | `gpt-4o-mini` | `claude-sonnet-4-20250514` | `tokens>4000` | 2.0 |
| cfo | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `tokens>5000`, `mention:forecast` | 5.0 |
| cpa | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `compliance`, `tokens>6000` | 5.0 |
| ea | `gpt-4o-mini` | `claude-sonnet-4-20250514` | `tokens>4000` | 2.0 |
| engineering | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `tokens>8000`, `mention:architecture` | 10.0 |
| growth | `gpt-4o-mini` | `claude-sonnet-4-20250514` | `tokens>3000`, `mention:campaign` | 3.0 |
| infra-ops | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `compliance`, `tokens>6000`, `mention:outage`, `mention:incident` | 5.0 |
| legal | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `compliance`, `tokens>4000` | 4.0 |
| partnerships | `gpt-4o-mini` | `claude-sonnet-4-20250514` | `tokens>3000`, `mention:contract` | 3.0 |
| qa | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `compliance`, `mention:vulnerability`, `mention:exploit` | 5.0 |
| social | `gpt-4o-mini` | `claude-sonnet-4-20250514` | `tokens>3000` | 3.0 |
| strategy | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `tokens>6000`, `mention:quarterly` | 6.0 |
| tax-domain | `o4-mini` | `claude-sonnet-4-20250514` | `compliance` | 3.0 |
| trading | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | `tokens>5000`, `mention:execute`, `mention:live_order` | 6.0 |
| ux | `gpt-4o-mini` | `claude-sonnet-4-20250514` | `tokens>3500` | 3.0 |

**Per-persona** — monthly budget: _TBD per persona spec_ · per-call cap: _TBD per persona spec_ (not in `PersonaSpec` today; enforcement is `daily_cost_ceiling_usd` in `agent.py`).

---

## Deployed & external automations (n8n, other services)

| Area | Notes |
|---|---|
| n8n workflows | **STALE** — not re-verified 2026-04-24; see archived table below. |
| FileFree / Studio | See product env and routes; not re-verified in this pass. |
| Cursor IDE | Product guidance; not `model_registry.json`. |

### STALE — Archived “Model Roster” (pre-2026-04-24, 9 model rows)

**Do not use for pricing** — Brain `model_registry.json` only lists six chat slugs + routing defaults. Kept for history.

| # | Model | Input/1M | Output/1M | Context | Role |
|---|---|---:|---:|---:|---|
| 1 | GPT-4o-mini | $0.15 | $0.60 | 128K | The Intern — bulk extraction, classification, summaries |
| 2 | Gemini 2.5 Flash | $0.30 | $2.50 | 1M | The Workhorse — default for non-specialized tasks — **STALE** — pricing differed from `model_registry.json` |
| 3 | o4-mini | $1.10 | $4.40 | 200K | The Math Brain — tax/financial reasoning |
| 4 | Gemini 2.5 Pro | $1.25 | $10.00 | 1M | The Researcher — **STALE** — not in Brain `model_registry.json` |
| 5 | GPT-4o | $2.50 | $10.00 | 128K | The Creative Director — brand voice, marketing copy |
| 6 | GPT-5.4 | $2.50 | $15.00 | 1M | The Autonomous Agent — **STALE** — not in `model_registry.json` |
| 7 | Claude Sonnet 4.6 | $3.00 | $15.00 | 200K | The Senior Engineer — **STALE** — code uses `claude-sonnet-4-20250514` API id |
| 8 | Claude Opus 4.6 | $5.00 | $25.00 | 1M | The Principal Engineer — **STALE** — `model_registry.json` has different Opus $/1M |
| 9 | o3 | $10.00 | $40.00 | 200K | Nuclear Option — **STALE** — not in `model_registry.json` |

### STALE — Archived n8n workflow env mapping (unverified 2026-04-24)

| Workflow | Model | Expected Role | Deviation? | Env Var |
|---|---|---|---|---|
| agent-thread-handler | gpt-4o-mini | Intern | No | THREAD_HANDLER_MODEL |
| ea-daily | gpt-4o-mini | Intern | No | EA_DAILY_MODEL |
| ea-weekly | gpt-4o-mini | Intern | No | EA_WEEKLY_MODEL |
| sprint-kickoff | gpt-4o | Creative Director | No | SPRINT_KICKOFF_MODEL |
| sprint-close | gpt-4o | Creative Director | No | SPRINT_CLOSE_MODEL |
| pr-summary | gpt-4o-mini | Intern | No | PR_SUMMARY_MODEL |
| social-content-generator | gpt-4o | Creative Director | No — fixed 2026-03-18 (was gpt-4o-mini) | SOCIAL_CONTENT_MODEL |
| growth-content-writer | gpt-4o | Creative Director | No — fixed 2026-03-18 (was gpt-4o-mini) | GROWTH_CONTENT_MODEL |
| partnership-outreach-drafter | gpt-4o | Creative Director | No | PARTNERSHIP_MODEL |
| cpa-tax-review | gpt-4o | Creative Director | Yes — should be Claude Sonnet (compliance) | CPA_REVIEW_MODEL |
| qa-security-scan | gpt-4o | Creative Director | Yes — should be Claude Sonnet (code/security) | QA_SCAN_MODEL |
| weekly-strategy-checkin | gpt-4o | Creative Director | No | STRATEGY_MODEL |
| decision-logger | (no AI node) | N/A | N/A | N/A |

### STALE — Archived API / product snippets (unverified 2026-04-24)

| Endpoint / area | Model | Notes |
|---|---|---|
| FileFree advisory (`/api/advisory`) | gpt-4o (env: ADVISORY_MODEL) | **STALE** — verify in app code |
| FileFree OCR extraction | gpt-4o-mini | **STALE** — verify in app code |
| FileFree OCR fallback | gpt-4o (vision) | **STALE** — verify in app code |

### STALE — Archived Cursor session recommendations (product, not Brain slugs)

| Session Type | Recommended Model | Rationale |
|---|---|---|
| Strategy / architecture / deep reasoning | Claude Opus 4.6 | Quality delta for high-stakes — **STALE** — label/version may not match `model_registry` |
| Complex multi-file refactors | Claude Opus 4.6 | 1M context, SWE-bench claims — **STALE** |
| Routine coding / component building | Claude Sonnet 4.6 | **STALE** — match Cursor product names to API slugs in registry |
| Quick fixes / single-file edits | Fast model | **STALE** — vague |

---

## Activation / roadmap

| Model | Target Use | Blocked By | ETA |
|---|---|---|---|
| Claude Sonnet 4.6 | CPA Tax Review, QA Security Scan | Anthropic API key not configured in n8n | **STALE** — Brain paths use `claude-sonnet-4-20250514` today; n8n claim unverified |
| o4-mini | Tax calculation verification | Tax engine not yet built | Phase 2 — **STALE** — `o4-mini` is in `model_registry.json` for `tax-domain` |
| Gemini 2.5 Flash | State data extraction (LaunchFree) | LaunchFree not yet in development | Phase 3 — **STALE** — planning |
| GPT-5.4 | Trinket market discovery | Trinkets pipeline not yet built | Phase 1.5 — **STALE** — not in `model_registry.json` |
| Gemini 2.5 Pro | Competitive intel, SEO drafts | No current workflow needs it | Phase 5 — **STALE** |

**STALE** — Reconcile with `model_registry.json` and infra before treating ETAs as commitments.

---

## Decision tree (Quick reference)

1. Deterministic (code / rules)? → No chat model ($0).
2. Persona known? → Use persona YAML (`default_model` / `escalation_model` + `escalate_if`).
3. High-volume, simple text, no tools? → Often `gpt-4o-mini` or classifier-driven `gpt-4o-mini` / `o4-mini` (see classifier rules in `llm.classify_query`).
4. Tax math / structured financial reasoning? → `o4-mini` when tax-domain or classifier selects it.
5. Tool use / MCP? → `claude-sonnet-4-20250514` or `gpt-4o` per path (circuit breaker may swap).
6. Escalation in spec? → `claude-opus-4-20250618` when `escalate_if` matches.
7. `strategy=extract_reason`? → `gemini-2.0-flash-exp` extract → Sonnet (see `ExtractAndReason`).

---

## Monthly cost tracking

Fill from provider dashboards. Prefer the slugs in `model_registry.json` when aggregating.

| Month | Notes |
|---|---|
| Mar 2026 | Pre-revenue placeholder |
| Apr 2026 | |

### STALE — Archived wide cost grid (pre-2026-04-24)

| Month | GPT-4o-mini | Gemini Flash | o4-mini | Gemini Pro | GPT-4o | GPT-5.4 | Sonnet | Opus | o3 | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|
| Mar 2026 | -- | -- | -- | -- | -- | -- | -- | -- | -- | **Pre-revenue** |
| Apr 2026 | | | | | | | | | | |

**STALE** — Mixes models not all in current `model_registry.json`; Opus pricing was doc-only.

---

## Swap history

| Date | Old Model | New Model | Workflows Affected | Reason | Monthly Cost Impact |
|---|---|---|---|---|---|
| 2026-03-18 | gpt-4o-mini | gpt-4o | social-content-generator, growth-content-writer | Brand voice requires higher quality model | ~+$0.50/run |
| 2026-03-18 | gpt-4o-mini | gpt-4o | FileFree advisory route.ts | User-facing advisory quality | ~+$0.02/request |
| 2026-03-18 | gpt-4o | gpt-4o-mini | ea-daily, ea-weekly | Briefings don't need full gpt-4o; token limit fix | ~-$0.10/run |
| 2026-04-24 | (doc) | (doc) | — | Registry + philosophy pass; code-aligned roster | — |

**STALE** — Rows before 2026-04-24 are n8n/product swap log; not automatically Brain persona YAML.

---

## Model evaluation queue

| Model | Status | Notes |
|---|---|---|
| (none pending) | | |

When a new model releases, AI Ops Lead evaluates per `agent-ops.mdc`.

---

## Provider dashboards

- **OpenAI**: https://platform.openai.com/usage
- **Anthropic**: https://console.anthropic.com/settings/billing
- **Google Cloud**: https://console.cloud.google.com/billing

---

## Key constraints

- **Brand / marketing voice:** cheaper defaults often `gpt-4o-mini` in YAML; **STALE blanket rule** “never Claude for brand” — many brand-adjacent personas still escalate to **Sonnet** on token thresholds. Follow YAML.
- **Compliance:** compliance-flagged personas escalate per `escalate_if` + `compliance_flagged` — not “GPT for compliance.”
- **PII:** NEVER send SSNs or unmasked PII to any model.
- **Brain routing:** Classifier + persona pins live in `apis/brain` — not exclusively n8n.
- **STALE — “n8n is the implementation layer for all automated model routing”** — **false** for Brain API; n8n may still automate **separate** jobs with their own env config.

See `agent-ops.mdc` for workflow checklists. See [`AI_MODEL_PHILOSOPHY.md`](philosophy/AI_MODEL_PHILOSOPHY.md) for refusal and ceiling policy.

---

## Quality-First routing (from prior doc)

Use the best model for the task. **STALE — “Venture Master Plan Section 0E”** as sole authority — cross-check with `model_registry.json` and persona specs; routing code wins on conflicts.

Only downgrade when a cheaper model produces **equivalent quality** — not merely “good enough.” Cost optimization is by **tier and routing**, not by starving high-stakes personas.
