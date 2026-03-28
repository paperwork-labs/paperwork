"""Pre-built hedge fund strategy templates -- Stage Analysis aware.

Each template uses extended fields: stage_label (10 sub-stages), regime_state (R1-R5),
scan_tier, action_label, ext_pct, ema10_dist_n, sma150_slope, ttm_squeeze_on,
ttm_momentum, etc.

New operators available: in, not_in, starts_with, contains.
"""
from __future__ import annotations
from typing import Any, Dict, List

STRATEGY_TEMPLATES: List[Dict[str, Any]] = [
    # ── Long Templates ────────────────────────────────────────────
    {
        "id": "stage2_breakout",
        "name": "Stage 2 Breakout",
        "description": (
            "Stage Analysis breakout: enter on 2A/2B with positive RS, "
            "SMA150 rising, only in R1-R3 regimes. Exit on stage deterioration or R5."
        ),
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["2A", "2B"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
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
        "id": "scan_breakout_elite",
        "name": "Scan Breakout Elite",
        "description": (
            "Highest-conviction longs from Scan Overlay Breakout Elite: "
            "stage 2A/2B, RS > 0, EMA10 distance > 0, tight ATRE. "
            "Regimes R1-R3 only."
        ),
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "scan_tier", "operator": "eq", "value": "Breakout Elite"},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                    {"field": "action_label", "operator": "eq", "value": "BUY"},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "action_label", "operator": "in", "value": ["REDUCE", "AVOID"]},
                    {"field": "scan_tier", "operator": "not_in", "value": ["Breakout Elite", "Breakout Standard"]},
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
        "id": "momentum_trend",
        "name": "Momentum Trend Following",
        "description": (
            "Trend-following on extended metrics: price above SMA150, "
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
        "id": "pullback_buy",
        "name": "Pullback Buy Zone",
        "description": (
            "Buy pullbacks in Stage 2: EMA10 distance pulls negative "
            "with positive RS and rising SMA150. Regimes R1-R3."
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
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
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
        "id": "mean_reversion",
        "name": "Mean Reversion RSI Bounce",
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
        "id": "stage4_short",
        "name": "Stage 4 Short",
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
        "id": "scan_breakdown_elite",
        "name": "Scan Breakdown Elite",
        "description": (
            "Short stocks flagged by Scan Overlay Breakdown Elite: "
            "Stage 4, negative RS, high extension below SMA150. R4/R5 only."
        ),
        "strategy_type": "short",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "scan_tier", "operator": "eq", "value": "Breakdown Elite"},
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
    {
        "id": "short_breakdown",
        "name": "Stage 4 Breakdown Short",
        "description": (
            "Short stocks breaking down into Stage 4 during bear regimes; "
            "weak RS (below -1%). Exit on early-stage recovery or R1/R2."
        ),
        "strategy_type": "short",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["4A", "4B"]},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                    {"field": "rs_mansfield_pct", "operator": "lt", "value": -1.0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["1B", "2A"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2"]},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 3.0,
        "max_positions": 5,
        "stop_loss_pct": 10.0,
    },
    {
        "id": "short_stage3_distribution",
        "name": "Stage 3 Distribution Short (Bear)",
        "description": (
            "Short distribution-phase names in R4/R5: Stage 3A/3B with "
            "negative RS and declining SMA150."
        ),
        "strategy_type": "short",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["3A", "3B"]},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                    {"field": "rs_mansfield_pct", "operator": "lt", "value": 0},
                    {"field": "sma150_slope", "operator": "lt", "value": 0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "stage_label", "operator": "in", "value": ["1B", "2A", "2B"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2"]},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 2.5,
        "max_positions": 6,
        "stop_loss_pct": 9.0,
    },
    {
        "id": "short_r5_liquidation",
        "name": "R5 Liquidation Short (4C)",
        "description": (
            "Aggressive short on late Stage 4C in the weakest regime (R5) "
            "with deeply negative RS. Tighter risk; cover on regime or stage lift."
        ),
        "strategy_type": "short",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "stage_label", "operator": "eq", "value": "4C"},
                    {"field": "regime_state", "operator": "eq", "value": "R5"},
                    {"field": "rs_mansfield_pct", "operator": "lt", "value": -5.0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "stage_label", "operator": "not_in", "value": ["4B", "4C"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 2.0,
        "max_positions": 4,
        "stop_loss_pct": 12.0,
    },
    # ── Sector / ETF Templates ────────────────────────────────────
    {
        "id": "sector_rotation",
        "name": "Sector Rotation ETF",
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
        "id": "td_counter_trend",
        "name": "TD Sequential Counter-Trend",
        "description": (
            "Counter-trend entries on TD buy completion: RSI < 40, "
            "not in Stage 4 decline. Long entries only in R1-R3."
        ),
        "strategy_type": "mean_reversion",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "td_buy_complete", "operator": "eq", "value": True},
                    {"field": "rsi_14", "operator": "lt", "value": 40},
                    {"field": "stage_label", "operator": "not_in", "value": ["4A", "4B", "4C"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
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
    # ── TTM Squeeze ───────────────────────────────────────────────
    {
        "id": "ttm_squeeze_stage2_long",
        "name": "TTM Squeeze Stage 2 Long",
        "description": (
            "Enter when volatility squeeze is on (Bollinger inside Keltner) in Stage 2, "
            "positive TTM momentum, RS and SMA150 constructive. R1-R3 only."
        ),
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "ttm_squeeze_on", "operator": "eq", "value": True},
                    {"field": "stage_label", "operator": "in", "value": ["2A", "2B", "2C"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                    {"field": "ttm_momentum", "operator": "gt", "value": 0},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                    {"field": "sma150_slope", "operator": "gt", "value": 0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "ttm_momentum", "operator": "lt", "value": 0},
                    {"field": "stage_label", "operator": "starts_with", "value": "3"},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 4.0,
        "max_positions": 12,
        "stop_loss_pct": 8.0,
    },
    {
        "id": "ttm_squeeze_oversold_long",
        "name": "TTM Squeeze Oversold Long",
        "description": (
            "Squeeze compression with RSI washed out, not in Stage 4, "
            "favorable regimes R1-R3. Exit on momentum flip or squeeze release."
        ),
        "strategy_type": "mean_reversion",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "ttm_squeeze_on", "operator": "eq", "value": True},
                    {"field": "rsi_14", "operator": "lt", "value": 35},
                    {"field": "stage_label", "operator": "not_in", "value": ["4A", "4B", "4C"]},
                    {"field": "regime_state", "operator": "in", "value": ["R1", "R2", "R3"]},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "rsi_14", "operator": "gt", "value": 55},
                    {"field": "ttm_squeeze_on", "operator": "eq", "value": False},
                    {"field": "regime_state", "operator": "in", "value": ["R4", "R5"]},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 3.0,
        "max_positions": 10,
        "stop_loss_pct": 6.0,
        "max_holding_days": 15,
    },
]


def get_template(template_id: str) -> Dict[str, Any] | None:
    return next((t for t in STRATEGY_TEMPLATES if t["id"] == template_id), None)


def list_templates() -> List[Dict[str, Any]]:
    return [
        {k: v for k, v in t.items() if k != "default_config"}
        for t in STRATEGY_TEMPLATES
    ]
