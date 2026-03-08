"""Generate trade signals from rule evaluation results."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from backend.models.strategy import Strategy

logger = logging.getLogger(__name__)


class SignalGenerator:
    def generate_signals(
        self, db: Session, strategy: Strategy, matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        for match in matches:
            signal = {
                "strategy_id": strategy.id,
                "symbol": match["symbol"],
                "action": match.get("action", "buy"),
                "strength": match.get("strength", 1.0),
                "context": match.get("context", {}),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            signals.append(signal)
            logger.info(
                "Signal generated: %s %s from strategy %s",
                signal["action"],
                signal["symbol"],
                strategy.name,
            )
        return signals
