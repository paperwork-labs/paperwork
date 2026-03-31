# Paperwork Brain Integration Handoff

**Date**: 2026-03-27
**AxiomFolio PR**: #236 (Phase 6 - Brain Integration Foundation)
**Paperwork Branch**: `feat/phase-11-alpha-complete`

---

## What AxiomFolio Has Built

---

### Internal Agent vs Brain Tools

AxiomFolio has two intelligence layers:

1. **Internal AgentBrain** (`backend/services/agent/brain.py`) — 55 tools for health remediation, interactive chat, and market analysis. Runs inside the AxiomFolio process. NOT exposed to Brain.

2. **Brain HTTP Tools** (`backend/api/routes/brain_tools.py`) — 9 curated endpoints that Paperwork Brain calls via MCP. These are the tools listed below.

The internal agent and Brain tools are completely independent codepaths. Adding a tool to one does NOT automatically register it in the other.

---

### Tool Endpoints (Ready for Brain to Call)

| Endpoint | Method | Tier | Description |
|----------|--------|------|-------------|
| `/api/v1/tools/portfolio` | GET | 0 | Portfolio summary with P&L, exposure |
| `/api/v1/tools/regime` | GET | 0 | Current market regime R1-R5 |
| `/api/v1/tools/stage/{symbol}` | GET | 0 | Stage Analysis for symbol |
| `/api/v1/tools/scan` | GET | 0 | Run scans, return candidates |
| `/api/v1/tools/risk` | GET | 0 | Circuit breaker status |
| `/api/v1/tools/preview-trade` | POST | 2 | Create PREVIEW order |
| `/api/v1/tools/execute-trade` | POST | 3 | Execute approved order |
| `/api/v1/tools/approve-trade` | POST | 3 | Approve pending order |
| `/api/v1/tools/reject-trade` | POST | 3 | Reject pending order |

### Authentication

**Tool API (Brain → AxiomFolio):**
```
Header: X-Brain-Api-Key: <AXIOMFOLIO_API_KEY>
```

**Webhooks (AxiomFolio → Brain) — HMAC-SHA256:**
```
Header: X-Webhook-Signature: sha256=<hex-encoded-hmac>
```

AxiomFolio signs the JSON request body with HMAC-SHA256 using `BRAIN_WEBHOOK_SECRET`:
```python
signature = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
headers["X-Webhook-Signature"] = f"sha256={signature}"
```

Brain verifies by recomputing the HMAC over the raw request body and comparing with `hmac.compare_digest`.

Set in AxiomFolio: `BRAIN_API_KEY=af_brain_xxx`, `BRAIN_WEBHOOK_SECRET=<shared_secret>`
Set in Brain: `AXIOMFOLIO_API_KEY=af_brain_xxx`, `AXIOMFOLIO_WEBHOOK_SECRET=<same_shared_secret>`

### Webhook Events (AxiomFolio → Brain)

AxiomFolio sends POST to `{BRAIN_WEBHOOK_URL}/api/v1/webhooks/axiomfolio`:

| Event | When |
|-------|------|
| `trade_executed` | Order filled by broker |
| `position_closed` | Position fully closed |
| `stop_triggered` | Stop loss hit |
| `risk_gate_activated` | Circuit breaker tripped |
| `scan_alert` | Scan finds candidates |
| `approval_required` | Tier 3 trade needs approval |

Payload (JSON body, signed with HMAC-SHA256):
```json
{
  "event": "trade_executed",
  "data": { "order_id": 123, "symbol": "AAPL", ... },
  "user_id": 1,
  "timestamp": "2026-03-27T14:30:00Z",
  "source": "axiomfolio"
}
```

### Tool Manifest

Located at: `docs/brain/axiomfolio_tools.yaml`

Copy to Brain's external tool registry or reference directly.

---

## What Brain Needs to Build

### 1. Register AxiomFolio as External Tool Provider

In `apis/brain/app/tools/external.py`:

```python
EXTERNAL_TOOL_PROVIDERS = {
    "axiomfolio": {
        "base_url": os.getenv("AXIOMFOLIO_API_URL", "http://localhost:8100"),
        "auth_header": "X-Brain-Api-Key",
        "auth_secret_env": "AXIOMFOLIO_API_KEY",
        "tools": [
            # Copy from docs/brain/axiomfolio_tools.yaml
        ]
    }
}
```

### 2. Webhook Handler

Endpoint `POST /api/v1/webhooks/axiomfolio` — **already implemented** in Brain.

Auth uses HMAC-SHA256 verification over the raw request body (see Authentication section above).

The handler stores events as episodic memory and should notify Slack for `approval_required` events.

### 3. Trading Persona

Create `personas/trading.mdc`:

```markdown
# Trading Persona

You are the trading intelligence within the Brain. Direct, data-driven, risk-aware.

## Available Tools
- get_portfolio: View positions and P&L
- stage_analysis: Check Stage Analysis for any symbol
- get_market_regime: Current market conditions
- run_scan: Find trading candidates
- preview_trade: Create trade for approval
- execute_trade: Execute approved trades

## Rules
- Never execute trades without explicit approval
- Always check circuit breaker before suggesting trades
- Explain Stage Analysis context for any recommendation
```

### 4. Slack Integration

In n8n workflow or Brain API:

1. Filter messages in `#trading` channel
2. Route to trading persona
3. For Tier 3 actions, post approval buttons
4. On button click, call `/tools/approve-trade` or `/tools/reject-trade`

---

## Environment Variables

### AxiomFolio Side
```
BRAIN_API_KEY=af_brain_xxx
BRAIN_WEBHOOK_URL=https://brain.paperworklabs.com
BRAIN_WEBHOOK_SECRET=<shared_secret_for_hmac>
BRAIN_TOOLS_USER_ID=1
TRADE_APPROVAL_MODE=all
TRADE_APPROVAL_THRESHOLD=5000
```

### Brain Side
```
AXIOMFOLIO_API_URL=https://api.axiomfolio.com
AXIOMFOLIO_API_KEY=af_brain_xxx
AXIOMFOLIO_WEBHOOK_SECRET=<same_shared_secret_for_hmac>
```

Note: `BRAIN_WEBHOOK_SECRET` (AxiomFolio) and `AXIOMFOLIO_WEBHOOK_SECRET` (Brain) must be the same value — this is the HMAC-SHA256 signing key for webhook payloads.

---

## Local Development

Both repos can run simultaneously:

| Service | Paperwork | AxiomFolio |
|---------|-----------|------------|
| Backend | 8000 | 8100 |
| Frontend | 3000 | 3100 |
| Postgres | 5432 | 5433 |
| Redis | 6379 | 6380 |

### Quick Test

```bash
# Start both stacks
cd ~/development/paperwork && make dev-d
cd ~/development/axiomfolio && make up

# Test tool endpoint
curl -H "X-Brain-Api-Key: af_brain_dev_key_change_in_prod" \
     http://localhost:8100/api/v1/tools/portfolio
```

---

## Approval Workflow

```
1. User (via Brain/Slack): "Buy 100 AAPL"

2. Brain validates → calls POST /tools/preview-trade
   → AxiomFolio creates order with status=PREVIEW
   → If approval required, changes to PENDING_APPROVAL
   → Webhooks Brain: {"event": "approval_required", ...}

3. Brain posts to Slack:
   "🔔 Trade Approval Required
    BUY 100 AAPL @ ~$185
    [Approve] [Reject]"

4. User clicks [Approve]
   → Brain calls POST /tools/approve-trade
   → AxiomFolio changes status to PREVIEW, sets approved_by

5. Brain calls POST /tools/execute-trade
   → AxiomFolio executes via broker
   → Webhooks Brain: {"event": "trade_executed", ...}

6. Brain posts confirmation:
   "✅ Filled: BUY 100 AAPL @ $184.95"
```

---

## Analyst Role

| Role | Permissions |
|------|-------------|
| `owner` | Full access, can approve/execute trades |
| `analyst` | Read access, can propose trades (needs owner approval) |
| `viewer` | Read-only access |

Analyst-proposed trades always require owner approval regardless of `TRADE_APPROVAL_MODE`.

Note: `approve-trade` and `reject-trade` endpoints bind to `BRAIN_TOOLS_USER_ID` server-side. Brain does not pass user IDs — the service identity is the approver/rejector.

---

## Job Cadence

All scheduling is driven by Celery Beat from `backend/tasks/job_catalog.py`. Render cron jobs have been retired.

| Job | Cron (UTC unless noted) | Group |
|-----|------------------------|-------|
| Nightly Coverage Pipeline | 0 1 * * * | market_data |
| Index Constituents Refresh | 30 0 * * * | market_data |
| Tracked Universe Cache Rebuild | 45 0 * * * | market_data |
| Audit Quality Refresh | 0 */2 * * * | market_data |
| 5-Minute Candle Backfill | 30 13-21 * * 1-5 | market_data |
| Regime Alert Monitor | */5 9-16 * * 1-5 (ET) | market_data |
| IBKR Daily Sync | 15 2 * * * | portfolio |
| Schwab Daily Sync | 30 2 * * * | portfolio |
| Recover Stale Syncs | */5 * * * * | portfolio |
| Monitor Open Orders | * * * * * | portfolio |
| IBKR Gateway Watchdog | */5 * * * * | portfolio |
| Reconcile Order Fills | */10 * * * * | portfolio |
| Evaluate Strategy Entry Rules | 0 2 * * 1-5 (ET) | strategy |
| Evaluate Exit Cascade | 30 2 * * 1-5 (ET) | strategy |
| Daily Intelligence Digest | 30 1 * * 1-5 (ET) | intelligence |
| Weekly Strategy Brief | 0 7 * * 1 (ET) | intelligence |
| Monthly Review | 0 8 1 * * (ET) | intelligence |
| Data Retention Cleanup | 30 4 * * * | maintenance |
| Recover Stale Job Runs | 0 */6 * * * | maintenance |
| Auto-Ops Health Remediation | */15 * * * * | maintenance |

---

## Questions?

Check:
- `docs/brain/axiomfolio_tools.yaml` for tool definitions
- `backend/api/routes/brain_tools.py` for endpoint implementation
- `backend/services/brain/webhook_client.py` for webhook details (HMAC-SHA256 signing)
- `backend/services/execution/approval_service.py` for approval logic
