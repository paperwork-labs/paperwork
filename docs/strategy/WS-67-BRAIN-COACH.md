---
last_reviewed: 2026-05-01
---

# WS-67 — Brain coach for Opus

> Status: design (2026-04-28). Implementation will be split into sub-PRs.

## North-star pitch

Brain is not just an L5 self-improving system. **Brain is the operating intelligence that wraps every agent action** — pre-flight, in-action, post-action — with context, memory, and learning.

Today (without WS-67):
- Procedural rules sit in YAML — Brain reads them on retro, but Opus doesn't consult them before acting.
- Recurring failures (path bug, missing medallion tag, ruff format, cost-bleed) repeat because the lessons live in Brain's data dir, not in Opus's working memory.
- The founder catches things Brain should be catching ("you auto-merged 399", "Vercel is at 91%").

After WS-67:
- Opus consults Brain before any non-trivial dispatch or merge. Brain returns matched rules, recent incidents, and predicted cost.
- Brain auto-distills repeated failure signatures into new procedural rules during weekly retro — no manual rule-writing needed.
- The founder's job shifts from "catch bugs" to "set objectives + accept/reject Brain's proposed rules".

## Layered architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Founder (objectives, audits)                    │
└─────────────────────────────────────────────────────────────────────┘
                                  ↑
┌─────────────────────────────────────────────────────────────────────┐
│  Pre-action layer (NEW — WS-67)                                      │
│    • coach/preflight: matched rules + recent incidents + cost predict│
│    • coach/plan-critique: Brain reviews a written plan               │
│    • coach/conflict-radar: in-flight agents touching same files      │
└─────────────────────────────────────────────────────────────────────┘
                                  ↕
┌─────────────────────────────────────────────────────────────────────┐
│  Opus (orchestrator)                                                 │
│    • Dispatches cheap-agents                                         │
│    • Reviews diffs (mandatory, doctrine)                             │
│    • Clicks merge button                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  ↕
┌─────────────────────────────────────────────────────────────────────┐
│  Cheap-agents (executors)                                            │
│    • Implement, write tests, push, rebase                            │
└─────────────────────────────────────────────────────────────────────┘
                                  ↕
┌─────────────────────────────────────────────────────────────────────┐
│  Post-action layer (EXISTS — WS-62, WS-64)                           │
│    • PR outcomes (h1, h24, lagging)                                  │
│    • Weekly retros                                                   │
│    • Self-prioritization                                             │
└─────────────────────────────────────────────────────────────────────┘
                                  ↕
┌─────────────────────────────────────────────────────────────────────┐
│  Knowledge graph (FOUNDATION — WS-65 + extensions in WS-67)          │
│    • procedural_memory.yaml (exists)                                 │
│    • incidents.json (exists)                                         │
│    • pr_outcomes.json (exists)                                       │
│    • workstreams.json (exists)                                       │
│    • agent_dispatch_log.json (exists)                                │
│    • NEW: rule_applications.json (which rule fired on which action)  │
│    • NEW: failure_signatures.json (clustered failure root-causes)    │
└─────────────────────────────────────────────────────────────────────┘
```

## Sub-workstreams

### WS-67.A — `coach/preflight` endpoint (foundation, ship first)

**API:**
```
POST /api/v1/admin/coach/preflight
{
  "action_type": "dispatch" | "merge" | "plan" | "deploy",
  "files_touched": ["<repo path>", "..."],
  "personas": ["cpa", "cfo"],
  "branch": "feat/ws-XX-foo",
  "pr_number": 123,
  "pr_path_globs": ["apis/brain/**", "apps/studio/**"]
}

→ 200 {
  "matched_rules": [
    {
      "id": "brain_data_dir_traverses_three_levels",
      "confidence": "high",
      "do": "...",
      "rationale": "files_touched contains apis/brain/app/services/* — this rule applies"
    }
  ],
  "recent_incidents": [
    {
      "incident_id": "INC-2026-04-29-vercel-cost-bleed",
      "severity": "high",
      "root_cause": "vercel_monorepo_must_use_turbo_ignore violated",
      "lesson": "..."
    }
  ],
  "predicted_cost": {
    "vercel_builds_likely": 8,
    "vercel_build_min_estimate": 24,
    "agent_compute_estimate_usd": 0.15
  },
  "warnings": [
    "files_touched includes apis/brain/app/schedulers/__init__.py — append-only convention"
  ]
}
```

**Matching algorithm:**
- Path-glob match: rules with `applies_to` listing relevant personas, plus rules whose `when` clause references touched paths.
- Recency match: incidents from last 30 days where the resolved root-cause shares files with `files_touched`.
- Cost estimate: query Vercel API for projected builds based on which `apps/*` directories the file list maps to (uses turbo's affected-graph after WS-68 lands).

**Storage:** no new files; reads from `procedural_memory.yaml` + `incidents.json` + `pr_outcomes.json`.

**Effort:** 1 PR, ~400 LOC, ships in 4 hours of cheap-agent time.

---

### WS-67.B — Cursor rule wiring Opus to coach

A Cursor rule under `.cursor/rules/` (filename TBD when shipped) — globally loaded:

> Before dispatching any non-trivial cheap-agent OR merging any PR with > 50 LOC, you MUST call `POST /api/v1/admin/coach/preflight` with the action signals. Surface the matched rules to the founder if any are `confidence: high` AND the action conflicts with a `do` clause. Abort and ask if a rule says "must" and the action violates it.

**Effort:** 1 PR, just rule + tiny brain-mcp doc tweak.

---

### WS-67.C — Plan critique tool

When Opus drafts a plan (multi-step, multi-PR), Brain reviews it before execution. Returns:
- Files the plan will touch that have recent incidents
- Procedural rules that conflict with the plan
- Suggested re-ordering (e.g., "you plan to dispatch X then Y, but X depends on Y")
- Cost predict aggregate

**API:**
```
POST /api/v1/admin/coach/plan-critique
{
  "plan_text": "...",
  "estimated_prs": 6,
  "estimated_workstreams": ["WS-67.A", "WS-67.B"]
}

→ 200 { issues: [...], suggestions: [...], cost_predict: {...} }
```

**Effort:** 1 PR, ~300 LOC. Uses an LLM call internally (low-cost — `gpt-5.5-medium` or local `composer-1.5`).

---

### WS-67.D — Conflict radar (in-flight agents)

Brain tracks active agent dispatches via `agent_dispatch_log.json`. When Opus is about to dispatch agent N, coach checks: "agent K is already touching files A, B — your dispatch will conflict if it touches the same."

**Output included in `coach/preflight` response under `conflict_radar`.**

**Effort:** subset of WS-67.A.

---

### WS-67.E — Auto-distillation (weekly retro extension)

Extend `apis/brain/app/services/self_improvement.py`:
- Cluster recent incidents + PR-outcome failures by root-cause regex (e.g., "FileNotFoundError" + "apis/brain/app/data/" → path bug cluster).
- If cluster has ≥3 occurrences in last 14 days, propose a new procedural rule via PR (Brain self-merges this when in graduated tier per WS-44).
- Flag for founder review if confidence < high.

**Effort:** 1 PR, ~250 LOC extending existing service.

---

### WS-67.F — Brain MCP server (longer term)

Today: Studio + Opus call Brain via HTTP. Cheap-agents do not have direct Brain access.

After WS-67.F: Brain exposes an MCP server (alongside the FastAPI backend) so any agent (Opus, cheap-agents, Studio, GitHub Actions) can query the knowledge graph or call coach endpoints. Mounted at `/mcp` on `brain.paperworklabs.com`.

**Effort:** 1 medium PR, ~600 LOC. Defers to after .A-.E are stable.

---

### WS-67.G — Conversational coaching (longer term)

`POST /api/v1/admin/coach/ask` with free-text questions:
- "Why did PR #401 fail?"
- "Should I merge X before Y?"
- "What's the cheapest way to do Z?"

Returns LLM-synthesised answer grounded in KG. Low priority — the structured endpoints (.A, .C) cover 80% of value.

---

## Failure modes & mitigations

| Failure | Mitigation |
|---|---|
| Brain mis-fires a rule, Opus aborts a legitimate action | Rules require explicit `confidence: high` to be blocking. Lower confidence = warning only. |
| Brain becomes a single point of failure (down → blocks Opus) | Coach returns gracefully with `{matched_rules: [], degraded: true}` if any data source unavailable. Opus proceeds. |
| Rule corpus grows too noisy (50+ rules, all match every action) | Add `applies_to_signals` precise matching + a confidence-decay where rules with `last_fired > 90 days ago` get downgraded. |
| Auto-distillation proposes bad rules | Founder must approve `confidence: high` rules; lower confidence rules go in but get reviewed in weekly retro. |
| Cheap-agents bypass the coach (don't call it) | Coach call wrapped in the agent dispatch helper; cheap-agents inherit it from the orchestrator scaffold. |

## Acceptance criteria

L4 acceptance:
- [ ] WS-67.A endpoint live with ≥6 procedural rules being matched on real PRs.
- [ ] WS-67.B Cursor rule loaded — Opus measurably consults coach for ≥80% of non-trivial dispatches (via `agent_dispatch_log.json` "preflight_consulted" field).
- [ ] WS-67.E auto-distills its first new rule within 30 days of launch.

L5 acceptance:
- [ ] WS-67.C plan-critique used on at least 1 plan before execution.
- [ ] Brain proposes ≥1 new rule per month via auto-distillation that founder approves.
- [ ] Recurring failures (same root-cause-cluster ≥3 times in 30 days) drop to <1 per quarter.

## Order of operations

1. **Now**: WS-67.A (`coach/preflight` endpoint) — foundation.
2. **Next**: WS-67.B (Cursor rule) — wires Opus.
3. **Then**: WS-67.E (auto-distillation) — closes the learning loop.
4. **Later**: WS-67.C (plan-critique), WS-67.D (conflict radar — subset of .A).
5. **Eventually**: WS-67.F (MCP server), WS-67.G (conversational).
