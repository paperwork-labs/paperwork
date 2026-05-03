# PR T-Shirt Sizing System

> Canonical reference for Paperwork Labs agent dispatch cost discipline.
> Enforced at hook layer (`.cursor/hooks/enforce-cheap-agent-model.sh`), tracked in DB (`agent_dispatches` table), surfaced in Studio UI (`/admin/cost`).

## Why This Exists

The Opus orchestrator was dispatching subagents without specifying a `model:` parameter, defaulting to expensive models. A single wave consumed ~$30 on Opus subagents that should have cost ~$2 on cheap dispatches. **Wave L makes violations impossible** — the hook blocks non-compliant dispatches at tool-call time, before any tokens are burned.

**The three-layer enforcement stack:**

1. **Hook layer** (`.cursor/hooks/enforce-cheap-agent-model.sh`) — blocks at dispatch time, `failClosed`
2. **DB layer** (`agent_dispatches` table) — every dispatch recorded with `t_shirt_size` + `model_used`; Opus-as-subagent rows are rejected by CHECK constraint
3. **UI layer** (`/admin/cost` Studio page) — real-time visibility into spend by size, workstream, and day

## The Taxonomy (locked)

| Size | Model slug | Est cost/dispatch | Use case |
|------|-----------|-------------------|----------|
| XS | `composer-1.5` | $0.05–0.15 | Narrow scaffold, generator, README stub |
| S | `composer-2-fast` | $0.20–0.60 | Single-file extraction, mechanical refactor |
| M | `gpt-5.5-medium` | $0.50–1.50 | Moderate cross-file, simple multi-step |
| L | `claude-4.6-sonnet-medium-thinking` | $1–5 | Cross-file reasoning, security-sensitive |
| XL | (Opus models) | **FORBIDDEN** | Orchestrator only, never as subagent |

**Bijection invariant:** size ↔ model slug is a 1-to-1 mapping. The hook and DB CHECK constraints enforce this. You can derive `t_shirt_size` from `model_used` deterministically.

### Model → Size mapping (in code)

```python
MODEL_TO_SIZE = {
    "composer-1.5":                      "XS",
    "composer-2-fast":                   "S",
    "gpt-5.5-medium":                    "M",
    "claude-4.6-sonnet-medium-thinking": "L",
}
# Any slug containing "opus" → XL (forbidden as subagent)
```

### Estimated costs (in cents, used for `estimated_cost_cents`)

```python
SIZE_COST_CENTS = {
    "XS": 10,   # $0.10 midpoint
    "S":  40,   # $0.40 midpoint
    "M":  100,  # $1.00 midpoint
    "L":  300,  # $3.00 midpoint
    "XL": 0,    # never set from subagent path
}
```

## Sizing Decision Tree

```
Is this a narrow, single-concern task?
  ├── YES: Does it touch ≤ 1 file?
  │     ├── YES: Is it pure scaffolding/generation (YAML, README, boilerplate)?
  │     │     └── YES → XS (composer-1.5, ~$0.10)
  │     └── YES: Is it mechanical (rename, extract, format)?
  │           └── YES → S (composer-2-fast, ~$0.40)
  └── NO: Does it touch 2–5 files with moderate reasoning?
        ├── YES: No security or compliance implications?
        │     └── YES → M (gpt-5.5-medium, ~$1.00)
        └── NO: Is it cross-file reasoning, security-sensitive, or architecture-touching?
              └── YES → L (claude-4.6-sonnet-medium-thinking, ~$3.00)

Is it the orchestrator itself (not a subagent)?
  └── → XL (Opus) — orchestrator only, NEVER dispatch as Task subagent
```

**Escalation rule:** When in doubt, step UP one size. Never step down and compromise quality. The cost delta between M and L is ~$2 — that's worth the correctness guarantee.

## Real Dispatch Examples

### XS — Wave K6 money-package scaffold
```
Task(
  model="composer-1.5",
  prompt="Create packages/money/src/index.ts with currency formatting utils from spec..."
)
```
Single new file, pure generation from spec. $0.08 actual.

### S — Wave K3 single-file extraction
```
Task(
  model="composer-2-fast",
  prompt="Extract formatCurrency() from packages/ui/src/utils.ts into packages/money/..."
)
```
One-to-two file mechanical move with test update. $0.35 actual.

### M — Wave K wave-k-billing-page
```
Task(
  model="gpt-5.5-medium",
  prompt="Add billing page to Studio: fetch from /v1/costs/summary, render chart..."
)
```
3-file UI feature, no security implications. $0.90 actual.

### L — Wave A initial architecture
```
Task(
  model="claude-4.6-sonnet-medium-thinking",
  prompt="Implement Alembic migration chain, SQLAlchemy base, and async session factory..."
)
```
Cross-file reasoning, database schema, security-relevant. $3.20 actual.

### L — Wave K3 security-sensitive auth middleware
```
Task(
  model="claude-4.6-sonnet-medium-thinking",
  prompt="Add HMAC-based BRAIN_INTERNAL_TOKEN middleware to protect /v1/admin/* routes..."
)
```
Security-sensitive, cross-file (main.py + middleware + tests). $2.80 actual.

## Cost Calibration Methodology

### Phase 1 (current): Estimated costs from midpoint heuristics

Estimates in `SIZE_COST_CENTS` are midpoints of the taxonomy range. Used for `estimated_cost_cents` at dispatch time.

### Phase 2 (post-launch): Actual billing reconciliation

Monthly calibration job reads `agent_dispatches` rows where `actual_cost_cents IS NULL AND completed_at < NOW() - INTERVAL '24 hours'` and cross-references:

- **Anthropic Console** → export usage CSV by date + model → match to `dispatched_at + model_used`
- **OpenAI Usage API** → `/v1/usage` endpoint, filter by model slug, aggregate by day
- **Cursor billing API** (if exposed by Cursor) → per-session cost breakdown

Calibration writes `actual_cost_cents` back to the row. The `/admin/cost` page shows the calibration delta ratio (`estimated / actual`) per size — green if within 20%, red if >50% off.

### Recalibration triggers

- Monthly: automated job (see `apis/brain/app/schedulers/cost_calibration_scheduler.py`)
- After any new model is added to the allow-list: immediate manual calibration
- After any major provider pricing change: immediate manual calibration

## TODOs for Full Calibration Integration

- [ ] **Anthropic Console export** — download monthly CSV, parse with `cost_calibration.py`, match to `agent_dispatches` rows by `dispatched_at` and `model_used`
- [ ] **OpenAI Usage API** — implement `/v1/usage` polling in `cost_calibration.py`
- [ ] **Cursor billing API** — pending Cursor exposing a billing endpoint; file feature request
- [ ] **Automated monthly job** — `apis/brain/app/schedulers/cost_calibration_scheduler.py` stub promoted to full implementation
- [ ] **Calibration dashboard** — extend `/admin/cost` with calibration delta tab once actual costs flow

## Links

- **Enforcement hook:** `.cursor/hooks/enforce-cheap-agent-model.sh`
- **Hook docs:** `.cursor/hooks/README.md`
- **Doctrine:** `.cursor/rules/cheap-agent-fleet.mdc` Rule #2
- **DB schema:** `apis/brain/alembic/versions/014_agent_dispatches.py`
- **SQLAlchemy model:** `apis/brain/app/models/agent_dispatch.py`
- **API router:** `apis/brain/app/routers/agent_dispatches.py`
- **Studio cost page:** `apps/studio/src/app/admin/cost/page.tsx`
- **Architecture:** `docs/BRAIN_ARCHITECTURE.md`
