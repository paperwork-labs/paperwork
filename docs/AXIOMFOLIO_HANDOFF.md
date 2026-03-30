# AxiomFolio ↔ Brain Integration Handoff

This document describes how to connect AxiomFolio to the Paperwork Labs Brain for AI-powered trading assistance.

## Overview

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   AxiomFolio    │◄────►│     Brain       │◄────►│     Slack       │
│  Trading Bot    │      │  AI Orchestrator│      │  Human Control  │
└─────────────────┘      └─────────────────┘      └─────────────────┘
       │                         │
       │  webhooks               │  MCP tools
       ▼                         ▼
  Events (scans,            Actions (scan,
  approvals, stops)          approve, reject)
```

**Brain URL**: `https://brain.paperworklabs.com`

## 1. Environment Variables

### In AxiomFolio (.env)

```bash
# Brain connection
BRAIN_API_URL=https://brain.paperworklabs.com
BRAIN_API_KEY=<get from Paperwork vault>
BRAIN_WEBHOOK_SECRET=<shared secret for signature verification>

# Which events to notify Brain about
BRAIN_NOTIFY_EVENTS=approval.required,risk.gate.activated,scan.alert,stop.triggered,position.closed
```

### In Brain (Render dashboard)

```bash
# AxiomFolio connection
AXIOMFOLIO_API_URL=https://axiomfolio.com   # or your deployment URL
AXIOMFOLIO_API_KEY=<AxiomFolio-generated key>
AXIOMFOLIO_WEBHOOK_SECRET=<same shared secret>
```

## 2. Webhook Events (AxiomFolio → Brain)

AxiomFolio notifies Brain of trading events via POST to:

```
POST https://brain.paperworklabs.com/api/v1/webhooks/axiomfolio
Authorization: Bearer <AXIOMFOLIO_WEBHOOK_SECRET signature>
Content-Type: application/json
```

### Event: `approval.required`

Sent when a trade needs human approval (Tier 3 classification).

```json
{
  "event": "approval.required",
  "timestamp": "2026-03-30T08:00:00Z",
  "data": {
    "order_id": "ord_abc123",
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 100,
    "reason": "Position size exceeds risk threshold"
  }
}
```

### Event: `risk.gate.activated`

Sent when a risk gate blocks a trade.

```json
{
  "event": "risk.gate.activated",
  "timestamp": "2026-03-30T08:00:00Z",
  "data": {
    "gate_name": "max_position_size",
    "blocked_action": "buy 500 TSLA",
    "threshold": "10% portfolio",
    "current_value": "15%"
  }
}
```

### Event: `scan.alert`

Sent when a market scan finds actionable opportunities.

```json
{
  "event": "scan.alert",
  "timestamp": "2026-03-30T08:00:00Z",
  "data": {
    "scan_name": "momentum_breakout",
    "results": [
      {"symbol": "NVDA", "score": 0.92, "signal": "buy"},
      {"symbol": "AMD", "score": 0.87, "signal": "buy"}
    ]
  }
}
```

### Event: `stop.triggered`

Sent when a stop-loss or take-profit triggers.

```json
{
  "event": "stop.triggered",
  "timestamp": "2026-03-30T08:00:00Z",
  "data": {
    "symbol": "TSLA",
    "stop_type": "stop_loss",
    "trigger_price": 245.00,
    "exit_price": 244.50,
    "pnl_percent": -2.5
  }
}
```

### Event: `position.closed`

Sent when a position is fully closed.

```json
{
  "event": "position.closed",
  "timestamp": "2026-03-30T08:00:00Z",
  "data": {
    "symbol": "GOOGL",
    "side": "sell",
    "quantity": 50,
    "exit_price": 178.25,
    "pnl_percent": 5.2
  }
}
```

## 3. MCP Tools (Brain → AxiomFolio)

Brain can call AxiomFolio actions via MCP tools. All requests use:

```
Authorization: X-Brain-Api-Key <AXIOMFOLIO_API_KEY>
Content-Type: application/json
```

### `scan_market`

Run a market scan strategy.

```http
POST /api/v1/tools/scan
{
  "strategy": "momentum_breakout",
  "params": {"min_volume": 1000000}
}
```

### `preview_trade`

Create a pending trade for review (does NOT execute).

```http
POST /api/v1/tools/preview
{
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 100,
  "order_type": "limit",
  "limit_price": 185.00
}
```

Response:

```json
{
  "order_id": "ord_abc123",
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 100,
  "estimated_cost": 18500.00,
  "risk_check": "passed",
  "expires_at": "2026-03-30T09:00:00Z"
}
```

### `approve_trade`

Approve a previously previewed trade (executes it).

```http
POST /api/v1/tools/approve
{
  "order_id": "ord_abc123"
}
```

### `reject_trade`

Reject a pending trade.

```http
POST /api/v1/tools/reject
{
  "order_id": "ord_abc123",
  "reason": "Market conditions changed"
}
```

### `get_portfolio`

Get current portfolio state.

```http
GET /api/v1/tools/portfolio
```

### `get_market_regime`

Get current market regime classification.

```http
GET /api/v1/tools/regime
```

## 4. Brain Behavior

### Tier Classification

Brain classifies trading actions into tiers:

| Tier | Actions | Brain Behavior |
|------|---------|----------------|
| 1 | `scan_market`, `get_portfolio`, `get_market_regime` | Auto-execute, inform user |
| 2 | `preview_trade` | Execute, await user decision |
| 3 | `approve_trade`, `reject_trade` | Requires explicit user approval |

### Slack Flow for Tier 3

1. AxiomFolio webhook: `approval.required` → Brain receives event
2. Brain posts to Slack: "Trade pending: buy 100 AAPL @ $185. Reply 'approve' or 'reject'."
3. User replies in thread: "approve"
4. Brain calls `approve_trade` → AxiomFolio executes
5. Brain confirms: "Trade executed: bought 100 AAPL @ $184.95"

## 5. Security

### Webhook Signatures

AxiomFolio signs webhook payloads with HMAC-SHA256:

```
X-Webhook-Signature: sha256=<hex-encoded-hmac>
```

Brain verifies:

```python
import hmac
import hashlib

expected = hmac.new(
    AXIOMFOLIO_WEBHOOK_SECRET.encode(),
    request.body,
    hashlib.sha256
).hexdigest()

if not hmac.compare_digest(f"sha256={expected}", request.headers["X-Webhook-Signature"]):
    raise HTTPException(401, "Invalid signature")
```

### API Key Rotation

To rotate `AXIOMFOLIO_API_KEY`:

1. Generate new key in AxiomFolio
2. Add new key to Brain env vars (Render dashboard)
3. Trigger Brain redeploy
4. Verify Brain can call AxiomFolio (check Render logs)
5. Revoke old key in AxiomFolio

## 6. Testing Checklist

- [ ] Brain can reach `AXIOMFOLIO_API_URL` (no firewall/CORS issues)
- [ ] `AXIOMFOLIO_API_KEY` is valid (test `GET /api/v1/tools/portfolio`)
- [ ] AxiomFolio can reach Brain webhook endpoint
- [ ] Webhook signature verification works
- [ ] Approval flow works end-to-end via Slack

## 7. Troubleshooting

### Brain logs "AxiomFolio API error: 401"

`AXIOMFOLIO_API_KEY` is invalid or missing. Check Render env vars.

### AxiomFolio logs "Brain webhook rejected"

`AXIOMFOLIO_WEBHOOK_SECRET` mismatch. Ensure both sides use the same secret.

### Brain says "hold on" but doesn't complete

MCP tool execution failed. Check Brain Render logs for:
- `Anthropic MCP API error: 400` → Tool name mismatch (recently fixed)
- `StreamableHTTPSessionManager not initialized` → FastMCP lifespan issue (recently fixed)

### No Slack notifications for trades

1. Check that `BRAIN_NOTIFY_EVENTS` includes the event type
2. Check Brain Render logs for webhook receipt
3. Check n8n `brain-slack-adapter` workflow is active

---

**Last updated**: 2026-03-30
**Contact**: hello@paperworklabs.com
