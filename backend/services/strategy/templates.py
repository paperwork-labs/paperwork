"""Pre-built hedge fund strategy templates."""
from __future__ import annotations
from typing import Any, Dict, List

STRATEGY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "weinstein_stage2_breakout",
        "name": "Weinstein Stage 2 Breakout",
        "description": "Breakout strategy targeting stocks in Stage 2A/2B with positive RS, above SMA 50, and positive 5-day performance.",
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                    {"field": "perf_5d", "operator": "gt", "value": 0},
                    {"field": "atr_distance", "operator": "gt", "value": 0},
                ],
                "groups": [
                    {
                        "logic": "or",
                        "conditions": [
                            {"field": "stage_label", "operator": "eq", "value": "2A"},
                            {"field": "stage_label", "operator": "eq", "value": "2B"},
                        ],
                        "groups": [],
                    },
                ],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "atr_distance", "operator": "lt", "value": 0},
                ],
                "groups": [
                    {
                        "logic": "or",
                        "conditions": [
                            {"field": "stage_label", "operator": "eq", "value": "3"},
                            {"field": "stage_label", "operator": "eq", "value": "4"},
                        ],
                        "groups": [],
                    },
                ],
            },
        },
        "position_size_pct": 5.0,
        "max_positions": 15,
        "stop_loss_pct": 8.0,
        "universe_filter": {"indices": ["sp500", "nasdaq100"]},
    },
    {
        "id": "momentum_trend_following",
        "name": "Momentum Trend Following",
        "description": "Classic trend-following: price above SMAs, RSI > 50, positive relative strength. Exit on break below EMA 21 with RSI < 40.",
        "strategy_type": "momentum",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "atr_distance", "operator": "gt", "value": 0},
                    {"field": "atr_dist_ema200", "operator": "gt", "value": 0},
                    {"field": "rsi", "operator": "gt", "value": 50},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "atr_dist_ema21", "operator": "lt", "value": 0},
                    {"field": "rsi", "operator": "lt", "value": 40},
                ],
                "groups": [],
            },
        },
        "position_size_pct": 5.0,
        "max_positions": 20,
        "stop_loss_pct": 10.0,
    },
    {
        "id": "mean_reversion_rsi_bounce",
        "name": "Mean Reversion RSI Bounce",
        "description": "Buy oversold bounces: RSI < 30, price above SMA 200, not in Stage 4. Exit on RSI > 70 or 5-day gain > 5%.",
        "strategy_type": "mean_reversion",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "rsi", "operator": "lt", "value": 30},
                    {"field": "atr_dist_ema200", "operator": "gt", "value": 0},
                    {"field": "stage_label", "operator": "neq", "value": "4"},
                ],
                "groups": [],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "rsi", "operator": "gt", "value": 70},
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
    {
        "id": "pullback_buy_zone",
        "name": "Pullback Buy Zone",
        "description": "Buy pullbacks in Stage 2: price pulls back toward EMA 21 (atr_dist_ema21 < -0.5) with positive RS. Exit on extended move or stage change.",
        "strategy_type": "breakout",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "atr_dist_ema21", "operator": "lt", "value": -0.5},
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 0},
                ],
                "groups": [
                    {
                        "logic": "or",
                        "conditions": [
                            {"field": "stage_label", "operator": "eq", "value": "2A"},
                            {"field": "stage_label", "operator": "eq", "value": "2B"},
                            {"field": "stage_label", "operator": "eq", "value": "2C"},
                        ],
                        "groups": [],
                    },
                ],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "atr_dist_ema21", "operator": "gt", "value": 2.0},
                ],
                "groups": [
                    {
                        "logic": "or",
                        "conditions": [
                            {"field": "stage_label", "operator": "eq", "value": "3"},
                            {"field": "stage_label", "operator": "eq", "value": "4"},
                        ],
                        "groups": [],
                    },
                ],
            },
        },
        "position_size_pct": 4.0,
        "max_positions": 15,
        "stop_loss_pct": 7.0,
    },
    {
        "id": "sector_rotation_etf",
        "name": "Sector Rotation ETF",
        "description": "Momentum on sector ETFs: top quartile RS (rs_mansfield_pct > 5), Stage 2, above SMA 50. Universe: ETFs only.",
        "strategy_type": "momentum",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "rs_mansfield_pct", "operator": "gt", "value": 5},
                    {"field": "atr_distance", "operator": "gt", "value": 0},
                ],
                "groups": [
                    {
                        "logic": "or",
                        "conditions": [
                            {"field": "stage_label", "operator": "eq", "value": "2A"},
                            {"field": "stage_label", "operator": "eq", "value": "2B"},
                        ],
                        "groups": [],
                    },
                ],
            },
            "exit_rules": {
                "logic": "or",
                "conditions": [
                    {"field": "rs_mansfield_pct", "operator": "lt", "value": 0},
                ],
                "groups": [
                    {
                        "logic": "or",
                        "conditions": [
                            {"field": "stage_label", "operator": "eq", "value": "3"},
                            {"field": "stage_label", "operator": "eq", "value": "4"},
                        ],
                        "groups": [],
                    },
                ],
            },
        },
        "position_size_pct": 10.0,
        "max_positions": 10,
        "universe_filter": {"asset_type": "etf"},
    },
    {
        "id": "td_sequential_counter_trend",
        "name": "TD Sequential Counter-Trend",
        "description": "Counter-trend entries on TD buy completion: td_buy_complete true, RSI < 40, not Stage 4. Quick exit on TD sell or 5d gain > 3%.",
        "strategy_type": "mean_reversion",
        "default_config": {
            "entry_rules": {
                "logic": "and",
                "conditions": [
                    {"field": "td_buy_complete", "operator": "eq", "value": True},
                    {"field": "rsi", "operator": "lt", "value": 40},
                    {"field": "stage_label", "operator": "neq", "value": "4"},
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
