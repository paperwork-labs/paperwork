---
owner: agent-ops
last_reviewed: 2026-04-23
doc_kind: plan
domain: automation
status: active
---
# Agent-Driven PR Automation — Plan Set

> **STATUS (2026-04-23): IMPLEMENTATION DIRECTION SUPERSEDED — PLANNING TRAIL PRESERVED.**
>
> After a strategic review on the Paperwork side, the implementation direction pivoted from a custom Cursor-BG-Agent dispatcher to a leaner **Path A**: GitHub Free + Hetzner self-hosted runner + [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action) for review + thin Brain glue (webhook → Slack → cross-PR memory). Same outcome (automated review, danger-zone gating, auto-merge, Slack-native ops) with ~200 lines of Brain code instead of ~1,500, ~$2/mo out-of-pocket instead of $7–20/mo, and zero custom orchestrator to maintain.
>
> **What stayed relevant from this plan set (and is being executed now):**
> - Phase 0 repo move (see [`00-repo-move.md`](./00-repo-move.md)) — done.
> - AxiomFolio-side danger-zone detection + `protected-regions.mdc` rule (see [`01-axiomfolio-side.md`](./01-axiomfolio-side.md)) — reused, now wired through branch protection + an auto-labeler workflow instead of a custom signing script.
> - Brain-side webhook receiver + iteration memory table (see [`02-paperwork-brain-side.md`](./02-paperwork-brain-side.md)) — kept, now scoped to ~200 lines (no dispatcher, no router, no prompt templates).
> - Slack-native approvals via existing `brain-slack-adapter` n8n workflow — kept.
> - `paperwork-agent` GitHub App — not needed for the simplified path (GitHub's native auto-merge replaces the custom merge bot).
>
> **Why preserved here:** the planning artifacts document the design exploration that produced the pivot (custom orchestrator → GitHub-native), including cost math, escalation ladders, and risk analysis. Read as historical planning trail, not current implementation spec. Current direction lives in `paperwork/docs/` (see §5.5 "Simplest PR automation" in the active Axiomfolio Brain Ship-Year plan).

---

Three companion plans that together describe **Phase 1 of "Brain as Dev OS"** — a hands-off PR review/fix/merge loop where Paperwork Brain orchestrates Cursor Background Agents and posts back to GitHub + Slack.

This work fills `draft_pr` / `merge_pr` / `update_doc` rows in [Brain v10 BRAIN_ARCHITECTURE D17 (Tool execution guardrails)](https://github.com/paperwork-labs/paperwork/blob/main/docs/BRAIN_ARCHITECTURE.md) that were specced but never built. It also realigns AxiomFolio to its declared position in BRAIN_ARCHITECTURE line 7: *"axiomfolio is a skill/capability within Brain"*.

## Read order

> **New here?** Start with [`HANDOFF.md`](./HANDOFF.md) — it's the single-document context dump (sequence of intent shifts, current state of both repos, decisions, full phase plan, risks, resume prompt).

| # | File | Repo | What it covers | Estimate |
|---|---|---|---|---|
| — | [HANDOFF.md](./HANDOFF.md) | meta | Full context dump for fresh-machine / fresh-chat resume. Read first. | — |
| 0 | [00-repo-move.md](./00-repo-move.md) | meta | Move `sankalp404/axiomfolio` → `paperwork-labs/axiomfolio`. Strategic prerequisite (org alignment). | 30-80 min |
| 1 | [01-axiomfolio-side.md](./01-axiomfolio-side.md) | this repo | Thin GHA triggers, agent prompt templates (`reviewer.md`, `fixer.md`, `security.md`), `paperwork-agent` GitHub App install, danger-zone check, iteration counter. | ~2 days |
| 2 | [02-paperwork-brain-side.md](./02-paperwork-brain-side.md) | `paperwork-labs/paperwork` | `/api/v1/webhooks/github` route, Cursor BG agent dispatcher, GitHub PR write tools, iteration state DB, Slack n8n adapter wiring. Includes v2-v4 dev-OS roadmap (Decision Logger, Daily Briefing, Sprint Sync, Persona Dispatch, Doc Drift, Incident Response). | ~5 days |

## Why split

Two repos, two execution surfaces. Each plan can be picked up, executed, and reviewed independently. The Brain plan ships first (so the webhook target exists); the AxiomFolio plan can land its files behind a feature flag (`AGENT_AUTOMATION_ENABLED=false`) and flip on once Brain is live.

## Tracking issues

- **AxiomFolio side**: see issue link added on PR
- **Brain side**: parallel issue opened in `paperwork-labs/paperwork`, cross-linked

## Decisions confirmed

| Decision | Value |
|---|---|
| Path | Path 2 (Brain orchestrates, GHA = thin trigger) |
| Repo destination | `paperwork-labs/axiomfolio` |
| Bot identity | GitHub App `paperwork-agent` (App ID + private key as secrets) |
| Default model | `composer-2-fast` on Cursor Ultra plan (included usage) |
| Escalation model | `gpt-5.4-medium` only for: Fixer iter ≥2, DANGER ZONE reviews, Security findings |
| Daily spend cap | $10/day hard kill, $5/day soft alert |
| Per-PR cap | $2 (label `agent-budget-low` lowers to $0.50) |
| Iteration cap | 3 fixer iterations → label `human-review-needed`, halt |
| Slack | via existing `brain-slack-adapter` n8n workflow on Hetzner |
| Migration story | None — Path 2 is the destination, no v1→v2 rewrite later |

## Out of scope (deferred to v2-v4)

See "v2-v4 Roadmap: Brain as Dev OS" section in [02-paperwork-brain-side.md](./02-paperwork-brain-side.md):

- v2: Decision Logger expansion (Brain auto-drafts `D###` entries to KNOWLEDGE.md)
- v3: Daily dev briefing (compiles 24h shipped + in-flight + blocked + sprint progress)
- v4: Cross-repo sprint sync (TASKS.md ↔ Brain memory ↔ TASKS.md)
- v5: Engineering persona dispatch (right `.mdc` persona per PR type)
- v6: Doc drift detection (Brain notices code-vs-doc gaps, drafts updates)
- v7: Incident response (production health drop → triage agent → Slack diagnosis → fix PR draft)
