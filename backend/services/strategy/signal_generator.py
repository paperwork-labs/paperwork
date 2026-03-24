"""Generate trade signals from rule evaluation results."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from backend.models.strategy import Strategy

logger = logging.getLogger(__name__)


class SignalGenerator:
    _V4_CONTEXT_FIELDS = (
        "regime_state", "regime_multiplier", "scan_tier", "action_label",
        "stage_label", "ext_pct", "ema10_dist_n", "sma150_slope",
    )

    def generate_signals(
        self, db: Session, strategy: Strategy, matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for match in matches:
            ctx = match.get("context", {})
            v4_ctx = {k: match.get(k) for k in self._V4_CONTEXT_FIELDS if match.get(k) is not None}
            if v4_ctx:
                ctx = {**ctx, "v4": v4_ctx}

            signal = {
                "strategy_id": strategy.id,
                "symbol": match["symbol"],
                "action": match.get("action", "buy"),
                "strength": match.get("strength", 1.0),
                "context": ctx,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            signals.append(signal)
            logger.info(
                "Signal generated: %s %s from strategy %s (regime=%s, tier=%s)",
                signal["action"],
                signal["symbol"],
                strategy.name,
                v4_ctx.get("regime_state", "?"),
                v4_ctx.get("scan_tier", "?"),
            )
        return signals
