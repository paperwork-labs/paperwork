"""Exit-cascade planning context helpers (G24 wiring point).

medallion: gold
"""

from __future__ import annotations

from typing import Any, Dict

from app.models.broker_account import BrokerAccount
from app.services.gold.strategy.account_strategy import get_strategy_profile


def build_exit_planner_context(account: BrokerAccount) -> Dict[str, Any]:
    """Build strategy context injected into exit-cascade evaluation."""
    profile = get_strategy_profile(account)
    return {
        "account_strategy_profile": {
            "allow_wash_sale": profile.allow_wash_sale,
            "tax_lot_method": profile.tax_lot_method,
            "max_gain_holding_days_for_ltcg": profile.max_gain_holding_days_for_ltcg,
            "margin_available": profile.margin_available,
            "options_level": profile.options_level,
            "short_allowed": profile.short_allowed,
        }
    }
