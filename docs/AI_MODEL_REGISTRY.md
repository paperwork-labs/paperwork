---
owner: agent-ops
last_reviewed: 2026-04-25
doc_kind: reference
domain: ai-models
status: active
---

# AI model registry

This file is the single source of truth for which AI model serves which workflow at Paperwork Labs. Update it whenever routing, persona defaults, or n8n wiring change. **Authority for routing policy:** the AI Operations Lead rules in [`.cursor/rules/agent-ops.mdc`](../.cursor/rules/agent-ops.mdc) (use the **decision tree** below, not the legacy “Current Model Assignments (March 2026)” table in that file).

**Companion (policy, not model math):** [`docs/philosophy/AI_MODEL_PHILOSOPHY.md`](philosophy/AI_MODEL_PHILOSOPHY.md)

## Routing path

1. Inbound (Slack, n8n webhooks/cron, or other triggers) either posts to the Brain `POST /api/v1/brain/process` with optional `persona_pin`, or—only in a shrinking set of workflows—calls **OpenAI directly** via n8n `@n8n/n8n-nodes-langchain.openAi` with a hardcoded `modelId`.
2. The Brain service resolves [`apis/brain/app/personas/specs/*.yaml`](../apis/brain/app/personas/specs/) (PersonaSpec) plus classifier / router logic (`ClassifyAndRoute`, optional `strategy=extract_reason` paths) to choose a provider and model.
3. Approved slugs and math inputs live in [`apis/brain/app/model_registry.json`](../apis/brain/app/model_registry.json) for cost and capability checks.

**Track 2.1 (streamline sprint):** remaining n8n `langchain.openAi` jobs are expected to move onto Brain; until then, those runs bypass PersonaSpec and are marked below.

## Model routing decision tree (authoritative)

Use for **all new AI tasks** (per `agent-ops.mdc` — numbered 1–9, verbatim):

1. Can it be done deterministically (code/rules)? → No AI needed ($0)
2. Is it high-volume + simple (classification, extraction, summaries)? → GPT-4o-mini ($0.15/$0.60)
3. Does it need math/financial reasoning? → o4-mini ($1.10/$4.40)
4. Is it brand voice / creative copy? → GPT-4o ($2.50/$10)
5. Does it need autonomous web browsing? → GPT-5.4 ($2.50/$15)
6. Is it code generation or legal compliance? → Claude Sonnet 4.6 ($3/$15)
7. Default for everything else → Gemini 2.5 Flash ($0.30/$2.50)
8. Escalation only (>32K output, multi-hour sessions) → Claude Opus 4.6 ($5/$25)
9. Nuclear (complex multi-step reasoning) → o3 ($10/$40)

*Implementation note:* running Brain code maps API model IDs (e.g. `claude-sonnet-4-20250514`, `gemini-2.5-flash`, `o4-mini`) to these product tiers. When the decision tree names a “4.6” or “2.5 Flash” label, the deployed slug in PersonaSpec / `model_registry.json` is the source of truth.

## How the Brain service maps the tree to slugs (production code)

The decision tree is the **policy** layer; the repo uses explicit **API slugs** and helpers:

- **Unpinned / classify:** `llm` routing uses the classifier in [`apis/brain/app/services/llm.py`](../apis/brain/app/services/llm.py); the approved classifier slug in [`model_registry.json`](../apis/brain/app/model_registry.json) is `gemini-2.5-flash` (`routing_defaults.classifier`).
- **Persona present:** `resolve_model` in [`apis/brain/app/personas/registry.py`](../apis/brain/app/personas/registry.py) against each [`specs/*.yaml`](../apis/brain/app/personas/specs/) file.
- **Extract then reason:** `ExtractAndReason` in [`apis/brain/app/services/router.py`](../apis/brain/app/services/router.py) — extraction pass uses `gemini-2.0-flash-exp` (constant `EXTRACTION_MODEL`) before the main model completes.
- **Embeddings (episodes / memory):** [`apis/brain/app/services/embeddings.py`](../apis/brain/app/services/embeddings.py) calls OpenAI `text-embedding-3-small`.
- **PR review endpoint path:** [`apis/brain/app/services/pr_review.py`](../apis/brain/app/services/pr_review.py) uses `claude-haiku-4-5-20251001` by default and `claude-sonnet-4-20250514` for critical file prefixes or env override `BRAIN_PR_REVIEW_MODEL` (see `_choose_model`).

`mock` in tests and local no-key modes may stand in for live providers; never treat `mock` as production routing.

**n8n workflows in `infra/hetzner/workflows/` (active `*.json` glob, excluding `archive/` and `retired/`) with no LLM node:** `decision-logger`, `data-annual-update`, `data-source-monitor`, `data-deep-validator`, `error-notification`, `infra-status-slash` — determinism, HTTP, and Slack only; no registry row required unless an AI node is added. (Credential expiry, infra heartbeat, and infra health exports live under `retired/`; Brain runs those jobs in-process.)

## Deployed assignments

**Last verified:** 2026-04-26 (against `apis/brain/app/personas/specs/*.yaml` and `infra/hetzner/workflows/*.json`, excluding `archive/`, `retired/`, and `_reference/`). Cost band is a **rough** all-in guess per call (classifier + main completion + small overhead); true spend varies with tokens and escalations.

### Brain PersonaSpec (default → escalation on `escalate_if` match)

| Persona | Entry / trigger | Default model | Escalation model | Est. $ / run |
| --- | --- | --- | --- | --- |
| agent-ops | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| brand | Brain `process` | `gpt-4o-mini` | `claude-sonnet-4-20250514` | $0.01–0.10 |
| cfo | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| cpa | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| ea | Brain `process` | `gpt-4o-mini` | `claude-sonnet-4-20250514` | $0.01–0.10 |
| engineering | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.80 |
| growth | Brain `process` | `gpt-4o-mini` | `claude-sonnet-4-20250514` | $0.01–0.10 |
| infra-ops | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| legal | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| partnerships | Brain `process` | `gpt-4o-mini` | `claude-sonnet-4-20250514` | $0.01–0.10 |
| qa | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| social | Brain `process` | `gpt-4o-mini` | `claude-sonnet-4-20250514` | $0.01–0.10 |
| strategy | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| tax-domain | Brain `process` | `o4-mini` | `claude-sonnet-4-20250514` | $0.02–0.20 |
| trading | Brain `process` | `claude-sonnet-4-20250514` | `claude-opus-4-20250618` | $0.05–0.60 |
| ux | Brain `process` | `gpt-4o-mini` | `claude-sonnet-4-20250514` | $0.01–0.10 |

### n8n workflows (repo: `infra/hetzner/workflows/*.json`, active tree only)

| Persona or label | Workflow trigger | Model (today) | Est. $ / run |
| --- | --- | --- | --- |
| (classifier) | **Brain daily / weekly / PR** — `brain_daily_briefing`, `brain_weekly_briefing`, `pr_sweep` (replaces exports in `retired/`) | **Brain-routed** | $0.02–0.40 |
| (thread persona) | **Brain Slack Adapter** — Slack events → same API, thread context | **Brain-routed** (no pin; sticky / classify) | $0.02–0.50 |
| strategy | **Sprint kickoff** — schedule, `persona_pin: strategy` | **Brain-routed via `strategy` PersonaSpec** | $0.05–0.50 |
| strategy | **Weekly strategy** — `brain_weekly_strategy` (replaces `retired/weekly-strategy-checkin.json`) | **Brain-routed** (`strategy` persona) | $0.10–0.50 |
| cpa | **CPA tax review** — webhook, `persona_pin: cpa` | **Brain-routed via `cpa` PersonaSpec** | $0.05–0.60 |
| qa | **QA security scan** — webhook, `persona_pin: qa` | **Brain-routed via `qa` PersonaSpec** | $0.05–0.60 |
| — | **Sprint close** — Fri cron, `langchain.openAi` | **Direct OpenAI `gpt-4o` (Track 2.1 migration pending)** | $0.10–0.50 |
| — | **Social content generator** — webhook, `langchain.openAi` | **Direct OpenAI `gpt-4o` (Track 2.1 migration pending)** | $0.10–0.50 |
| — | **Growth content writer** — webhook, `langchain.openAi` | **Direct OpenAI `gpt-4o` (Track 2.1 migration pending)** | $0.10–0.50 |
| — | **Partnership outreach drafter** — webhook, `langchain.openAi` | **Direct OpenAI `gpt-4o` (Track 2.1 migration pending)** | $0.10–0.50 |

Other exported workflows in the same folder (e.g. decision logger, data monitors, infra health, credential checks) are **not LLM-backed**; they are omitted here.

*Known gap:* the decision tree **labels** (GPT-5.4, Gemini 2.5 Pro, Claude “4.6” marketing names) are not all mirrored as one-to-one `model_registry.json` slugs today. When a task requires a slug that is not in PersonaSpec + registry, the AI Ops lead must add it in code and registry first.

**Upcoming (planned, not current product):** See [`docs/sprints/STREAMLINE_SSO_DAGS_2026Q2.md`](sprints/STREAMLINE_SSO_DAGS_2026Q2.md) — remaining n8n direct-OpenAI nodes (e.g. sprint close, growth) should migrate onto Brain personas when touched.

## Provider dashboards

- **OpenAI (platform usage + keys):** https://platform.openai.com/usage — n8n direct-OpenAI workflows and any OpenAI-backed paths in the Brain stack.
- **Anthropic (console + billing):** https://console.anthropic.com/settings/billing — Claude Sonnet/Opus traffic from Brain.
- **Google Cloud (billing; Gemini):** https://console.cloud.google.com/billing — Classifier and other Gemini call paths.

## Non-negotiables (safety, from `agent-ops`)

- Never send SSNs, full account numbers, or other unmasked PII to any LLM.
- “Brand voice” and “compliance” routing follow **this registry + PersonaSpec** and the decision tree, not ad-hoc n8n defaults.

**n8n operational notes** (import paths, creds, env for non-Brain nodes): [infra/hetzner/workflows/README.md](../../infra/hetzner/workflows/README.md#model-configuration).

## Update protocol

- **Update this file** when: (1) a `default_model` / `escalation_model` or `escalate_if` change lands in a PersonaSpec; (2) a new n8n workflow is added that calls the Brain or OpenAI; (3) a `langchain.openAi` `modelId` is changed; (4) the agent-ops lead completes a model audit; (5) provider pricing or `model_registry.json` structure changes in a way that affects cost tables.
- **Code sources of truth:** `apis/brain/app/model_registry.json`, `apis/brain/app/personas/specs/`, and router/LLM services under `apis/brain/app/services/`.
- **Review:** any PR that touches the above should get `agent-ops` review; merge only after the Deployed assignments table reflects production intent.

See also: [`AGENTS.md`](../AGENTS.md) for org-wide agent context.
