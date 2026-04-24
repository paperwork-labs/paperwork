# Strategy System

## Overview

The strategy system enables quantitative rule-based trading with backtesting and automated execution.

## Architecture

```
User → Strategy UI → Rules Engine → Backtest Engine → Signal Generator → Order Pipeline
```

### Components

- **Rule Evaluator** (`backend/services/strategy/rule_evaluator.py`): Evaluates nested condition groups against market data
- **Backtest Engine** (`backend/services/strategy/backtest_engine.py`): Replays rules against MarketSnapshotHistory
- **Signal Generator** (`backend/services/strategy/signal_generator.py`): Converts rule matches to actionable signals
- **Templates** (`backend/services/strategy/templates.py`): Pre-built hedge fund strategy configurations

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/strategies` | List user strategies |
| POST | `/strategies` | Create custom strategy |
| GET | `/strategies/templates` | List pre-built templates |
| GET | `/strategies/templates/:id` | Get full template config |
| POST | `/strategies/from-template` | Create from template |
| GET | `/strategies/:id` | Get strategy detail |
| PUT | `/strategies/:id` | Update strategy |
| DELETE | `/strategies/:id` | Delete strategy |
| POST | `/strategies/:id/evaluate` | Run rules against live data |
| POST | `/strategies/:id/backtest` | Run historical backtest |

## Pre-Built Templates

### 1. Weinstein Stage 2 Breakout
- **Type**: Breakout
- **Entry**: Stage 2A/2B, RS Mansfield > 0, price above SMA 50, positive 5d performance
- **Exit**: Stage 3/4 or price below SMA 50
- **Universe**: S&P 500 + NASDAQ 100

### 2. Momentum Trend Following
- **Type**: Momentum
- **Entry**: Price above SMA 50 and SMA 200, RSI > 50, positive RS
- **Exit**: Price below EMA 21 and RSI < 40

### 3. Mean Reversion RSI Bounce
- **Type**: Mean Reversion
- **Entry**: RSI < 30, price above SMA 200, not Stage 4
- **Exit**: RSI > 70 or 5d gain > 5%

### 4. Pullback Buy Zone
- **Type**: Breakout
- **Entry**: Stage 2, pulled back to EMA 21, positive RS
- **Exit**: Extended from EMA 21 or stage deterioration

### 5. Sector Rotation ETF
- **Type**: Momentum
- **Entry**: Top quartile RS, Stage 2, above SMA 50
- **Exit**: RS drops below 0 or stage change
- **Universe**: ETFs only

### 6. TD Sequential Counter-Trend
- **Type**: Mean Reversion
- **Entry**: TD buy completion, RSI < 40, not Stage 4
- **Exit**: TD sell completion or 5d gain > 3%

## Rule Engine

### Condition Operators
- `gt`, `gte`, `lt`, `lte`: Numeric comparisons
- `eq`, `neq`: Equality checks (works for strings and numbers)
- `between`: Range check (requires value and value_high)

### Condition Groups
Rules are nested AND/OR groups:
```json
{
  "logic": "and",
  "conditions": [
    {"field": "rsi", "operator": "lt", "value": 30},
    {"field": "stage_label", "operator": "neq", "value": "4"}
  ],
  "groups": [
    {
      "logic": "or",
      "conditions": [
        {"field": "stage_label", "operator": "eq", "value": "2A"},
        {"field": "stage_label", "operator": "eq", "value": "2B"}
      ]
    }
  ]
}
```

### Available Fields
Any column from MarketSnapshot can be used, including:
- Price: `current_price`, `sma_5` through `sma_200`, `ema_8`, `ema_21`, `ema_200`
- Momentum: `rsi`, `macd`, `macd_signal`, `macd_histogram`, `adx`, `stoch_rsi`
- Volatility: `atr_14`, `atr_30`, `atrp_14`, `atrp_30`, `atr_distance`, `atr_dist_ema21`
- Stage: `stage_label`, `current_stage_days`, `stage_slope_pct`
- Relative Strength: `rs_mansfield_pct`
- Performance: `perf_1d`, `perf_5d`, `perf_20d`, `perf_60d`, `perf_252d`
- TD Sequential: `td_buy_setup`, `td_sell_setup`, `td_buy_complete`, `td_sell_complete`
- Bollinger: `bollinger_upper`, `bollinger_lower`, `bollinger_width`

## User Journey

1. Browse strategy templates or create custom
2. Configure universe, position sizing, risk parameters
3. View entry/exit rules
4. Run backtest with date range and initial capital
5. Review equity curve, metrics, and trade history
6. Activate strategy (paper mode first)
7. Monitor signals in Market Dashboard Holdings lens
8. Execute trades from signals
