# Models Reference

Data models (Position, Trade, Option, TaxLot, etc.) for DB and API. Inventory and table list: [ARCHITECTURE.md](ARCHITECTURE.md#data-model-inventory). Domain context: [PORTFOLIO.md](PORTFOLIO.md), [MARKET_DATA.md](MARKET_DATA.md).

---

## Table of contents

- [Core](#core)
- [Market Data](#market-data)
- [Market data relationships](#market-data-relationships)
- [Naming conventions](#naming-conventions-reduce-confusion)

---

## Core
- BrokerAccount
  - Fields: user_id, broker, account_number, account_name, account_type, status, sync_status, last_successful_sync
  - Notes: Single source for accounts across brokers

- Position (stocks/equities)
  - Purpose: a user's stock position in a specific broker account
  - Key: (user_id, account_id, symbol)
  - Fields: quantity, average_cost, total_cost_basis, current_price, market_value, unrealized_pnl, unrealized_pnl_pct, day_pnl, sector, industry
  - API DTO (stocks rows):
    - symbol, position (quantity), average_cost, market_price, position_value, unrealized_pnl, unrealized_pnl_pct, day_change, day_change_pct, sector

- Option (options contract/position)
  - Unique: (account_id, underlying_symbol, strike_price, expiry_date, option_type)
  - Fields: open_quantity, current_price, market_value, unrealized_pnl, multiplier, data_source
  - API DTO (options rows):
    - symbol/underlying_symbol, strike_price, expiration_date, option_type, quantity (contracts), average_open_price, current_price, market_value, unrealized_pnl, days_to_expiration, multiplier

- Trade
  - Unique: (account_id, execution_id) and (account_id, order_id)
  - Fields: symbol, side, quantity, price, executed_at, commission, exchange, asset_category

- Transaction
  - Unique: (account_id, external_id) and (account_id, execution_id)
  - Fields: symbol, description, transaction_type, quantity, trade_price, amount, currency, transaction_date

- TaxLot
  - Fields: acquisition_date, quantity, cost_per_share, current_price, market_value, unrealized_pnl, is_long_term, asset_category
  - Methods: FIFO/LIFO/HIFO support in service layer

- AccountBalance
  - Fields: balance_date, net_liquidation, cash, buying_power, margin requirements

- Signals/Alerts
  - ATR signals, portfolio alerts; Discord notifications
  - **SignalType** enum: ENTRY, EXIT, SCALE_OUT, STOP_LOSS, ALERT, TRIM, REBALANCE, ROTATE (TRIM, REBALANCE, ROTATE for strategy automation)

- **CategoryRule** (planned, Section 2)
  - Purpose: rule for auto-assigning positions to categories
  - Fields: category_id, rule_type (SECTOR, INDUSTRY, MARKET_CAP, STAGE, SYMBOL_LIST, CUSTOM), operator, field, value (JSON), priority, is_active

- **Order** (planned, Section 3)
  - Purpose: track orders from strategy signals; idempotency and status lifecycle
  - Fields: idempotency_key, strategy_id, signal_id, user_id, account_id, symbol, side, order_type, quantity, limit_price, stop_price, time_in_force, status (PENDING, SUBMITTED, PARTIAL_FILL, FILLED, CANCELLED, REJECTED, EXPIRED), broker_order_id, filled_quantity, filled_avg_price, is_paper_trade, parent_order_id

- Strategy (existing; enum extension planned)
  - **StrategyStatus**: DRAFT → BACKTESTING → PAPER_TRADING → ACTIVE (PAPER_TRADING, BACKTESTING added in Section 2)

## Market Data

- PriceData
  - Purpose: canonical OHLCV store for symbols (daily/intraday slices)
  - Key: unique on (symbol, date, interval) via constraint `uq_symbol_date_interval`
  - Fields: open_price, high_price, low_price, close_price (required), adjusted_close, volume, true_range, data_source, interval, is_adjusted, created_at
  - Notes: backfills use ON CONFLICT DO NOTHING; missing O/H/L coalesce to Close, Volume defaults to 0

- MarketSnapshot (table: `market_snapshot`)
  - Purpose: compact, query-friendly latest technical snapshot per symbol
  - Key: latest row by (symbol, analysis_type) ordered by `analysis_timestamp`
  - Core fields: current_price, rsi, atr_value/percent/distance, SMA(20/50/100/200), EMA(10/8/21/200), MACD + signal, performance windows (1d/3d/5d/20d/60d/120d/252d/MTD/QTD/YTD)
  - Pine metrics: pct and ATR distances to EMA(8/21/200), TD Sequential counts, gap counts, simple trendline counts
  - Stage: `stage_label`, `stage_slope_pct`, `stage_dist_pct`
  - Notes: `raw_analysis` JSON stores full payload; `expiry_timestamp` enables TTL; refreshed by Celery tasks

- MarketSnapshotHistory (table: `market_snapshot_history`)
  - Purpose: immutable daily snapshots for backtesting/analytics
  - Unique: (symbol, analysis_type, as_of_date)
  - Headline fields: current_price, rsi, atr_value, sma_50, macd, macd_signal
  - Fields: stored as a flat/wide table (queryable columns, no JSON payload)

## Market data relationships

- **PriceData** (OHLCV) is the source for backfills and history; uniqueness on (symbol, date, interval).
- **MarketSnapshot**: latest per-symbol snapshot (stage, RS, RSI, ATR, performance windows, etc.); keyed by (symbol, analysis_type), ordered by analysis_timestamp.
- **MarketSnapshotHistory**: immutable daily snapshots for backtesting; unique (symbol, analysis_type, as_of_date).
- **DailyBar** (if used): daily OHLCV aggregates; consumed by indicator pipeline to produce MarketSnapshot.
- Portfolio **Position** is enriched by LEFT JOIN to latest MarketSnapshot on symbol (no FK; portfolio symbols are in tracked universe).

Constraints and Integrity
- Enforced uniqueness on trades, transactions, and options to prevent brokerage dupes
- Foreign keys point to `BrokerAccount`
- Use enums from `backend/models/broker_account.py` and related enums for consistency

## Naming conventions (reduce confusion)

- Use "stocks" and "options" in routes/pages; avoid the term "holdings".
- Use "position" to refer to a position row (stock or option). For stocks: `Position`. For options: `Option`.
- Align DTO field names across API responses:
  - For stocks, prefer: position (quantity), average_cost, market_price, market_value, day_change.
  - For options, prefer: quantity (contracts), average_open_price, current_price, market_value.

Testing Checklist per Model
--------------------------
- Creation and basic persistence
- Uniqueness constraint violations (expected failure)
- Relationship integrity (FKs)
- Serialization shape used by API routes

