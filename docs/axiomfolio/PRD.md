---
owner: strategy
last_reviewed: 2026-04-09
doc_kind: reference
domain: trading
status: active
---
# Product Requirements Document

> **STRATEGIC UPDATE — 2026-04-09**: This PRD is **historically frozen** and reflects the v0 single-operator vision. The current product strategy, milestones, and scope live in [`docs/axiomfolio/plans/MASTER_PLAN_2026.md`](plans/MASTER_PLAN_2026.md).
>
> Key shifts since this doc was written:
> - **Multi-tenant SaaS** — was non-goal, now core. Five subscription tiers (Free / Pro / Pro+ / Quant Desk / Enterprise).
> - **Native AgentBrain chat** — Pro+ hook, lives in-product (was non-goal).
> - **Validator-curated picks pipeline** — Twisted Slice persona (hedge fund analyst) forwards emails → LLM polymorphic parser → validator queue → tier-gated publish.
> - **Beautiful portfolio charts** — free-tier hook for retail acquisition (equity curve, drawdown, sector heatmaps, income calendar).
> - **Multi-broker** — Plaid Investments + 5+ hand-rolled adapters (was IBKR/Schwab/TastyTrade only).
> - **PWA mobile** — was non-goal, now v1 acceptance criterion.
> - **Cross-product integration with [Paperwork Labs](https://github.com/paperwork-labs/paperwork)** — FileFree (taxes), Paperwork Brain (cross-domain AI). Not required, optional bundles.
>
> A full v2 PRD rewrite is scheduled for v1 launch week (2026-06-21). Until then, the master plan is the source of truth.

---

## Vision

AxiomFolio is a quantitative portfolio intelligence platform that implements the Oliver Kell / Weinstein Stage Analysis trading system. It combines multi-broker portfolio aggregation, systematic market intelligence, and rule-based strategy execution into a single platform.

The goal: replace Bloomberg Terminal + Excel spreadsheets + manual monitoring with an automated, agent-driven system that delivers actionable intelligence.

## Target User

Single operator (hedge fund manager / active trader) managing a multi-broker portfolio across IBKR, Schwab, and TastyTrade. Power user who understands Stage Analysis, market regimes, and quantitative risk management.

## Three Pillars

### Pillar 1: Portfolio (Read-Only Sync)

Aggregate positions, trades, tax lots, options, balances, and transactions across multiple brokers into a unified view.

- **Brokers**: IBKR (FlexQuery + Gateway), TastyTrade (SDK), Schwab (OAuth)
- **Data**: Positions, tax lots (FIFO), trades, transactions, dividends, transfers, balances, options with Greeks
- **Features**: Smart categories, drag-and-drop reordering, allocation analysis, tax center, P&L tracking
- **IB Gateway**: Live overlay for real-time prices, positions, Greeks, option chains

### Pillar 2: Intelligence (Market Data + Indicators)

Systematic market data pipeline that computes Stage Analysis indicators for a tracked universe (~2,500 stocks).

- **Data**: 252 trading days of OHLCV per ticker from FMP/Finnhub/TwelveData/AlphaVantage/yfinance
- **Indicators**: SMA/EMA suite, RSI (Wilder), ATR, MACD, ADX, Bollinger, StochRSI, TD Sequential, Mansfield RS
- **Stage Analysis**: SMA150 anchor, 10 sub-stages, ATRE override, EMA10 Dist_N, volume ratio, range fields
- **Market Regime Engine**: 6-input scoring (VIX, VIX3M/VIX, VVIX/VIX, NH-NL, %above200D, %above50D) → R1–R5 hard gates
- **Scan Overlay**: 4 long tiers + 2 short tiers, 6-filter gate, regime-gated access
- **Output**: MarketSnapshot (latest) + MarketSnapshotHistory (immutable daily ledger)

### Pillar 3: Strategy (Rules + Execution)

Rule-based strategy engine with backtesting, signal generation, and order execution.

- **Rule Evaluator**: Nested AND/OR condition groups against MarketSnapshot fields
- **Backtest Engine**: Replay rules against MarketSnapshotHistory
- **Templates**: Pre-built strategies (Weinstein Stage 2 Breakout, Momentum, Mean Reversion, etc.)
- **Order Pipeline**: OrderManager → RiskGate → BrokerRouter → Executor (IBKR primary)
- **Exit Cascade**: 9-tier independently-firing exit system (5 base + 4 regime)
- **Position Sizing**: ATR-based with Regime Multiplier x Stage Cap

## Dashboard Views (Bloomberg-Style)

### Top-Down View
Regime banner, volatility panel (VIX3M/VIX, VVIX/VIX), index performance grid, sector weight matrix, thematic groups (ATOMS/BITS/Debasement), valuation sidebar, watchlist.

### Bottom-Up Strategy Selection
Stage distribution bar, stock scanner table (Ticker, Sector, Stage, Action, Ext150%, ATRv150, ATR%, RSI), key picks summary with rationale, regime-gated filters.

### Sector Deep-Dives
Per-sector thesis + individual stock tables with PE/PEG ratios, growth metrics, ATR fields.

### Historical Heatmap
Sector ETFs x dates, cells colored by stage. Spot sector rotation visually.

## Intelligence Brief System

### Daily Digest (auto, post-pipeline)
Regime state change, stage transitions, scan tier promotions, exit cascade triggers, key metrics.

### Weekly Strategy Brief (Monday pre-market)
Regime trend, stage distribution shift, top picks, sector rotation, portfolio health, open position review. Styled like GPUs_vs_GWs research briefs.

### Monthly/Quarterly Review
Performance attribution, regime history, backtest validation, thematic deep-dives.

## Non-Goals (Do Not Build)

- Multi-user SaaS (single operator for now)
- Drawing tools, volume profile, Elliott Wave, Fibonacci (use TradingView for these)
- Custom indicator creation UI (power users edit indicator_engine.py directly)
- Mobile native app (responsive web only)
- Social/community features
