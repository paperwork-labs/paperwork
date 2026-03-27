# AxiomFolio + Brain Integration

**Last Updated**: 2026-03-27
**Status**: Architecture defined, implementation pending Phase 11

This document defines how AxiomFolio integrates with the Paperwork Labs Brain — the AI life intelligence that orchestrates across all your financial domains.

---

## Architecture Decision: Separate Repos, Brain Orchestrates

**AxiomFolio stays as a separate repo.** Brain (in the Paperwork repo) calls AxiomFolio as an external tool provider.

```
┌─────────────────────────────────────────────────────────────────┐
│                         BRAIN                                    │
│                  (brain.paperworklabs.com)                       │
│                                                                  │
│   AI life intelligence that knows:                               │
│   - Your taxes (FileFree)                                        │
│   - Your business (LaunchFree)                                   │
│   - Your portfolio (AxiomFolio)                                  │
│   - Your calendar, emails, routines                              │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │       Model Router (ClassifyAndRoute - D20)              │   │
│   │   Gemini Flash classifies → routes to optimal model      │   │
│   └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│   ┌──────────────────────────▼──────────────────────────────┐   │
│   │                   Tool Dispatcher                        │   │
│   │   Calls product APIs as "skills"                         │   │
│   └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│   FileFree   │    │    AxiomFolio    │    │  LaunchFree  │
│     API      │    │       API        │    │     API      │
│              │    │                  │    │              │
│  Tax tools   │    │  Trading tools   │    │ Formation    │
│  SAME REPO   │    │  SEPARATE REPO   │    │  SAME REPO   │
└──────────────┘    └──────────────────┘    └──────────────┘
```

### Why Separate Repos

| Concern | Why Separation Works |
|---------|---------------------|
| **Security boundary** | Trading systems need audit trails, compliance isolation |
| **Deployment cycles** | Trading needs rock-solid stability; Paperwork iterates fast |
| **Team access** | Analyst role gets AxiomFolio access without Paperwork exposure |
| **Regulatory** | If SEC/FINRA compliance needed, already isolated |
| **Focus** | Each repo has one job. Brain orchestrates across them. |

### What Each System Owns

**Brain owns:**
- Model selection (which AI to use)
- Tool routing (which skill to call)
- Memory (episodes, context across all domains)
- Personas (voice, personality)
- Cross-domain insights ("Your Q4 gains affect your estimated taxes")

**AxiomFolio owns:**
- Trading logic (Stage Analysis, risk gates)
- Broker integration (IBKR, Schwab)
- Order execution
- Portfolio data
- Market scanning

---

## AxiomFolio Tools for Brain

Brain calls these endpoints as tools. Each tool has a tier determining approval requirements.

| Tool | Endpoint | Tier | Description |
|------|----------|------|-------------|
| `scan_market` | `GET /api/v1/scans/run` | 0 (auto) | Run scans, return candidates |
| `get_portfolio` | `GET /api/v1/portfolio` | 0 (auto) | Current positions, P&L, exposure |
| `stage_analysis` | `GET /api/v1/analysis/{symbol}` | 0 (auto) | Technical analysis for a symbol |
| `get_risk_status` | `GET /api/v1/portfolio/risk` | 0 (auto) | Current risk metrics, gates |
| `get_watchlist` | `GET /api/v1/watchlist` | 0 (auto) | Tracked symbols and alerts |
| `execute_trade` | `POST /api/v1/orders` | 3 (approval) | Execute trade - requires human approval |
| `modify_position` | `PUT /api/v1/positions/{id}` | 2 (draft) | Modify stops, targets |

### Tool Registration in Brain

```python
# apis/brain/tools/external.py

EXTERNAL_TOOL_PROVIDERS = {
    "axiomfolio": {
        "base_url": os.getenv("AXIOMFOLIO_API_URL", "http://localhost:8100"),
        "auth_header": "X-API-Key",
        "auth_secret": "AXIOMFOLIO_API_KEY",
        "tools": {
            "scan_market": {"method": "GET", "path": "/api/v1/scans/run", "tier": 0},
            "get_portfolio": {"method": "GET", "path": "/api/v1/portfolio", "tier": 0},
            "stage_analysis": {"method": "GET", "path": "/api/v1/analysis/{symbol}", "tier": 0},
            "execute_trade": {"method": "POST", "path": "/api/v1/orders", "tier": 3},
        }
    }
}
```

---

## Cross-Domain Intelligence Examples

With Brain knowing both your taxes AND your portfolio:

> **Tax-aware trading:**
> "Your YTD short-term gains are $47K. One more trade pushing you over $50K moves you into the next bracket. Consider holding AAPL until January for long-term treatment."

> **Estimated tax reminders:**
> "Q4 estimated taxes due January 15. Based on your trading gains, you should set aside $12K. Want me to flag this in your sweep account?"

> **Loss harvesting:**
> "You have $8K in unrealized losses in XYZ. Harvesting now would offset your recent $10K gain in ABC. Want me to analyze the wash sale implications?"

> **Refund routing:**
> "Your $3,200 refund is coming. Based on your portfolio allocation, I'd suggest 60% to brokerage, 40% to HYSA. Want me to set that up?"

---

## Analyst Role + Human Approval Workflow

### Phase 1: Just You
- AxiomFolio is your personal trading system
- Brain calls tools directly (Tier 0-1)
- Tier 3 trades (execute_trade) require your Slack approval

### Phase 2: Add Analyst (Hedge Fund Buddy)

**Roles:**
| Role | Permissions |
|------|-------------|
| `owner` | Full access, can execute trades, manage system |
| `analyst` | Read access to scans, positions, analysis. Can propose trades. |
| `viewer` | Read-only portfolio view |

**Human Approval Workflow:**
```
Trade proposed (by Brain or Analyst)
    │
    ▼
┌─────────────────────────────────┐
│  Slack notification to #trades  │
│  "🔔 Trade proposed: BUY 100    │
│   AAPL @ $185. Risk: $1,850.    │
│   Stage: 2 breakout.            │
│   [Approve] [Reject] [Details]" │
└─────────────────────────────────┘
    │
    ▼
Owner/Analyst clicks [Approve]
    │
    ▼
Trade executes via IBKR
    │
    ▼
Confirmation posted to Slack
```

**Approval Rules (configurable):**
- All trades require approval (conservative)
- Trades > $X require approval
- Only new positions require approval (adds OK, closes auto)
- Analyst-proposed trades require owner approval

### Phase 3: Subscription Autotrading

**User types:**
| Type | Description |
|------|-------------|
| `self_directed` | User connects broker, Brain advises, user executes |
| `auto_approved` | Brain executes within risk parameters, user notified |
| `human_gated` | All trades require user approval via app/Slack |

**Revenue model:**
- $X/mo subscription for Brain trading intelligence
- Optional: % of AUM for fully managed accounts
- Tiered: Free (paper trading) → Personal ($29/mo) → Pro ($99/mo)

### Phase 4: Bloomberg Terminal Vision

Full market intelligence dashboard powered by Brain:
- Real-time market data and alerts
- AI-powered analysis and insights
- Portfolio monitoring across multiple accounts
- News sentiment and event detection
- Collaborative features (analyst notes, shared watchlists)

---

## Local Development: Running Both Repos

Both repos can run simultaneously with different ports.

### Port Allocation

| Service | Paperwork | AxiomFolio |
|---------|-----------|------------|
| PostgreSQL | 5432 | 5433 |
| Redis | 6379 | 6380 |
| Backend API | 8000-8003 | 8100 |
| Frontend | 3000-3004 | 3100 |
| Ladle (Storybook) | — | 6006 |

### AxiomFolio compose.dev.yaml Changes

Update `infra/compose.dev.yaml` to use offset ports:

```yaml
services:
  postgres:
    ports:
      - "5433:5432"  # Changed from 5432:5432
  
  redis:
    ports:
      - "6380:6379"  # Changed from 6379:6379
  
  backend:
    ports:
      - "8100:8000"  # Changed from 8000:8000
    environment:
      - DATABASE_URL=postgresql://...localhost:5433/...  # Update port
      - REDIS_URL=redis://localhost:6380/0
  
  frontend:
    ports:
      - "3100:3000"  # Changed from 3000:3000
```

### Unified Dev Script (Optional)

Create `~/development/dev-all.sh`:

```bash
#!/bin/bash
set -e

echo "Starting Paperwork stack..."
cd ~/development/paperwork && make dev-d

echo "Starting AxiomFolio stack..."
cd ~/development/axiomfolio && make up

echo ""
echo "✓ Both stacks running:"
echo "  Paperwork FileFree: http://localhost:3000"
echo "  Paperwork Studio:   http://localhost:3001"
echo "  AxiomFolio:         http://localhost:3100"
echo ""
echo "To stop: cd ~/development/paperwork && make stop"
echo "         cd ~/development/axiomfolio && make down"
```

---

## Implementation Phases

### Now (AxiomFolio focus)
- [ ] Token efficiency setup (Headroom/RTK installed, MemStack added)
- [ ] API key authentication for external callers
- [ ] Analyst role + permissions model
- [ ] Human approval workflow via Slack

### Phase 11-alpha (Brain Internal)
- [ ] Brain API scaffold (`apis/brain/`)
- [ ] External tool provider registry
- [ ] AxiomFolio tool integration (read-only first)
- [ ] Cross-domain memory (portfolio context in Brain)

### Phase 11-beta (Brain Consumer)
- [ ] Tier 3 approval workflow through Brain
- [ ] Portfolio insights in weekly Brain Brief
- [ ] Tax-aware trading recommendations

### Future
- [ ] Multi-user subscription model
- [ ] Full Bloomberg terminal dashboard
- [ ] Managed account offering

---

## API Contract

### Authentication

AxiomFolio exposes an API key for Brain:

```bash
# In AxiomFolio .env
BRAIN_API_KEY=af_brain_xxxxxxxxxxxx

# Brain calls with header
X-API-Key: af_brain_xxxxxxxxxxxx
```

### Request/Response Format

All endpoints return consistent envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### Webhook for Trade Events

AxiomFolio sends webhooks to Brain for portfolio events:

```json
POST brain.paperworklabs.com/webhooks/axiomfolio
{
  "event": "trade_executed",
  "data": {
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 100,
    "price": 185.50,
    "pnl_impact": null
  },
  "timestamp": "2026-03-27T14:30:00Z"
}
```

Events: `trade_executed`, `position_closed`, `stop_triggered`, `risk_gate_activated`, `scan_alert`

---

## Summary

- **Separate repos** — AxiomFolio stays isolated for security/compliance
- **Brain orchestrates** — calls AxiomFolio as external tool provider
- **Analyst role** — your buddy gets read access + trade proposal ability
- **Human gating** — Tier 3 trades require Slack approval
- **Path to scale** — subscription autotrading with configurable approval levels
- **Bloomberg vision** — full market intelligence dashboard, powered by Brain
