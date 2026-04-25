---
owner: agent-ops
last_reviewed: 2026-04-24
doc_kind: generated
domain: brain
status: generated
---
<!-- GENERATED — do not edit by hand.
     Source: docs/axiomfolio/brain/axiomfolio_tools.yaml
     Regen:  python scripts/generate_axiomfolio_integration_doc.py
     CI:     .github/workflows/brain-personas-doc.yaml -->

# AxiomFolio ↔ Paperwork Brain integration

> This file is auto-generated. The hand-written predecessors (`AXIOMFOLIO_INTEGRATION.md`, `AXIOMFOLIO_HANDOFF.md`) were removed as part of Track M.4 after they fell out of sync with code. Everything authoritative now lives in the YAML source and the webhook router.

## Overview

Two directions, one contract:

* **Brain → AxiomFolio (tools)** — Paperwork Brain calls 12 HTTP tools on AxiomFolio (Tier 0: 7, Tier 2: 2, Tier 3: 3). These back the `trading` persona's tool-calling loop and also power the user-facing MCP surface for self-directed investors via Claude Desktop.
* **AxiomFolio → Brain (webhooks)** — AxiomFolio posts 10 event types to Brain's webhook receiver. High-importance events (`risk.gate.activated`, `approval.required`, `stop.triggered`) wake the `trading` persona and post a narrated explanation to `#trading` (Track M.2).

## Authentication

**Brain → AxiomFolio:** API key in `X-Webhook-Signature`, value from `AXIOMFOLIO_API_KEY` env var on the Brain side. All `/api/v1/tools/*` routes require this header.

**AxiomFolio → Brain:** HMAC-SHA256 of the raw body, sent as `X-Webhook-Signature: sha256=<hex>`. Shared secret in `BRAIN_WEBHOOK_SECRET` on AxiomFolio and `AXIOMFOLIO_WEBHOOK_SECRET` on Brain.

## Brain → AxiomFolio tool catalog

| Tool | Method | Path | Tier | Timeout | Description |
|---|---|---|---|---|---|
| `get_portfolio` | `GET` | `/api/v1/tools/portfolio` | 0 | 10s | Get user's portfolio summary with positions, P&L, and risk exposure |
| `get_market_regime` | `GET` | `/api/v1/tools/regime` | 0 | 5s | Get current market regime (R1-R5) and recommendation |
| `stage_analysis` | `GET` | `/api/v1/tools/stage/{symbol}` | 0 | 5s | Get Stage Analysis for a specific symbol |
| `run_scan` | `GET` | `/api/v1/tools/scan` | 0 | 15s | Run market scans and return candidates |
| `get_risk_status` | `GET` | `/api/v1/tools/risk` | 0 | 5s | Get circuit breaker status and risk metrics |
| `preview_trade` | `POST` | `/api/v1/tools/preview-trade` | 2 | 15s | Create a trade preview for user approval |
| `execute_trade` | `POST` | `/api/v1/tools/execute-trade` | 3 | 30s | Execute an approved trade order |
| `approve_trade` | `POST` | `/api/v1/tools/approve-trade` | 3 | 10s | Approve a pending trade order (owner only) |
| `reject_trade` | `POST` | `/api/v1/tools/reject-trade` | 3 | 10s | Reject a pending trade order |
| `list_schedules` | `GET` | `/api/v1/tools/schedules` | 0 | 5s | List all scheduled tasks from the job catalog with last run status |
| `run_task` | `POST` | `/api/v1/tools/run-task` | 2 | 10s | Trigger a catalog task to run immediately via Celery |
| `pending_approvals` | `GET` | `/api/v1/tools/pending-approvals` | 0 | 5s | List orders currently awaiting approval with timeout info |

### Tier meaning

* **Tier 0** — **Read-only.** No approval gate; tool runs immediately.
* **Tier 2** — **State-changing.** Requires agent autonomy level ≥ ``safe`` in AxiomFolio and enters the approval queue when autonomy is ``ask``.
* **Tier 3** — **Execution / financial.** Always enters the approval queue regardless of autonomy level. Owner-only approval routes available via the ``approve_trade`` / ``reject_trade`` tools.

## AxiomFolio → Brain webhook events

| Event | Description |
|---|---|
| `trade_executed` | Order filled by broker |
| `position_closed` | Position fully closed |
| `stop_triggered` | Stop loss triggered |
| `risk_gate_activated` | Circuit breaker or risk limit hit |
| `scan_alert` | New Breakout Elite/Standard candidates detected |
| `regime_change` | Market regime shifted (e.g. R2 to R3) |
| `exit_alert` | Exit cascade triggered for held positions |
| `approval_required` | Trade requires owner approval |
| `daily_digest` | Daily intelligence digest generated |
| `weekly_brief` | Weekly strategy brief generated |

### Events that wake the trading persona

The following events trigger a `#trading` Slack post narrated by the `trading` persona (default model: `claude-sonnet-4`). All others land as memory rows only.

* `risk.gate.activated` / `risk.alert`
* `approval.required` / `approval.needed`
* `stop.triggered`

See `apis/brain/app/routers/webhooks.py::_TRADING_WAKEUP_EVENTS` for the live list.

## LLM delegation (Track M.1)

When `AXIOMFOLIO_USE_PAPERWORK_BRAIN=True` and no BYOK key is configured for the caller, AxiomFolio's TradingAgent delegates its LLM turn to Paperwork Brain (`POST /brain/process?persona_pin=trading`) instead of calling OpenAI directly. Benefits:

* Single cost ledger — cost attributed to the `trading` persona ceiling.
* Persona tone, rate limits, PII scrubbing, and episode memory all apply.
* Brain's router picks the model (Sonnet, not gpt-4o-mini).

## BYOK surface (do not consolidate)

Paid-tier self-directed investors can set their own OpenAI/Anthropic key via `users.llm_provider_key_encrypted`. When a user has a valid BYOK key **and** their subscription tier is ≥ PRO, TradingAgent calls their provider directly — Brain is bypassed entirely. This path exists for privacy and quota isolation and must remain separate from the delegation shim.

See `apis/axiomfolio/app/services/agent/brain.py::TradingAgent._resolve_llm_target` for the resolution logic.

## User-facing MCP surface (do not consolidate)

`apis/axiomfolio/app/api/routes/mcp.py` exposes JSON-RPC at `/api/v1/mcp/jsonrpc` for self-directed investors to point Claude Desktop and similar clients at their own AxiomFolio account. This is a separate product surface — not part of the two-brain delegation flow — and must keep working unchanged.

## Provenance stamps

Every AxiomFolio `agent_actions` row that results from a delegated Brain turn is stamped with `metadata.brain_episode_uri = brain://episode/<id>`, tying the tool call back to the Brain exchange that produced it. Audit trails stay end-to-end even as the LLM step moves between products.

