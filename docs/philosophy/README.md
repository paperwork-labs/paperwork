---
owner: agent-ops
last_reviewed: 2026-04-23
doc_kind: philosophy
domain: company
status: active
---

# Philosophy

This folder holds Paperwork Labs' **immutable rules** — the doctrines that constrain how every product, agent, and human operator behaves. They answer "what we will not do" and "what we will not change without a founder + persona-owner sign-off."

These docs are intentionally **low-churn, CODEOWNERS-locked**, and exempt from the 90-day freshness check that applies to architecture/runbook docs. If you find yourself wanting to change one, that's a sprint-level event.

| Domain | Architecture (mutable "how") | Philosophy (immutable "why / what we won't do") |
|---|---|---|
| company | [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) | [`docs/VENTURE_MASTER_PLAN.md`](../VENTURE_MASTER_PLAN.md) |
| brain | [`docs/BRAIN_ARCHITECTURE.md`](../BRAIN_ARCHITECTURE.md) | [`BRAIN_PHILOSOPHY.md`](./BRAIN_PHILOSOPHY.md) |
| infra | [`docs/INFRA.md`](../INFRA.md) | [`INFRA_PHILOSOPHY.md`](./INFRA_PHILOSOPHY.md) |
| data | [`docs/axiomfolio/MARKET_DATA.md`](../axiomfolio/MARKET_DATA.md) | [`DATA_PHILOSOPHY.md`](./DATA_PHILOSOPHY.md) |
| trading | [`docs/axiomfolio/TRADING.md`](../axiomfolio/TRADING.md) | [`docs/axiomfolio/TRADING_PRINCIPLES.md`](../axiomfolio/TRADING_PRINCIPLES.md) (product-local, indexed here) |
| tax / FileFree | _stub deferred — see PRD_ | [`TAX_PHILOSOPHY.md`](./TAX_PHILOSOPHY.md) |
| formation / LaunchFree | _stub deferred — see PRD_ | [`FORMATION_PHILOSOPHY.md`](./FORMATION_PHILOSOPHY.md) |
| personas | [`docs/BRAIN_PERSONAS.md`](../BRAIN_PERSONAS.md) | [`docs/GROUND_TRUTH.md`](../GROUND_TRUTH.md) (de-facto; explicit philosophy doc deferred) |
| automation | [`docs/DEPENDABOT.md`](../DEPENDABOT.md) + [`docs/BRAIN_PR_REVIEW.md`](../BRAIN_PR_REVIEW.md) | [`AUTOMATION_PHILOSOPHY.md`](./AUTOMATION_PHILOSOPHY.md) |
| design | [`docs/axiomfolio/DESIGN_SYSTEM.md`](../axiomfolio/DESIGN_SYSTEM.md) | _deferred — pending unified design system across Studio/AxiomFolio/FileFree_ |
| ai-models | [`docs/AI_MODEL_REGISTRY.md`](../AI_MODEL_REGISTRY.md) | [`AI_MODEL_PHILOSOPHY.md`](./AI_MODEL_PHILOSOPHY.md) |

## How to use these docs

1. **Persona authors** — when responding inside a domain, your output must not violate the matching philosophy. If a request asks you to violate one, refuse and surface the rule that conflicts.
2. **PR reviewers** (human or Brain) — flag any architecture change that contradicts a philosophy. Either the philosophy needs an explicit amendment (high bar) or the architecture change should be reshaped.
3. **CI** — `scripts/check_doc_freshness.py` exempts this folder. Stale-but-current is the design intent.
4. **Edits** — every change requires the founder + the domain owner persona on the PR (enforced by `CODEOWNERS`).

## What does NOT belong here

- Roadmaps, sprint goals, gap lists → `docs/sprints/` or product `plans/`
- Runbooks (operational steps that change with infra) → `docs/INFRA.md` or product `runbooks/`
- Architecture diagrams that update with code → `docs/ARCHITECTURE.md` or product `ARCHITECTURE.md`
- Decision logs (point-in-time choices) → `docs/KNOWLEDGE.md` (org) or `docs/axiomfolio/DECISIONS.md` (product)

## Lineage

Authored 2026-04-23 as part of the Docs Streamline 2026 Q2 (see [`docs/DOCS_STREAMLINE_2026Q2.md`](../DOCS_STREAMLINE_2026Q2.md)). Philosophy stubs were created from the L8 cross-cut audit's identified Architecture↔Philosophy gaps.
