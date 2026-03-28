# Paperwork Brain Integration Handoff

**Date**: 2026-03-27
**AxiomFolio PR**: #236 (Phase 6 - Brain Integration Foundation)
**Paperwork Branch**: `feat/phase-11-alpha-complete`

---

## What AxiomFolio Has Built

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

```
Header: X-Brain-Api-Key: <AXIOMFOLIO_API_KEY>
```

Set in AxiomFolio: `BRAIN_API_KEY=af_brain_xxx`
Set in Brain: `AXIOMFOLIO_API_KEY=af_brain_xxx`

### Webhook Events (AxiomFolio → Brain)

AxiomFolio sends POST to `{BRAIN_WEBHOOK_URL}/webhooks/axiomfolio`:

| Event | When |
|-------|------|
| `trade_executed` | Order filled by broker |
| `position_closed` | Position fully closed |
| `stop_triggered` | Stop loss hit |
| `risk_gate_activated` | Circuit breaker tripped |
| `scan_alert` | Scan finds candidates |
| `approval_required` | Tier 3 trade needs approval |

Payload:
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

Create endpoint `POST /webhooks/axiomfolio`:

```python
@router.post("/webhooks/axiomfolio")
async def axiomfolio_webhook(
    event: str,
    data: dict,
    user_id: Optional[int],
    timestamp: str,
    x_webhook_secret: str = Header(None),
):
    # Verify secret
    if x_webhook_secret != settings.AXIOMFOLIO_WEBHOOK_SECRET:
        raise HTTPException(401, "Invalid webhook secret")
    
    # Handle events
    if event == "approval_required":
        # Post to Slack with [Approve] [Reject] buttons
        await post_approval_request_to_slack(data)
    elif event == "trade_executed":
        # Store as episode in user's memory
        await remember_trade(user_id, data)
    # ... etc
```

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
BRAIN_WEBHOOK_SECRET=secret_here
BRAIN_TOOLS_USER_ID=1
TRADE_APPROVAL_MODE=all
TRADE_APPROVAL_THRESHOLD=5000
```

### Brain Side
```
AXIOMFOLIO_API_URL=https://api.axiomfolio.com
AXIOMFOLIO_API_KEY=af_brain_xxx
AXIOMFOLIO_WEBHOOK_SECRET=secret_here
```

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

---

## Questions?

Check:
- `docs/brain/axiomfolio_tools.yaml` for tool definitions
- `backend/api/routes/brain_tools.py` for endpoint implementation
- `backend/services/brain/webhook_client.py` for webhook details
- `backend/services/execution/approval_service.py` for approval logic
