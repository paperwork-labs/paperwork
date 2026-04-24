# Strategy → Market Navigation Restructure Plan

## Current State

```
MARKET (4 items)
├── Dashboard
├── Tracked
├── Intelligence
└── Education

PORTFOLIO (8 items)
├── Overview
├── Holdings
├── Options
├── Transactions
├── Categories
├── Tax Center
├── Orders
└── Workspace

STRATEGY (2 items)
├── Strategy Manager
└── Strategies
```

## Problem

1. Strategy is tightly coupled to Market data — strategies evaluate rules against `MarketSnapshot`
2. Natural workflow: "View market → See opportunity → Create/backtest strategy"
3. Portfolio is separate concern (your holdings) vs Market+Strategy (decision engine)
4. Agent Guru needs prominent placement as the unifying interface

## Proposed Structure

```
MARKET
├── Dashboard (/) — Top-down regime + sectors
├── Tracked (/market/tracked) — Bottom-up stock scanner
├── Strategies (/market/strategies) — NEW LOCATION
│   ├── List view with backtest stats
│   └── Create from templates
├── Education (/market/education) — Stage Analysis deep dives
└── Agent Guru (/admin/agent) — AI assistant (prominent placement)

PORTFOLIO (unchanged)
├── Overview
├── Holdings
├── Options
├── Transactions
├── Categories
├── Tax Center
├── Orders
└── Workspace
```

## Data Flow Rationale

```
Ingest → Compute → Store → Consume → Act
  │        │         │        │        │
  └────────┼─────────┼────────┼────────┘
           │         │        │
      MarketData   MarketSnapshot  Strategy Rules
           │         │              │
           └─────────┴──────────────┘
                     │
              "Intelligence Pillar"
```

Strategy is a **consumer** of Intelligence, not a separate pillar in the UI sense.
Portfolio remains separate — it's your actual money, not hypotheticals.

## Implementation Steps

### Phase 1: Route Migration

1. Update `App.tsx` routes:
   - `/strategies` → `/market/strategies`
   - `/strategies-manager` → `/market/strategies/manage`
   - Add redirect for old paths

2. Update `DashboardLayout.tsx`:
   ```tsx
   const marketItems = [
     { label: 'Dashboard', icon: Home, path: '/' },
     { label: 'Tracked', icon: List, path: '/market/tracked' },
     { label: 'Strategies', icon: Target, path: '/market/strategies' },  // Moved
     { label: 'Education', icon: BookOpen, path: '/market/education' },
     { label: 'Agent Guru', icon: Brain, path: '/admin/agent' },  // Promoted
   ];
   
   // Remove strategyItems array
   ```

### Phase 2: Agent Guru Promotion

Option A: Top of Market section (recommended)
```tsx
const marketItems = [
  { label: 'Agent Guru', icon: Brain, path: '/admin/agent' },  // First
  { label: 'Dashboard', icon: Home, path: '/' },
  ...
];
```

Option B: Floating action button (always visible)
- FAB in bottom-right corner
- Opens slide-over chat panel

Option C: Keep in nav but add keyboard shortcut
- `Cmd+K` or `Cmd+J` to open Agent

### Phase 3: Deep Linking

Ensure these flows work:
1. Click stock in Tracked → View chart → "Create strategy for AAPL"
2. Agent suggests strategy → One-click navigate to strategy detail
3. Backtest result → Link to historical snapshot view

## Files to Change

| File | Changes |
|------|---------|
| `frontend/src/App.tsx` | Route paths, add redirects |
| `frontend/src/components/layout/DashboardLayout.tsx` | Nav items |
| `frontend/src/pages/Strategies.tsx` | Update internal links |
| `frontend/src/pages/StrategiesManager.tsx` | Update internal links |
| `frontend/src/pages/StrategyDetail.tsx` | Update breadcrumbs |
| `app/api/routes/strategies.py` | No change (API paths stay same) |

## Migration Path

1. Add new routes alongside old ones
2. Add redirects from old → new
3. Update nav items
4. Test all deep links
5. Remove old routes after 1 release

## Questions to Resolve

1. **Agent Guru placement**: Top of Market, or floating FAB?
2. **Intelligence page**: Keep as separate item or merge into Dashboard?
3. **Strategy Manager vs Strategies**: Merge into single page with tabs?

## Timeline

This is a frontend-only change. Backend API routes remain unchanged.

- Phase 1 (routes): 2-3 hours
- Phase 2 (Agent placement): 1 hour
- Phase 3 (deep links): 2 hours
- Testing: 1 hour

Total: ~6-8 hours of focused work
