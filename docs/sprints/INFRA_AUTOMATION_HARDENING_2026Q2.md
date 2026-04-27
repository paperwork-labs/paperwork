---
owner: engineering
last_reviewed: 2026-04-23
doc_kind: sprint
domain: company
status: shipped
sprint:
  start: 2026-04-01
  end: 2026-04-23
  duration_weeks: 4
  pr: 141
  prs: [141]
  ships: [studio, brain, axiomfolio, n8n]
  personas: [agent-ops, engineering, infra-ops, qa]
  plans:
    - docs/INFRA.md
    - docs/BRAIN_ARCHITECTURE.md
    - docs/PERSONA_PLATFORM.md
---

# Infra & Automation Hardening — 2026 Q2

**Sprint window**: 2026-04-01 → 2026-04-23 (4 weeks)
**PR**: [#141 (squash-merged)](https://github.com/paperwork-labs/paperwork/pull/141)
**Result**: shipped

## Goal

Land the infrastructure and automation foundation Paperwork Labs needs before feature work resumes — persona platform, model selection, doc-vs-code truth checks, AxiomFolio brain delegation, and a Studio command center that stays honest about reality.

## Outcome

- Brain is now the single LLM gateway. n8n workflows shrink to webhook → Brain (`persona_pin=<slug>`) → Slack post. No model selection in n8n.
- Persona platform: typed `PersonaSpec` per persona, per-persona cost ceilings, rate limiting, golden suites in CI (4 lanes), nightly summary.
- Doc-vs-code truth check: `scripts/check_doc_code_refs.py` flags dead `file:line` references in docs. Baseline mode lets us iterate without churn.
- AxiomFolio's `TradingAgent` (renamed from `AgentBrain`) delegates LLM calls to Paperwork Brain via `persona_pin=trading`. BYOK preserved. New `/admin/agent/deep-analyze` endpoint demonstrates the `extract_reason` chain strategy (Flash extracts, Sonnet reasons).
- `packages/pwa` shared package: PWA manifest generation, install prompt, installability hook. Studio + AxiomFolio both consumers.
- n8n workflow DAGs: snapshotted via `scripts/snapshot_n8n_graphs.py` to a static JSON, rendered in `/admin/workflows`. Deterministic (content-hash, no timestamps) so CI doesn't flake.
- Studio: `/admin` overview now reflects real state (PRs, n8n executions, infra health), not stub cards. New `/admin/docs` hub with category navigation. New `/admin/architecture` system map.
- `docs/_index.yaml` taxonomy: every doc is categorized, owned, and rendered in the UI.

## Tracks

| Track | Lane | What shipped |
|---|---|---|
| F | Persona pinning | `persona_pin` request param; n8n bypasses keyword router |
| G | QA golden suites | 4 nightly suites, weekly QA report scheduler, CI matrix |
| K | Doc-vs-code refs | Auto-gen `BRAIN_PERSONAS.md`, `check_doc_code_refs.py` baseline + drift check |
| M | AxiomFolio Brain delegation | `paperwork_brain_client.py`, conditional delegation, BYOK preserved |
| N | Studio docs hub | `/admin/docs` + `_index.yaml` taxonomy, search |
| E | AxiomFolio Next.js scaffold | Vite app preserved; Next.js shell ready for Q3 cutover |
| Buffer Wk 4 | n8n DAG snapshot + chain strategies | `extract_reason` strategy, deep-analyze endpoint, deterministic snapshot |

## What we learned

- **Auto-generated docs need a `last_modified` per generator, not per filesystem mtime.** mtime drifts on rebase and CI. Generators now write a `content_hash` field that's stable across runs.
- **CI gates are only as good as their idempotence.** The n8n snapshot was failing every CI run because of an ISO timestamp; switched to content-hash and it's been silent since.
- **Persona pinning beats keyword routing** for any caller that already knows which employee to invoke. n8n was the obvious win; AxiomFolio is the second.
- **BYOK + delegation is a real architecture, not a hack.** AxiomFolio users can still bring their own keys; if they don't, AxiomFolio routes to Paperwork Brain. We track cost in one place either way.

## Follow-ups

- `/admin/tasks` (renders `docs/TASKS.md` as company tracker) — moving to follow-up sprint
- `/admin/products/<slug>/plan` per-product master plan views — moving to follow-up sprint
- `scripts/generate_tracker_index.py` to unify TASKS + sprints + plans + per-product PRDs into one JSON index — moving to follow-up sprint
- Friday CFO digest via Brain `persona_pin=cfo`
- `/sprint`, `/tasks`, `/plan <slug>` Slack slash commands

These ship in the next mini-sprint (`chore/docs-streamline-and-trackers` branch).

- **Shipped (2026-04-26):** Vercel auto-promote matrix expanded to include `axiomfolio-next`, `trinkets`, and `accounts` (placeholder `TBD_CREATE_BEFORE_MERGE` until Vercel projects are linked; skip-guard in workflow). See `.github/workflows/vercel-promote-on-merge.yaml` and `docs/infra/VERCEL_AUTO_PROMOTE.md`.
