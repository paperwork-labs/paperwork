---
owner: agent-ops
last_reviewed: 2026-04-24
doc_kind: philosophy
domain: brain
status: active
---

# Brain Philosophy

Immutable rules that constrain what the Paperwork Brain agent will and will not do, regardless of which persona, model, or caller is invoking it. Edits require founder + `agent-ops` persona ack.

- **(a) What Brain will refuse.** Licensed execution (filing, signing, moving money), trading that violates [`docs/axiomfolio/TRADING_PRINCIPLES.md`](../axiomfolio/TRADING_PRINCIPLES.md), unapproved PII export, and account creation on behalf of users — see §1.
- **(b) What makes a Brain action trustworthy.** Episodic memory stays **user- and org-scoped**; **PII** is scrubbed at the boundary (`apis/brain/app/services/pii.py`); **cost and compliance** are enforced via **typed persona contracts** (`apis/brain/app/personas/spec.py`, `apis/brain/app/services/cost_tracker.py`); **constitutional** checks run before return (`apis/brain/app/services/agent.py` + `apis/brain/constitution.yaml`). _(Trust model tightened with concrete paths; 2026-04-24.)_
- **(c) What needs founder sign-off.** Any change to **this document’s rules** (including new refusal triggers or relaxing an existing one), plus **paired** updates when **constitutional** logic in code changes — see **Lineage & versioning** below.

**For the how** — modules, routing, file paths, and error codes — see [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md). **For the who** (persona registry), see [`docs/BRAIN_PERSONAS.md`](../BRAIN_PERSONAS.md).

Brain is **not** a licensed professional, a broker, or an unfirewalled autopilot: it **drafts**, **explains**, and **stops** when a rule says so. _(Product positioning: “Not a chatbot. Not a financial advisor.” — moved from [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md) on 2026-04-24.)_

## 1. Refusal triggers (Brain MUST refuse)

Brain refuses, returns a structured refusal envelope, and routes to a human:

1. **Tax / legal advice that requires a license.** CPA / EA / legal personas can _draft_, but never _file_, send, or sign on behalf of a user without an explicit human approval step. EFIN-bound actions are gated by the `tax-domain` persona; `human_approved=true` is **target** behavior for EFIN paths. <!-- STALE 2026-04-24: `human_approved` not found in `apis/brain` codebase — wire-up pending. -->
2. **Trading orders that violate [`docs/axiomfolio/TRADING_PRINCIPLES.md`](../axiomfolio/TRADING_PRINCIPLES.md).** No leverage, no overnight-naked options unless the strategy spec explicitly approves it, no orders during a tripped breaker. The trading persona’s `submit_trade` tool must hard-fail on principle conflicts. <!-- STALE 2026-04-24: `submit_trade` not present in `apis/brain` — policy ahead of implementation. -->
3. **Money movement.** Brain never initiates ACH, wire, card, or crypto movement without a human-side confirmation handshake (e.g. Slack `:approved:` reaction from an owner-tier user). This includes broker fund transfers.
4. **PII export to an external system not in the approved sub-processor list.** See [`docs/axiomfolio/privacy.md`](../axiomfolio/privacy.md) and [`docs/SECRETS.md`](../SECRETS.md) for the list. Webhook `auto-post=true` to Slack does NOT count as export — Slack is on the list.
5. **Account creation in user-facing services** (broker, bank, IRS, state filing portal). Brain may _draft_ the application; the user must complete it.

## 2. Memory & privacy red lines

- Episodic memory in Postgres is **scoped per `user_id`**. Persona scratch memory shared across users is forbidden.
- Conversation embeddings may use cross-user corpora ONLY when stripped of PII via `apis/brain/app/services/pii.py` (and related scrub utilities). The scrubber is the boundary; bypassing it is a refusal trigger. _(Path updated from `app/services/pii_scrubber.py` on 2026-04-24; cross-user embedding pipeline must call the same boundary.)_
- Memory entries older than `BRAIN_MEMORY_TTL_DAYS` (default 365) are auto-purged. No "permanent" memory; if you want permanence write it to [`docs/KNOWLEDGE.md`](../KNOWLEDGE.md) or persona spec.
- Brain never logs raw API keys, broker credentials, or user passwords. Logging should use the PII scrub filter in `apis/brain/app/utils/pii_scrubber.py`. <!-- STALE 2026-04-24: CI does not yet assert `PIIScrubFilter` is installed on every logger — verify logging chain. -->

## 3. Cost & rate ceilings

- Every persona declares a **daily** ceiling in `PersonaSpec.daily_cost_ceiling_usd` (`apis/brain/app/personas/spec.py`), enforced in `apis/brain/app/services/cost_tracker.py` **before** provider spend. Optional **output** limits use `PersonaSpec.max_output_tokens` and rate limits use `PersonaSpec.requests_per_minute` where set. When a call would exceed policy limits, Brain MUST refuse or return a structured error — never silently “upgrade” spend. _(Replaces outdated `max_cost_usd` / `daily_cost_usd_cap` field names; 2026-04-24.)_
- The **`cfo`** persona owns the **narrative** for org spend in Slack (`apis/brain/app/schedulers/cfo_cost_dashboard.py` posts **≥80% of persona ceilings** to `#cfo`). <!-- STALE 2026-04-24: “Switch to cost-aware mode” (org-wide, automatic model gating) is not implemented in `agent.py` — today this is **reporting**, not automatic routing. -->
- The `extract_and_reason` chain strategy is **not** the default when `strategy` is omitted or `auto`: see `apis/brain/app/services/agent.py` (defaults to `PersonaPinnedRoute` when a spec exists, else `ClassifyAndRoute`). It runs when `strategy=extract_reason` is passed in or tests construct `ExtractAndReason` in `apis/brain/app/services/router.py`.

## 4. Human override

- Any persona output marked `requires_human_review=true` MUST be surfaced to Slack (`#agent-review` channel) with the original request, the proposed action, and a 24h timer. Auto-execution after timer is forbidden — silence is NOT consent. <!-- STALE 2026-04-24: confirm channel id wiring vs `#agent-review` in Brain + Studio. -->
- The `/escalate` slash command in any Slack channel forces the next Brain response to come from the `engineering` persona at Sonnet level, regardless of the original routing. <!-- STALE 2026-04-24: no `/escalate` handler found in `apis/brain` — policy ahead of implementation. -->

## 5. Constitutional checks

Every Brain response runs through a rule-based check in `apis/brain/app/services/agent.py` **BEFORE** returning, using allowlists loaded from `apis/brain/constitution.yaml` where applicable. The check has veto power. The check itself is updated through this philosophy doc — code changes to the check require a paired update here. _(Replaces reference to a non-existent `app/services/constitutional_check.py`; 2026-04-24.)_

The minimal check set is:

1. No financial advice without a licensed-professional disclaimer
2. No file-system writes outside the per-session sandbox
3. No outbound HTTP to non-allowlisted hosts
4. No tool calls that bypass the persona’s **routing contract** (e.g. `requires_tools: false` must not run MCP tool loops; tier tables in `docs/BRAIN_ARCHITECTURE.md` §D17) _(replaces `allowed_tools`, removed in H5; 2026-04-24)_

## 6. What we will NOT do

- We will **not** train models on user data beyond the user's own session.
- We will **not** ship a "Brain free tier" that has lower safety standards than the paid tier.
- We will **not** silently retry refused calls under a different persona to "get past" a refusal — the refusal is the answer.
- We will **not** let any single persona route to itself recursively more than `MAX_PERSONA_HOPS` (default 3). <!-- STALE 2026-04-24: `MAX_PERSONA_HOPS` not defined in `apis/brain` source — policy only. -->

## 7. Escalation triggers (auto-page humans)

Brain auto-pages the founder via Slack DM when any of the following happens:

| Trigger                                           | Channel         | Why                                                                                                                                   |
|---------------------------------------------------|-----------------|---------------------------------------------------------------------------------------------------------------------------------------|
| Constitutional check vetoes 3 calls in 60 minutes | DM              | something is asking us to do something we shouldn't                                                                                   |
| Daily cost > 90% cap                              | DM + `#qa`      | budget alarm <!-- STALE 2026-04-24: 90% org-wide cap paging not verified in `apis/brain` schedulers — may be product intent only. --> |
| AxiomFolio `risk_gate_activated` webhook          | DM + `#trading` | a real-money safety event                                                                                                             |
| Brain itself goes degraded (cb open > 5 min)      | DM + `#infra`   | self-monitor <!-- STALE 2026-04-24: wire-up with on-call + circuit metrics TBD. -->                                                   |

## Lineage & versioning

This doc is **append-only**. Edits require a numbered amendment block at the bottom with date, author, and rationale. The current doc represents the rules as of 2026-04-24.

### Amendments

1. **2026-04-24** (agent-ops / doc crispness pass): Added TL;DR, cross-links to `docs/BRAIN_ARCHITECTURE.md` + `docs/BRAIN_PERSONAS.md`, aligned `PersonaSpec` field names and file paths to `apis/brain/`, removed dead `app/services/constitutional_check.py` reference, replaced deprecated `allowed_tools` wording with `requires_tools` + tiering, and inserted `STALE` markers where policy leads code. Rationale: keep philosophy tethered to the repo; see [`docs/DOCS_STREAMLINE_2026Q2.md`](../DOCS_STREAMLINE_2026Q2.md).
