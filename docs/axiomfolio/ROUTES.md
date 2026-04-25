---
owner: engineering
last_reviewed: 2026-04-24
doc_kind: reference
domain: trading
status: active
---
# Frontend Route Map

Complete route tree, navigation structure, access control, and component mapping for the Axiomfolio frontend.

## Route Tree

```
/ (RequireAuth → DashboardLayout)
├── / (index) → MarketDashboard
├── /market/dashboard → MarketDashboard
│   ├── All (Constituents lens): S&P 500 / NASDAQ 100 / DOW 30 — broad market scanning for entries and exits
│   │   Sections: Pulse, Action Queue, Sector Rotation, Scatter, Setups,
│   │             Transitions, Ranked, Proximity, Insights, Signals, Earnings
│   ├── ETFs (Sector Rotation lens): ~60 sector & thematic ETFs
│   │   Sections: Pulse, Sector Rotation, Scatter, Proximity, Insights
│   └── Holdings (Portfolio lens): Your positions
│       Sections: Action Queue, Setups, Transitions, Proximity, Signals, Earnings
├── /market/tracked → MarketTracked
├── /market/coverage → MarketCoverage
├── /market/education → MarketEducation
├── /portfolio (RequireNonMarketAccess section="portfolio")
│   ├── /portfolio → PortfolioOverview
│   ├── /portfolio/holdings → PortfolioHoldings
│   ├── /portfolio/options → PortfolioOptions
│   ├── /portfolio/transactions → PortfolioTransactions
│   ├── /portfolio/categories → PortfolioCategories
│   ├── /portfolio/tax → PortfolioTaxCenter
│   ├── /portfolio/orders → PortfolioOrders
│   └── /portfolio/workspace → PortfolioWorkspace
├── /strategies (RequireNonMarketAccess section="strategy")
│   ├── /strategies → Strategies (hub with template gallery)
│   ├── /strategies/:id → StrategyDetail (Overview, Rules, Backtest, Signals tabs)
│   └── /strategies-manager → redirects to /strategies
├── /settings → SettingsShell (nested)
│   ├── /settings (redirect → profile)
│   ├── /settings/profile → SettingsProfile
│   ├── /settings/preferences → SettingsPreferences
│   ├── /settings/notifications → SettingsNotifications
│   ├── /settings/connections → SettingsConnections
│   └── /settings/admin/* (RequireAdmin)
│       ├── /settings/admin/dashboard → AdminDashboard
│       ├── /settings/admin/jobs → AdminJobs
│       ├── /settings/admin/schedules → AdminSchedules
│       └── /settings/admin/users → SettingsUsers
/login → Login
/register → Register
/invite/:token → Invite
```

All routes under `/` are lazy-loaded via `React.lazy` with a shared `<Suspense>` boundary.

## Market Section Details

### /market/dashboard (MarketDashboard)

Three analytical lenses:

| Lens | Scope | Sections |
|------|-------|----------|
| **All** (Constituents) | S&P 500 / NASDAQ 100 / DOW 30 — broad market scanning for entries and exits | Pulse, Action Queue, Sector Rotation, Scatter, Setups, Transitions, Ranked, Proximity, Insights, Signals, Earnings |
| **ETFs** (Sector Rotation) | ~60 sector & thematic ETFs | Pulse, Sector Rotation, Scatter, Proximity, Insights |
| **Holdings** (Portfolio) | Your positions | Action Queue, Setups, Transitions, Proximity, Signals, Earnings |

### /market/tracked (MarketTracked)

- **Toggles:** My Holdings, ETFs Only
- **Filter presets:** Momentum Trend, Giants Waking Up, Short-Term Squeeze, Breakout Watch, Pullback Buy Zone, RS Leaders, Stage 1 Base Building, Distribution Warning, Stage 4 Decline
- **Trade actions:** Per-row Trade button opening OrderModal

## Strategy Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/strategies` | Strategies | Hub with template gallery |
| `/strategies/:id` | StrategyDetail | Overview, Rules, Backtest, Signals tabs |
| `/strategies-manager` | — | Redirects to `/strategies` |

## Sidebar Navigation

The sidebar renders four collapsible sections. Visibility depends on `appSettings` feature flags and the user's role.

| Section      | Items                                                                                                    | Visible When                                              |
| ------------ | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **MARKET**   | Dashboard (`/`), Tracked (`/market/tracked`), Coverage (`/market/coverage`), Education (`/market/education`) | Always                                                    |
| **PORTFOLIO**| Overview, Holdings, Options, Transactions, Categories, Tax Center, Orders, Workspace                     | `portfolioEnabled` — admin OR (`!market_only_mode` AND `portfolio_enabled`) |
| **STRATEGY** | Strategy Manager (`/strategies-manager`), Strategies (`/strategies`)                                     | `strategyEnabled` — admin OR (`!market_only_mode` AND `strategy_enabled`)   |
| **SETTINGS** | Settings (`/settings`)                                                                                   | `user.role === 'admin'`                                   |

Non-admin users reach settings pages (Profile, Preferences, Connections) through the user avatar menu in the header, not via the sidebar.

## Access Control

| Guard                      | Wraps                                  | Behavior                                                                                         |
| -------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **RequireAuth**            | All routes under `/`                   | Redirects unauthenticated users to `/login`                                                      |
| **RequireAdmin**           | `/settings/admin/*`                    | Checks `user.role === 'admin'`; redirects to `/` if not admin                                    |
| **RequireNonMarketAccess** | `/portfolio/*`, `/strategies*`         | Admins always pass. Non-admins are redirected to `/` when `market_only_mode` is on or the section's feature flag is off |

### Feature Flags (from `appSettings`)

- **`market_only_mode`** — When true, only Market routes are accessible for non-admin users.
- **`portfolio_enabled`** — Gates the Portfolio section. Ignored when `market_only_mode` is true.
- **`strategy_enabled`** — Gates the Strategy section. Ignored when `market_only_mode` is true.

Admin users (`user.role === 'admin'`) bypass all feature-flag gates.

## Contextual Panels

These are overlay components rendered outside the route tree:

- **ChartSlidePanel** (Intelligence Panel) — Right slide-over panel. 95 vw on mobile, 60 vw on desktop. Opened via `SymbolLink` click or `ChartContext`. Used across Market, Portfolio, and Workspace pages.
- **TradeModal** (via OrderModal) — 3-step trade wizard (configure → preview → submit). Triggered from Holdings, Tax Center, Workspace, MarketTracked, and ChartSlidePanel. Defaults to Buy for non-held symbols, Sell for held.

## Planned Routes

| Route               | Component        | Notes                            |
| -------------------- | ---------------- | -------------------------------- |
| `/market/watchlist`  | MarketWatchlist   | Custom watchlist management      |
| `/strategies/new`    | StrategyCreate   | Strategy creation wizard         |
