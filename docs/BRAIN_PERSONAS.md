# Brain Persona Platform

Typed contracts that govern how each Brain persona is routed, budgeted,
and held accountable.

## Why this exists

Before Phase D, every Brain request went through one generic classifier
(Gemini Flash) that picked a model and decided whether to enable tools.
That worked for a dozen personas, but as we migrate n8n workflows into
Brain we need:

- **Per-persona cost control.** CPA advice is worth Claude Sonnet;
  social captions are not.
- **Explicit escalation rules.** Compliance personas should never run on
  `gpt-4o-mini` — full stop — but social growth is fine there.
- **Auditable provenance.** Every Brain artifact should carry a URI
  pointing back to the episode that produced it.
- **A registry Studio can render.** Operators shouldn't have to grep
  `.mdc` files to know which persona exists and what it's allowed to do.

PersonaSpec answers all four.

## Anatomy

A spec lives at `apis/brain/app/personas/specs/<name>.yaml` and pairs
1:1 with the natural-language rules at `.cursor/rules/<name>.mdc`. The
`.mdc` is *what the persona sounds like*; the YAML is *what it's
allowed to do*.

```yaml
name: cpa
description: CPA — advisory-tier tax guidance with CPA firm context.
default_model: claude-sonnet-4-20250514
escalation_model: claude-opus-4-20250618
escalate_if:
  - compliance          # force escalation for compliance_flagged personas
  - tokens>6000         # or inputs over this threshold (tiktoken-counted)
requires_tools: false   # true = route through MCP; LLM can call tools
compliance_flagged: true
confidence_floor: 0.8
daily_cost_ceiling_usd: 5.00
owner_channel: cpa
mode: chat
```

### Supported `escalate_if` tags

| Tag                | Meaning                                           |
| ------------------ | ------------------------------------------------- |
| `compliance`       | Persona is `compliance_flagged: true`.            |
| `tokens>N`         | Input message exceeds N tokens (tiktoken count).  |
| `mention:<slug>`   | Message contains `<slug>` (case-insensitive).     |

Unknown tags fail validation at load time. CI also runs
`apis/brain/scripts/check_persona_coverage.py` to guarantee every
router-producible slug has a spec and every spec has an `.mdc`.

## Routing flow

`apis/brain/app/services/agent.py::process` does:

1. Route persona via `services/personas.route_persona`.
2. `get_spec(persona)` — spec or `None`.
3. **Enforce the daily cost ceiling** (H3). Redis-backed counter keyed
   `(organization_id, persona)`; if the cap is hit, return a structured
   `cost_ceiling_exceeded` error *before* spending anything with the
   provider.
4. Count input tokens with tiktoken (H6) — no more `len(msg)//4`
   heuristic for the `tokens>N` tag.
5. If spec exists → `PersonaPinnedRoute` (skips Gemini Flash, saves a
   classifier call, respects escalation rules, uses `requires_tools`
   to decide MCP-vs-text).
6. Otherwise → legacy `ClassifyAndRoute` (Gemini Flash).
7. Run LLM. If every provider fails → raise `LLMUnavailableError`; the
   agent returns a structured `llm_unavailable` error instead of silent
   mock content (H1).
8. Record actual spend against the daily counter.
9. For `compliance_flagged` personas with `confidence_floor` set,
   stamp `needs_human_review: true` on the episode metadata and return
   it in the response payload (H4). The actionable review queue lands
   in D7.
10. Check constitution, store episode with stamp.
11. Append `↪ source: brain://episode/<id>` to the response text.

Any persona with a spec is therefore cheaper *and* more predictable
than the classifier-driven path.

## Enforcement today vs later

| Spec field                | Today (Phase D H-pass)                        | Later                    |
| ------------------------- | --------------------------------------------- | ------------------------ |
| `default_model`           | Enforced — pinned route uses it               |                          |
| `escalation_model`        | Enforced — chosen when `escalate_if` fires    |                          |
| `escalate_if`             | Enforced                                      |                          |
| `requires_tools`          | Enforced — drives MCP vs text path            |                          |
| `daily_cost_ceiling_usd`  | **Enforced** (Redis CostTracker, fail-fast)   | D7: org-level roll-up    |
| `compliance_flagged`      | Drives escalation + `needs_human_review` flag |                          |
| `confidence_floor`        | Stamps episode + response metadata            | D7: blocking review gate |
| `owner_channel`           | Informational (Studio display)                | D7: auto-route to Slack  |
| `mode`                    | Informational                                 | D6: task-mode /run UI    |

If a spec field isn't enforced today, it isn't in the YAML. We don't
ship decorative contracts.

## Provenance (D4)

Every response returns:

```json
{
  "response": "...\n\n_source: brain://episode/481_",
  "persona": "cpa",
  "persona_spec": "cpa",
  "model": "claude-sonnet-4-20250514",
  "episode_id": 481,
  "episode_uri": "brain://episode/481",
  "needs_human_review": true,
  "error": null
}
```

The `brain://episode/<id>` URI is the canonical pointer. Slack, Studio,
n8n and downstream consumers should surface it so any artifact can be
traced back to the exchange that produced it.

## Structured error responses

| `error` code              | What happened                          | User-facing response                         |
| ------------------------- | -------------------------------------- | -------------------------------------------- |
| `cost_ceiling_exceeded`   | Daily cap hit for this (org, persona)  | "Persona has reached its daily spend cap..." |
| `llm_unavailable`         | Every provider failed (circuit open)   | "Brain is temporarily unable to reach..."    |

Both responses carry the persona and spec names so the caller can log
meaningful telemetry. Neither returns fake content.

## Studio surface

- `GET /api/v1/admin/personas` (Brain) — lists specs.
- `/admin/agents` (Studio) — renders the registry at the top of the
  page. Shows default/escalation model, cost ceiling, escalation tags,
  compliance flag, and a `tools` badge when `requires_tools: true`.

## Adding a persona

1. Write `.cursor/rules/<name>.mdc` (instructions).
2. Add `apis/brain/app/personas/specs/<name>.yaml` (contract).
3. Ensure `route_persona` can produce `<name>` (keyword list, channel
   map, or phrase list in `app/services/personas.py`).
4. Run `python apis/brain/scripts/check_persona_coverage.py` —
   CI enforces the same three-way invariant.
5. `pytest apis/brain/tests/test_persona_specs.py
   apis/brain/tests/test_persona_pinned_route.py -q`.
6. Deploy Brain. Studio picks it up automatically.

## What's next (Phase D2+)

- **D2** — Golden test suite replaying n8n history through Brain personas.
- **D3** — Move the registry to a Neon table so Studio can edit specs
  without a deploy.
- **D6** — `/admin/agents/run` operator UI for one-off persona calls.
- **D7** — Blocking review queue for `needs_human_review`, org-level
  cost roll-ups, rate limits, output caps, auto-routing to
  `owner_channel`.
- **D8** — Migrate the 12 fat n8n workflows to persona calls.
- **D9** — Re-introduce `allowed_tools` once D7 wires per-persona MCP
  tool filtering at the server level. (Removed in H5 to avoid
  declared-but-unenforced contracts.)
