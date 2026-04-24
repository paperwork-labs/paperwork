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
  - tokens>6000         # or inputs over this threshold
allowed_tools:
  - read_github_file
  - search_memory
compliance_flagged: true
confidence_floor: 0.8
daily_cost_ceiling_usd: 5.00
owner_channel: cpa
mode: chat
```

### Supported `escalate_if` tags

| Tag                | Meaning                                           |
| ------------------ | ------------------------------------------------- |
| `tools_required`   | Heuristic said the message needs tools.           |
| `compliance`       | Persona is `compliance_flagged: true`.            |
| `tokens>N`         | Input message exceeds ~N tokens.                  |
| `mention:<slug>`   | Message contains `<slug>` (case-insensitive).     |

Unknown tags fail validation at load time.

## Routing flow

`apis/brain/app/services/agent.py::process` does:

1. Route persona via `services/personas.route_persona`.
2. `get_spec(persona)` — spec or `None`.
3. If spec exists → `PersonaPinnedRoute` (skips Gemini Flash, saves a
   classifier call, respects escalation rules).
4. Otherwise → legacy `ClassifyAndRoute` (Gemini Flash).
5. Run LLM, check constitution, store episode.
6. **Stamp** `↪ source: brain://episode/<id>` on the response.

Any persona with a spec is therefore cheaper *and* more predictable
than the classifier-driven path.

## Provenance (D4)

Every response returns:

```json
{
  "response": "...\n\n_source: brain://episode/481_",
  "persona": "cpa",
  "persona_spec": "cpa",
  "model": "claude-sonnet-4-20250514",
  "episode_id": 481,
  "episode_uri": "brain://episode/481"
}
```

The `brain://episode/<id>` URI is the canonical pointer. Slack, Studio,
n8n and downstream consumers should surface it so any artifact can be
traced back to the exchange that produced it.

## Studio surface

- `GET /api/v1/admin/personas` (Brain) — lists specs.
- `/admin/agents` (Studio) — renders the registry at the top of the
  page. Shows default/escalation model, cost ceiling, escalation tags,
  compliance flag.

## Adding a persona

1. Write `.cursor/rules/<name>.mdc` (instructions).
2. Add `apis/brain/app/personas/specs/<name>.yaml` (contract).
3. `pytest apis/brain/tests/test_persona_specs.py -q`.
4. Deploy Brain. Studio picks it up automatically.

## What's next (Phase D2+)

- **D2** — Golden test suite replaying n8n history through Brain personas.
- **D3** — Move the registry to a Neon table so Studio can edit specs
  without a deploy.
- **D6** — `/admin/agents/run` operator UI for one-off persona calls.
- **D7** — Platform middleware enforcing `daily_cost_ceiling_usd`,
  rate limits, output caps, and PII stripping.
- **D8** — Migrate the 12 fat n8n workflows to persona calls.
