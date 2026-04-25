---
owner: trading
last_reviewed: 2026-04-24
doc_kind: spec
domain: trading
status: active
---
# Stage Analysis Specification — In-Repo Reference

> Canonical reference for AxiomFolio's Stage Analysis implementation.
> Source of truth: `Stage_Analysis.docx` → code in `app/services/market/stage_classifier.py`.

## Overview

Stage Analysis classifies every stock into one of **10 sub-stages** based on its relationship
to the **150-day SMA** (the primary anchor). Stages flow cyclically:
Base (1) → Advance (2) → Distribution (3) → Decline (4) → Base (1).

## Classification Rules

### Primary Anchor: SMA150

All stage classification begins with **price vs. SMA150** and **SMA150 slope** (20-day lookback).

### Slope Threshold

`SLOPE_T = 0.35%` — slopes above +0.35% are "up", below −0.35% are "down", in between is "flat".

### Priority Order (First Match Wins)

| Priority | Stage | Condition |
|----------|-------|-----------|
| 1 | **4C** | Below SMA150, slope strongly down (< −0.35%), extension < −15% |
| 2 | **4B** | Below SMA150, slope strongly down |
| 3 | **4A** | Below SMA150, slope ≤ 0, SMA50 slope < 0 |
| 4 | **1A** | \|extension\| < 5%, slope flat (±0.35%), SMA150 slope ≤ 0 |
| 5 | **1B** | \|extension\| < 5%, slope flat or gently positive (not strongly up) |
| 6 | **2A** | Above SMA150, slope positive (> 0), extension ≤ 5% |
| 7 | **2B** | Above SMA150, slope strongly up (> 0.35%), extension ≤ 15% |
| 8 | **2C** | Above SMA150, slope strongly up, extension > 15% |
| 9 | **3A** | Above SMA150, slope not strongly up |
| 10 | **3B** | Above SMA150 (safety net — effectively unreachable; all above + slope_up captured by 2B/2C) |

### Extension Percentage

`ext_pct = (price − SMA150) / SMA150 × 100`

### Slope Calculations

- **SMA150 slope**: percentage change over 20 bars
- **SMA50 slope**: percentage change over 10 bars

## Post-Classification Modifiers

### ATRE Override (2A/2B → 2C)

When `ATRE_150 > 6` (price is more than 6 ATR₁₄ above SMA150), stages 2A and 2B are
reclassified to **2C** (extended). This is purely a volatility-adjusted extension check,
**not** regime-based relabeling.

### RS Mansfield Modifier (2B → 2B(RS−))

When a stock is in stage 2B and its Mansfield Relative Strength vs. S&P 500 is negative
(`rs_mansfield < 0`), the stage is annotated as **2B(RS−)** to flag relative weakness
despite absolute strength.

### Breakout Override (1B → 2A)

When a stock is in 1B, **above** SMA150, with `vol_ratio > 1.5` and MAs stacked
(`EMA10 > SMA21 > SMA50`), it is immediately promoted to **2A**.

## Regime Gate (Risk Enforcement)

Stage caps control maximum position allocation based on current market regime:

| Stage | R1 (Bull) | R2 (Early Bear) | R3 (Bear) | R4 (Late Bear) | R5 (Crisis) |
|-------|-----------|-----------------|-----------|-----------------|-------------|
| 1A | 0% | 0% | 0% | 0% | 0% |
| 1B | 0% | 0% | 0% | 0% | 0% |
| **2A** | **75%** | 50% | 50% | **33%** | 0% |
| **2B** | **100%** | 100% | 75% | 0% | 0% |
| **2C** | 100% | 75% | 50% | 0% | 0% |
| 3A | 50% | 25% | 0% | 0% | 0% |
| 3B | 0% | 0% | 0% | 0% | 0% |
| 4A–4C | 0% | 0% | 0% | 0% | 0% |

**R4 + 2A at 33%** is intentional: deteriorating markets can still produce strong 2A breakouts
worthy of reduced-size positions with volume confirmation. **R5 blocks ALL new longs.**

Stage cap violations raise `RiskViolation` (hard block, not warning).

## Position Sizing Formula

```
risk_budget = account_equity × risk_per_trade_pct
full_position = risk_budget / (ATRP_14 / 100) / stop_multiplier
capped_position = full_position × stage_cap × regime_mult
shares = floor(capped_position / current_price)
```

Where:
- `ATRP_14` = ATR₁₄ as percentage of price: `(ATR_14 / price) × 100`
- `stop_multiplier` = default 2.0 (how many ATRs for the initial stop)
- `regime_mult` = adjustment factor based on market regime

## Exit Cascade — SMA150 Chain

When the stage classifier moves a position to **4x** (below declining SMA150), the exit
cascade's **T3 (Stage Deterioration)** tier triggers a **full position exit**. This is the
systematic enforcement of "never hold below a declining 150-day moving average."

## Minimum Data Requirements

- **175 bars** of daily OHLCV data required for classification (SMA150 + slope lookback)
- **252 bars** recommended for RS Mansfield calculation

## Key Files

| File | Purpose |
|------|---------|
| `app/services/market/stage_classifier.py` | Stage classification logic |
| `app/services/market/indicator_engine.py` | Indicator computation (SMA, ATR, RSI, etc.) |
| `app/services/market/regime_engine.py` | Market regime classification (R1–R5) |
| `app/services/execution/risk_gate.py` | Position sizing + stage/regime caps |
| `app/services/execution/exit_cascade.py` | 9-tier exit cascade including stage exits |
| `Stage_Analysis.docx` | Original specification document |
