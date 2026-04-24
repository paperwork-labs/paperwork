# AxiomFolio Trading North Star

14 non-negotiable principles derived from Mark Minervini, Paul Tudor Jones, Stan Weinstein, Ed Seykota, and Van Tharp. Every automated trade must align.

## Capital Protection (PTJ / Dalio)

1. **Risk First** — Never risk > 1% of equity on a single trade
2. **Cut Losses Quickly** — 7–8% max loss, hard stops non-negotiable
3. **Portfolio Heat Limit** — Total open risk never exceeds 6% of equity

## Position Sizing (Minervini / Van Tharp)

4. **Size by Volatility** — Position = Risk Budget / (ATR × Stop Mult)
5. **Conviction Scaling** — Full size only in best setups
6. **R-Multiple Framework** — Track every trade in units of initial risk

## Trend Alignment (Weinstein / O'Neil)

7. **Stage Discipline** — Long entries ONLY in Stage 2
8. **Regime Gate** — Adapt size/strategy to market regime
9. **Relative Strength** — Trade leaders only (RS > 0)

## Execution Discipline (Seykota / Williams)

10. **Mechanical Rules** — No discretionary overrides
11. **Let Winners Run** — Adaptive trailing, never cut winners short
12. **Volume Confirms** — Breakouts require Vol Ratio > 1.5

## Continuous Improvement

13. **Review Every Trade** — Post-trade analysis mandatory
14. **Expectancy Positive** — Only run strategies with edge > 0

---

## Principle → code enforcement map

| # | Principle | Where it is enforced (or status) |
|---|-----------|----------------------------------|
| 1 | Risk First | `app/services/execution/order_manager.py` — default `risk_budget = portfolio_equity * 0.01` when not supplied on preview/submit. `app/services/execution/risk_gate.py` — sizing uses that budget. **Note:** `Strategy.max_risk_per_trade` exists in `app/models/strategy.py` but is not yet wired into `OrderManager`; align DB defaults with this principle when connecting. |
| 2 | Cut Losses Quickly | `app/services/execution/exit_cascade.py` — Tier 1 hard stop (2× ATR below entry). Strategy templates: `app/api/routes/strategies.py` default `stop_loss_pct` 8%; `app/services/strategy/ai_strategy_builder.py` requires stop and rejects > 15% width. Fixed 7–8% equity stop is **policy + strategy params**, not a separate global hard gate today. |
| 3 | Portfolio Heat (6%) | **Gap:** No aggregate “open risk ≤ 6% equity” check in `OrderManager` / `PreTradeValidator` yet. `Strategy.max_portfolio_risk` on `app/models/strategy.py` is reserved for future wiring. Circuit breaker reduces size on daily loss: `app/services/risk/circuit_breaker.py`. |
| 4 | Size by Volatility | `app/services/execution/risk_gate.py` — `compute_position_size()` / docstring formula: Full $ = [Risk Budget / (ATR%14 × Stop Mult)] × Regime Mult; `DEFAULT_STOP_MULTIPLIER = 2.0`. |
| 5 | Conviction Scaling | `app/services/execution/risk_gate.py` — `STAGE_CAPS` (fraction of full size by stage × regime). Regime multipliers from `app/services/market/regime_engine.py` consumed in sizing path. |
| 6 | R-Multiple Framework | **Partial:** Trade/position models store execution data (`app/models/trade.py`, etc.); no dedicated R-multiple ledger or gate in the execution path. Backtest summaries expose win rate and profit factor in `app/services/strategy/backtest_engine.py`. |
| 7 | Stage Discipline | `app/services/execution/risk_gate.py` — `STAGE_CAPS` sets 0% size for Stage 1 buckets on longs. Stage classification and 1B→2A breakout rules: `app/services/market/indicator_engine.py` (e.g. `vol_ratio > 1.5`, stage priority). |
| 8 | Regime Gate | `app/services/market/regime_engine.py` — R1–R5 rules. `risk_gate.py` regime multipliers + stage caps; `app/services/execution/exit_cascade.py` — regime-conditioned exit tiers (T6–T9). `app/services/strategy/alpha_engine.py` — regime-weighted factors. |
| 9 | Relative Strength | `app/services/market/indicator_engine.py` — RS Mansfield and 2B(RS−) style modifiers. `app/services/strategy/alpha_engine.py` — `rs_mansfield` factor. Strategy conditions can reference snapshot fields via `app/services/strategy/rule_evaluator.py`. |
| 10 | Mechanical Rules | `app/services/strategy/rule_evaluator.py` — rule-driven evaluation. Automated path: `app/tasks/strategy/tasks.py` (signal → sizing → execution). `OrderManager` is the single submit path: `app/services/execution/order_manager.py`. |
| 11 | Let Winners Run | `app/services/execution/exit_cascade.py` — Tier 2 adaptive trailing (stage/regime/vol adjustments); higher tiers for regime deterioration. |
| 12 | Volume Confirms | `app/services/market/indicator_engine.py` — `vol_ratio` computation; breakout classification uses `vol_ratio > 1.5`. `app/services/strategy/alpha_engine.py` — `_compute_volume_trend` / vol_ratio checks in signal helpers. |
| 13 | Review Every Trade | `app/services/portfolio/activity_aggregator.py` + `app/api/routes/activity.py` — unified activity feed for post-hoc review. **Process** (mandatory review) is operational; not a code blocker on submit. |
| 14 | Expectancy Positive | `app/services/strategy/paper_validator.py` — gates (e.g. `min_profit_factor`, drawdown, win rate) before live promotion. `app/services/strategy/backtest_engine.py` — `profit_factor`, `win_rate` on `BacktestSummary`. |

When adding or changing execution logic, update this table if enforcement moves or new gates appear.
