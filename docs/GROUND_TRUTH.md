---
owner: qa
last_reviewed: 2026-04-24
doc_kind: audit
domain: personas
status: active
---
# Ground truth

**Owner**: `qa` persona (Track K)
**Cadence**: weekly, appended only (never rewritten), diff posted to `#qa`.
**Baseline**: 2026-04-24 (Week 0 of the Infra Hardening Sprint).

## What this file is

A single, dated, verifiable registry of claims about Paperwork Labs' system.
Everything here is a tagged claim: `{id, claim, added_by, added_at, verified_at, verification_command}`.

Rules:

- **Append-only.** Never edit prior claims in place. Supersede with a new dated entry.
- **Every claim has a verification command** that should exit 0 when the claim holds.
- **Other docs reference ground-truth anchors** (`see GROUND_TRUTH#R-042`) rather than restating facts that can drift.
- **Brain authors claims** via `/brain/process?persona_pin=qa` when it makes a decision worth pinning.

## R-001 — We are a monorepo as of 2026-04

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Claim**: All paperwork-labs code lives in `github.com/paperwork-labs/paperwork`. The formerly separate repos `sankalp404/axiomfolio`, `paperwork-labs/filefree`, `paperwork-labs/launchfree`, `paperwork-labs/distill` have been merged into this monorepo and archived.
- **Verification**: `ls apis/axiomfolio apps/axiomfolio apis/filefree apps/filefree apps/launchfree apps/distill`
- **Consequence**: Docs referring to "across our repos" or "paperwork-labs/axiomfolio" as a live remote are **stale** and must be rewritten. Track K flags these weekly.

## R-002 — PR automation home is Brain, not GitHub Actions

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Status**: **pending** — target by end of Week 1 Track B.
- **Claim**: Dependabot PR triage, non-dependency PR review, and auto-merge gating all run inside Paperwork Brain (APScheduler + GitHub webhook handler). The GH Actions workflows `auto-merge-sweep.yaml`, `dependabot-major-triage.yaml`, `dependabot-auto-approve.yaml` are deleted once Brain has been green for 48h of parallel operation.
- **Verification**: `grep -r "auto-merge" .github/workflows/ | wc -l` should be `0`; Brain `/admin/pr-queue` returns active queue.

## R-003 — Studio is the single command center; no local portal

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Claim**: `apps/studio` (deployed at `paperworklabs.com/admin`) is the single operator UI. The legacy `portal/index.html` is deleted. Individual apps (3001/3002/…) are not accessed directly during ops; everything funnels through Studio.
- **Verification**: `test ! -e portal/index.html`

## R-004 — Brain is the only place LLM calls are routed

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Status**: **partially true** — n8n workflows still hardcode `gpt-4o` in 3 places; AxiomFolio's AgentBrain still hardcodes `gpt-4o-mini`. Target: Week 2 Track F + Week 3 Tracks H/M eliminate.
- **Claim**: Every LLM call in Paperwork Labs goes through `POST /brain/process`, with model selection delegated to Brain's `ClassifyAndRoute` chain and optionally overridden by `persona_pin=<slug>`. No app or workflow hardcodes a model.
- **Verification**: `rg -n '"gpt-4o|"gpt-4o-mini|anthropic/|claude-3-5' apis/ apps/ infra/hetzner/workflows/ --type-add json:*.json --type-add py:*.py -tpy -tts -ttsx -tjson | grep -v apis/brain/ | grep -v tests/ | wc -l` should equal `0` (only Brain itself names models).

## R-005 — Medallion architecture: every backend, four layers

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Updated**: 2026-04-24 (Track D lift)
- **Claim**: bronze → silver → gold → execution. Ledgers are append-only (Iron Law #1). `scripts/medallion/check_imports.py` is parametric over `--app-dir` and runs against axiomfolio, brain, filefree, and launchfree via the `medallion-lint` workflow on every PR. Per-app maps live in `scripts/medallion/apps.yaml`. `apis/axiomfolio/scripts/medallion/*` are shims that forward to the root scripts for backward compatibility.
- **Verification**: `python3 scripts/medallion/check_imports.py --app-dir apis/axiomfolio` (or brain/filefree/launchfree)

## R-006 — GDrive is served over MCP from Brain, not a standalone service

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Claim**: Google Drive access is exposed as MCP tools from Paperwork Brain. Studio's "GDrive" row on `/admin/ops` should probe Brain's `/api/v1/admin/tools` registry, not report hardcoded status. (Fixed in PR #138, 2026-04-24.)
- **Verification**: `curl -s -H "X-Brain-Secret: $BRAIN_API_SECRET" "$BRAIN_API_URL/api/v1/admin/tools" | jq '.data.tools[] | select(.name | test("gdrive|google.*drive"; "i"))'` returns a tool.

## R-007 — Slack bot is installed cluster-wide; Brain can post/reply in any channel

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Claim**: The paperwork bot is a member of every Slack channel. Brain can DM and post to any channel. Slack health has a probe row on `/admin/infrastructure` (added in Week 0 Track J follow-up).
- **Verification**: `@paperwork status` in `#deployment` responds via `brain-slack-adapter.json` within 10s, with a persona avatar (not a generic bot name).

## R-008 — 16 personas in the router; 48 `.mdc` files (16 personas + 32 guardrail rules)

- **Added by**: `qa` (baseline)
- **Updated**: 2026-04-24 (Track F H11/H12)
- **Status**: **partially reconciled** — router slugs now match PersonaSpec YAMLs 1:1 (brand + infra-ops added). The remaining 32 .mdc files are intentional *rules*, not personas (git-workflow, token-efficiency, no-silent-fallback, trading sub-personas like alpha-researcher/portfolio-manager, etc). `scripts/check_persona_coverage.py` is green.
- **Claim**: Persona routing lives in `apis/brain/app/personas/routing.py` (moved from `app/services/personas.py`, which is now a deprecation shim). Each router slug has a matching `app/personas/specs/<slug>.yaml` PersonaSpec **and** a `.cursor/rules/<slug>.mdc` instruction file. The image bundles all .mdc files at `/app/cursor-rules/` so cold starts don't hit GitHub.
- **Verification**: `ls .cursor/rules/*.mdc | wc -l` (expect `48`); `.venv/bin/python apis/brain/scripts/check_persona_coverage.py` (expect `OK: 16 router slugs, 16 specs, 48 mdc files (32 guardrail rules + 16 personas)`).

## R-009 — AxiomFolio has its own agent; it delegates LLM to Paperwork Brain

- **Added by**: `qa` (baseline)
- **Added at**: 2026-04-24
- **Status**: **pending** — target: Week 3 Track M.
- **Claim**: AxiomFolio's in-product agent (renamed `TradingAgent` from `AgentBrain`) delegates model invocation to Paperwork Brain via `persona_pin=trading`. AxiomFolio keeps approval-queue UX, BYOK, and tier gating local. Paperwork Brain owns model routing, cost tracking, and episodic memory.
- **Verification**: `grep -r "MODEL = " apis/axiomfolio/app/services/agent/` should find no hardcoded model strings.

---

## Audit baseline (2026-04-24)

First run of `scripts/check_doc_refs.py`:

- **Files scanned**: 99
- **Total refs**: 1,588
- **Broken refs**: 1,250
- **Stale-language hits**: 60

### Top 10 broken-ref offenders

| count | file |
|---:|---|
| 104 | `docs/axiomfolio/ARCHITECTURE.md` |
| 88 | `docs/axiomfolio/plans/UX_AUDIT_2026Q2.md` |
| 82 | `docs/axiomfolio/plans/MEDALLION_AUDIT_2026Q2.md` |
| 75 | `docs/axiomfolio/KNOWLEDGE.md` |
| 74 | `docs/axiomfolio/plans/WAVE_F_TRADING_PARITY.md` |
| 74 | `docs/axiomfolio/specs/v1-phase-3-execution-spec.md` |
| 61 | `docs/axiomfolio/PORTFOLIO.md` |
| 56 | `docs/axiomfolio/plans/PLAID_FIDELITY_401K.md` |
| 52 | `docs/axiomfolio/plans/PLATFORM_REVIEW_2026Q2.md` |
| 48 | `docs/archive/TASKS-ARCHIVE.md` |

Root cause: these docs were authored when `axiomfolio` was a standalone repo and their paths were relative to that repo's root (e.g. `src/agents/brain.ts`). Now that axiomfolio lives under `apis/axiomfolio/` and `apps/axiomfolio/`, the paths 404.

### Remediation plan

- **Track M (Week 3)** includes a sweep to rewrite axiomfolio doc paths, owned by `engineering`.
- **Track K (ongoing)** runs this script weekly; regressions posted to `#qa`.
- **docs/archive/\*** is exempt — archived docs are permitted to be stale, they're historical record.
- CI gate introduced in Week 2 Track N alongside the Studio Docs hub: `python3 scripts/check_doc_refs.py --strict --paths docs/philosophy/` (immutable philosophy docs must never break).

### Commands

```bash
# Human-readable audit
python3 scripts/check_doc_refs.py

# Machine-readable dump for Brain / #qa weekly report
python3 scripts/check_doc_refs.py --json /tmp/doc-audit.json

# Strict mode (use in CI for the philosophy docs only, not the whole tree)
python3 scripts/check_doc_refs.py --strict --paths docs/philosophy/
```
