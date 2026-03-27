"""Pre-built hedge fund strategy templates -- v4 Stage Analysis aware.

Each template uses v4 fields: stage_label (10 sub-stages), regime_state (R1-R5),
scan_tier, action_label, ext_pct, ema10_dist_n, sma150_slope, etc.

New operators available: in, not_in, starts_with, contains.
"""
from __future__ import annotations
from typing import Any, Dict, List

STRATEGY_TEMPLATES: List[Dict[str, Any]] = [
    # ── Long Templates ────────────────────────────────────────────
    {
        "id": "v4_stage2_breakout",
        "name": "V4 Stage 2 Breakout (Regime-Gated)",
        "description": (
            "Stage Analysis v4 breakout: enter on 2A/2B with positive RS, "
            "SMA150 rising, only in R1/R2 regimes. Exit on stage deterioration or R5."
        ),
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["2A", "2B"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2"]},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                    {"field": "sma150_slope", "operator": "gt", "value": 0},
                    {"field": "ema10_dist_n", "operator": "gt", "value": -1.0},
                    {"field": "ext_pct", "operator": "lt", "value": 30},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["3A", "3B", "4A", "4B", "4C"]},
                    {"field": "regime_state", "operator": "eq", "value": "R5"},
                    {"field": "ext_pct", "operator": "gt", "value": 50},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 5.0,
        "max_positions": 15,
        "stop_loss_pct": 8.0,
        "universe_filter": {"indices": ["sp500", "nasdaq100"]},
    },
    {
        "id": "v4_scan_set1_elite",
        "name": "V4 Scan Set 1 Elite Longs",
        "description": (
            "Highest-conviction longs from Scan Overlay Set 1: "
            "stage 2A/2B, RS > 0, EMA10 distance > 0, tight ATRE. "
            "Regime R1 only."
        ),
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "scan_tier", "operator": "eq", "value": "Set 1"},
                    {"field": "regime_state", "operator": "eq", "value": "R1"},
                    {"field": "action_label", "operator": "eq", "value": "BUY"},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "action_label", "operator": "in", "value": ["REDUCE", "AVOID"]},
                    {"field": "scan_tier", "operator": "not_in", "value": ["Set 1", "Set 2"]},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 6.0,
        "max_positions": 10,
        "stop_loss_pct": 7.0,
        "universe_filter": {"indices": ["sp500", "nasdaq100"]},
    },
    {
        "id": "v4_momentum_trend",
        "name": "V4 Momentum Trend Following",
        "description": (
            "Trend-following on v4 metrics: price above SMA150, "
            "positive slope, RSI > 50, regime R1-R3. "
            "Exit on EMA10 distance collapse or stage break."
        ),
        "strategy_type": "momentum",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "starts_with", "value": "2"},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                    {"field": "rsi_14", "operator": "gt", "value": 50},
                    {"field": "sma150_slope", "operator": "gt", "value": 0},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "ema10_dist_n", "operator": "lt", "value": -2.0},
                    {"field": "rsi_14", "operator": "lt", "value": 35},
                    {"field": "stage_label", "operator": "not_in", "value": ["2A", "2B", "2C"]},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 5.0,
        "max_positions": 20,
        "stop_loss_pct": 10.0,
    },
    {
        "id": "v4_pullback_buy",
        "name": "V4 Pullback Buy Zone",
        "description": (
            "Buy pullbacks in Stage 2: EMA10 distance pulls negative "
            "with positive RS and rising SMA150. Regime R1-R2."
        ),
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["2A", "2B", "2C"]},
                    {"field": "ema10_dist_n", "operator": "between", "value": -2.0, "value_high": -0.3},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                    {"field": "sma150_slope", "operator": "gt", "value": 0},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2"]},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "ema10_dist_n", "operator": "gt", "value": 2.0},
                    {"field": "ext_pct", "operator": "gt", "value": 40},
                    {"field": "stage_label", "operator": "starts_with", "value": "3"},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 4.0,
        "max_positions": 15,
        "stop_loss_pct": 7.0,
    },
    {
        "id": "v4_mean_reversion",
        "name": "V4 Mean Reversion RSI Bounce",
        "description": (
            "Buy oversold bounces: RSI < 30, above SMA150 (Stage 1B/2C territory), "
            "not in late-stage decline. Quick exit on recovery."
        ),
        "strategy_type": "mean_reversion",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "rsi_14", "operator": "lt", "value": 30},
                    {"field": "stage_label", "operator": "not_in", "value": ["4A", "4B", "4C"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                    {"field": "sma150_slope", "operator": "gte", "value": 0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "rsi_14", "operator": "gt", "value": 70},
                    {"field": "perf_5d", "operator": "gt", "value": 5},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 3.0,
        "max_positions": 15,
        "stop_loss_pct": 5.0,
        "max_holding_days": 10,
    },
    # ── Short Templates ───────────────────────────────────────────
    {
        "id": "v4_stage4_short",
        "name": "V4 Stage 4 Short (Regime-Gated)",
        "description": (
            "Short declining stocks in Stage 4A/4B with negative RS, "
            "falling SMA150, only in R4/R5 regimes."
        ),
        "strategy_type": "short",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["4A", "4B"]},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                    {"field": "rs_mansfield_pct", "operator": "lt", "value": 0},
                    {"field": "sma150_slope", "operator": "lt", "value": 0},
                    {"field": "sma50_slope", "operator": "lt", "value": 0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["1A", "1B", "2A"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2"]},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 5},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 3.0,
        "max_positions": 10,
        "stop_loss_pct": 10.0,
    },
    {
        "id": "v4_scan_short_set1",
        "name": "V4 Scan Short Set 1",
        "description": (
            "Short stocks flagged by Scan Overlay Short Set 1: "
            "Stage 4, negative RS, high extension below SMA150. R4/R5 only."
        ),
        "strategy_type": "short",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "scan_tier", "operator": "eq", "value": "Short Set 1"},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                    {"field": "action_label", "operator": "eq", "value": "SHORT"},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "stage_label", "operator": "starts_with", "value": "1"},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2"]},
                    {"field": "action_label", "operator": "neq", "value": "SHORT"},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 2.5,
        "max_positions": 8,
        "stop_loss_pct": 8.0,
    },
    # ── Sector / ETF Templates ────────────────────────────────────
    {
        "id": "v4_sector_rotation",
        "name": "V4 Sector Rotation ETF",
        "description": (
            "Momentum on sector ETFs: Stage 2, top RS (>5%), "
            "rising SMA150. Regime-adaptive position sizing."
        ),
        "strategy_type": "momentum",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "starts_with", "value": "2"},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 5},
                    {"field": "sma150_slope", "operator": "gt", "value": 0},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "rs_mansfield_pct", "operator": "lt", "value": 0},
                    {"field": "stage_label", "operator": "starts_with", "value": "3"},
                    {"field": "regime_state", "operator": "eq", "value": "R5"},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 10.0,
        "max_positions": 10,
        "universe_filter": {"asset_type": "etf"},
    },
    # ── Counter-Trend ─────────────────────────────────────────────
    {
        "id": "v4_td_counter_trend",
        "name": "V4 TD Sequential Counter-Trend",
        "description": (
            "Counter-trend entries on TD buy completion: RSI < 40, "
            "not in Stage 4 decline. Quick exit on recovery."
        ),
        "strategy_type": "mean_reversion",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "td_buy_complete", "operator": "eq", "value": True},
                    {"field": "rsi_14", "operator": "lt", "value": 40},
                    {"field": "stage_label", "operator": "not_in", "value": ["4A", "4B", "4C"]},
                    {"field": "regime_state", "operator": "not_in", "value": ["R5"]},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "td_sell_complete", "operator": "eq", "value": True},
                    {"field": "perf_5d", "operator": "gt", "value": 3},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 2.0,
        "max_positions": 15,
        "stop_loss_pct": 3.0,
        "max_holding_days": 5,
    },
]


def get_template(template_id: str) -> Dict[str, Any] | None:
    return next((t for t in STRATEGY_TEMPLATES if t["id"] == template_id), None)


def list_templates() -> List[Dict[str, Any]]:
    return [
        {k: v for k, v in t.items() if k != "default_config"}
        for t in STRATEGY_TEMPLATES
    ]
