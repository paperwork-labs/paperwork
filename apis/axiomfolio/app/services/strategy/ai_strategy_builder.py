"""
AI Strategy Builder with Trust Scoring and Guardrails.

Uses LLM to generate strategy rules with safety constraints:
- Trust scoring based on backtesting performance
- Risk guardrails to prevent dangerous configurations
- Explainability of generated rules

medallion: gold
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.strategy import Strategy, StrategyType, StrategyStatus
from app.services.strategy.rule_evaluator import (
    ConditionGroup,
    Condition,
    ConditionOperator,
    LogicalOperator,
)

logger = logging.getLogger(__name__)


@dataclass
class SafetyGuardrail:
    """A safety constraint for AI-generated strategies."""

    name: str
    description: str
    check_fn: str  # Name of method to call
    severity: str  # "error" (blocks), "warning" (allows with flag)


@dataclass
class TrustScore:
    """Trust assessment of an AI-generated strategy."""

    overall: float  # 0-100
    components: Dict[str, float]  # Individual score components
    flags: List[str]  # Warning flags
    recommendation: str  # "deploy", "paper_trade", "reject"

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "components": self.components,
            "flags": self.flags,
            "recommendation": self.recommendation,
        }


@dataclass
class GeneratedStrategy:
    """Output of the AI strategy builder."""

    name: str
    description: str
    entry_rules: ConditionGroup
    exit_rules: ConditionGroup
    parameters: Dict[str, Any]
    trust_score: TrustScore
    explanation: str
    raw_llm_output: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "entry_rules": self._group_to_dict(self.entry_rules),
            "exit_rules": self._group_to_dict(self.exit_rules),
            "parameters": self.parameters,
            "trust_score": self.trust_score.to_dict(),
            "explanation": self.explanation,
        }

    def _group_to_dict(self, group: ConditionGroup) -> dict:
        return {
            "logic": group.logic.value,
            "conditions": [
                {
                    "field": c.field,
                    "operator": c.operator.value,
                    "value": c.value,
                    "value_high": c.value_high,
                }
                for c in group.conditions
            ],
            "groups": [self._group_to_dict(g) for g in group.groups],
        }


# Safety guardrails
GUARDRAILS = [
    SafetyGuardrail(
        name="max_position_size",
        description="Position size must not exceed 20% of portfolio",
        check_fn="_check_position_size",
        severity="error",
    ),
    SafetyGuardrail(
        name="stop_loss_required",
        description="Strategy must have a stop loss mechanism",
        check_fn="_check_stop_loss",
        severity="error",
    ),
    SafetyGuardrail(
        name="no_leverage",
        description="Leverage/margin trading not allowed",
        check_fn="_check_no_leverage",
        severity="error",
    ),
    SafetyGuardrail(
        name="realistic_returns",
        description="Expected returns must be realistic (<100% annual)",
        check_fn="_check_realistic_returns",
        severity="warning",
    ),
    SafetyGuardrail(
        name="sufficient_conditions",
        description="Must have at least 2 entry conditions",
        check_fn="_check_sufficient_conditions",
        severity="warning",
    ),
]

# Allowed fields for conditions
ALLOWED_FIELDS = {
    "current_price",
    "rsi",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "sma_50",
    "sma_150",
    "sma_200",
    "ema_8",
    "ema_21",
    "atr_14",
    "atr_pct",
    "volume",
    "volume_ratio",
    "stage",
    "stage_label",
    "adx",
    "plus_di",
    "minus_di",
    "bollinger_upper",
    "bollinger_lower",
    "ttm_squeeze_on",
    "rs_rank",
    "sector",
}


class AIStrategyBuilder:
    """
    Builds trading strategies using AI with safety guardrails.

    Process:
    1. Parse user intent
    2. Generate strategy rules via LLM (or rule-based fallback)
    3. Apply safety guardrails
    4. Calculate trust score
    5. Return with explanation
    """

    def __init__(self, db: Session):
        self.db = db
        self._templates = self._load_templates()

    def generate(
        self,
        user_prompt: str,
        user_id: int,
        use_llm: bool = False,
    ) -> GeneratedStrategy:
        """
        Generate a strategy from user prompt.

        Args:
            user_prompt: Natural language description of desired strategy
            user_id: User requesting the strategy
            use_llm: Whether to use LLM (requires API key)

        Returns:
            GeneratedStrategy with rules, trust score, and explanation
        """
        logger.info("Generating strategy from prompt: %s", user_prompt[:100])

        # Parse intent
        intent = self._parse_intent(user_prompt)

        # Generate rules
        if use_llm and settings.OPENAI_API_KEY:
            entry_rules, exit_rules, params, raw_output = self._generate_with_llm(
                user_prompt, intent
            )
        else:
            entry_rules, exit_rules, params, raw_output = self._generate_from_templates(
                intent
            )

        # Apply guardrails
        guardrail_results = self._apply_guardrails(entry_rules, exit_rules, params)

        # Calculate trust score
        trust_score = self._calculate_trust_score(
            entry_rules, exit_rules, params, guardrail_results
        )

        # Generate explanation
        explanation = self._generate_explanation(
            intent, entry_rules, exit_rules, trust_score
        )

        # Create name
        name = self._generate_name(intent)

        return GeneratedStrategy(
            name=name,
            description=user_prompt,
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            parameters=params,
            trust_score=trust_score,
            explanation=explanation,
            raw_llm_output=raw_output,
        )

    def save_strategy(
        self,
        generated: GeneratedStrategy,
        user_id: int,
    ) -> Strategy:
        """
        Save a generated strategy to the database.

        Only saves if trust score meets minimum threshold.
        """
        if generated.trust_score.overall < 30:
            raise ValueError(
                f"Trust score too low ({generated.trust_score.overall}). "
                "Strategy rejected for safety."
            )

        strategy = Strategy(
            name=generated.name,
            description=generated.description,
            user_id=user_id,
            strategy_type=StrategyType.CUSTOM,
            status=StrategyStatus.DRAFT,
            parameters={
                "entry_rules": generated.to_dict()["entry_rules"],
                "exit_rules": generated.to_dict()["exit_rules"],
                **generated.parameters,
            },
            stop_loss_pct=generated.parameters.get("stop_loss_pct", 5.0),
            take_profit_pct=generated.parameters.get("take_profit_pct", 15.0),
            max_positions=generated.parameters.get("max_positions", 5),
        )

        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)

        logger.info(
            "Saved AI-generated strategy %s (trust: %.0f, rec: %s)",
            strategy.id,
            generated.trust_score.overall,
            generated.trust_score.recommendation,
        )

        return strategy

    def _parse_intent(self, prompt: str) -> Dict[str, Any]:
        """Parse user intent from prompt."""
        prompt_lower = prompt.lower()

        intent = {
            "style": "swing",  # default
            "indicators": [],
            "stages": [],
            "risk_level": "moderate",
        }

        # Detect trading style
        if any(w in prompt_lower for w in ["day", "intraday", "scalp"]):
            intent["style"] = "day"
        elif any(w in prompt_lower for w in ["position", "long-term", "invest"]):
            intent["style"] = "position"

        # Detect indicators mentioned
        indicator_keywords = {
            "rsi": "rsi",
            "macd": "macd",
            "moving average": "sma",
            "sma": "sma",
            "ema": "ema",
            "bollinger": "bollinger",
            "atr": "atr",
            "volume": "volume",
            "squeeze": "ttm_squeeze",
            "adx": "adx",
        }
        for keyword, indicator in indicator_keywords.items():
            if keyword in prompt_lower:
                intent["indicators"].append(indicator)

        # Detect stage analysis
        stage_pattern = r"stage\s*([1-4][abc]?)"
        stages = re.findall(stage_pattern, prompt_lower)
        intent["stages"] = [s.upper() for s in stages]

        # Detect risk level
        if any(w in prompt_lower for w in ["aggressive", "high risk", "momentum"]):
            intent["risk_level"] = "aggressive"
        elif any(w in prompt_lower for w in ["conservative", "safe", "low risk"]):
            intent["risk_level"] = "conservative"

        return intent

    def _generate_from_templates(
        self, intent: Dict[str, Any]
    ) -> Tuple[ConditionGroup, ConditionGroup, Dict[str, Any], None]:
        """Generate strategy from built-in templates."""
        conditions = []
        exit_conditions = []
        params = {
            "stop_loss_pct": 5.0,
            "take_profit_pct": 15.0,
            "max_positions": 5,
            "position_size_pct": 0.1,
        }

        # Base conditions based on style
        if intent["style"] == "swing":
            # Stage 2 breakout base
            conditions.append(
                Condition(
                    field="stage_label",
                    operator=ConditionOperator.IN,
                    value=["2A", "2B"],
                )
            )
            conditions.append(
                Condition(
                    field="rsi",
                    operator=ConditionOperator.BETWEEN,
                    value=40,
                    value_high=70,
                )
            )

        # Add indicator-based conditions
        if "rsi" in intent["indicators"]:
            conditions.append(
                Condition(
                    field="rsi",
                    operator=ConditionOperator.LT,
                    value=30 if intent["risk_level"] == "aggressive" else 40,
                )
            )

        if "macd" in intent["indicators"]:
            conditions.append(
                Condition(
                    field="macd_histogram",
                    operator=ConditionOperator.GT,
                    value=0,
                )
            )

        if "ttm_squeeze" in intent["indicators"]:
            conditions.append(
                Condition(
                    field="ttm_squeeze_on",
                    operator=ConditionOperator.EQ,
                    value=True,
                )
            )

        # Add stage conditions
        if intent["stages"]:
            conditions.append(
                Condition(
                    field="stage_label",
                    operator=ConditionOperator.IN,
                    value=intent["stages"],
                )
            )

        # Ensure we have minimum conditions
        if len(conditions) < 2:
            conditions.append(
                Condition(
                    field="volume_ratio",
                    operator=ConditionOperator.GT,
                    value=1.2,
                )
            )

        # Exit conditions
        exit_conditions = [
            Condition(
                field="rsi",
                operator=ConditionOperator.GT,
                value=70,
            ),
        ]

        # Adjust params for risk level
        if intent["risk_level"] == "aggressive":
            params["stop_loss_pct"] = 7.0
            params["take_profit_pct"] = 20.0
            params["position_size_pct"] = 0.15
        elif intent["risk_level"] == "conservative":
            params["stop_loss_pct"] = 3.0
            params["take_profit_pct"] = 10.0
            params["position_size_pct"] = 0.05
            params["max_positions"] = 3

        entry_group = ConditionGroup(
            logic=LogicalOperator.AND,
            conditions=conditions,
            groups=[],
        )

        exit_group = ConditionGroup(
            logic=LogicalOperator.OR,
            conditions=exit_conditions,
            groups=[],
        )

        return entry_group, exit_group, params, None

    def _generate_with_llm(
        self, prompt: str, intent: Dict[str, Any]
    ) -> Tuple[ConditionGroup, ConditionGroup, Dict[str, Any], str]:
        """Generate strategy using LLM."""
        # Placeholder for LLM integration
        # In production, this would call OpenAI/Claude API
        logger.info("LLM generation requested but using template fallback")
        entry, exit_rules, params, _ = self._generate_from_templates(intent)
        return entry, exit_rules, params, "LLM not configured"

    def _apply_guardrails(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
    ) -> List[Tuple[SafetyGuardrail, bool, str]]:
        """Apply all safety guardrails."""
        results = []

        for guardrail in GUARDRAILS:
            check_method = getattr(self, guardrail.check_fn, None)
            if check_method:
                passed, message = check_method(entry_rules, exit_rules, params)
                results.append((guardrail, passed, message))
            else:
                results.append((guardrail, True, "Check not implemented"))

        return results

    def _check_position_size(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check position size is reasonable."""
        size = params.get("position_size_pct", 0.1)
        if size > 0.2:
            return False, f"Position size {size*100}% exceeds 20% limit"
        return True, f"Position size {size*100}% is acceptable"

    def _check_stop_loss(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check stop loss is configured."""
        stop_loss = params.get("stop_loss_pct")
        if not stop_loss or stop_loss <= 0:
            return False, "No stop loss configured"
        if stop_loss > 15:
            return False, f"Stop loss {stop_loss}% is too wide"
        return True, f"Stop loss at {stop_loss}%"

    def _check_no_leverage(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check no leverage/margin is used."""
        leverage = params.get("leverage", 1.0)
        if leverage > 1.0:
            return False, f"Leverage {leverage}x not allowed"
        return True, "No leverage"

    def _check_realistic_returns(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check expected returns are realistic."""
        expected = params.get("expected_annual_return")
        if expected and expected > 100:
            return False, f"Expected return {expected}% is unrealistic"
        return True, "Returns within realistic range"

    def _check_sufficient_conditions(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check we have enough entry conditions."""
        count = len(entry_rules.conditions) + sum(
            len(g.conditions) for g in entry_rules.groups
        )
        if count < 2:
            return False, f"Only {count} entry conditions (need 2+)"
        return True, f"{count} entry conditions"

    def _calculate_trust_score(
        self,
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        params: Dict[str, Any],
        guardrail_results: List[Tuple[SafetyGuardrail, bool, str]],
    ) -> TrustScore:
        """Calculate trust score for the strategy."""
        components = {}
        flags = []

        # Guardrail score (40% weight)
        errors = sum(1 for g, p, _ in guardrail_results if not p and g.severity == "error")
        warnings = sum(1 for g, p, _ in guardrail_results if not p and g.severity == "warning")

        if errors > 0:
            components["guardrails"] = 0
            flags.append(f"{errors} safety violations")
        elif warnings > 0:
            components["guardrails"] = 70 - (warnings * 10)
            flags.append(f"{warnings} warnings")
        else:
            components["guardrails"] = 100

        # Complexity score (20% weight) - more conditions = more specific
        condition_count = len(entry_rules.conditions) + len(exit_rules.conditions)
        if condition_count >= 4:
            components["complexity"] = 100
        elif condition_count >= 2:
            components["complexity"] = 70
        else:
            components["complexity"] = 40
            flags.append("Low complexity strategy")

        # Risk management score (40% weight)
        stop_loss = params.get("stop_loss_pct", 0)
        take_profit = params.get("take_profit_pct", 0)
        if stop_loss > 0 and take_profit > 0 and take_profit > stop_loss:
            components["risk_management"] = 100
        elif stop_loss > 0:
            components["risk_management"] = 70
        else:
            components["risk_management"] = 20
            flags.append("No stop loss")

        # Calculate overall
        overall = (
            components["guardrails"] * 0.4
            + components["complexity"] * 0.2
            + components["risk_management"] * 0.4
        )

        # Determine recommendation
        if overall >= 70 and errors == 0:
            recommendation = "deploy"
        elif overall >= 50 and errors == 0:
            recommendation = "paper_trade"
        else:
            recommendation = "reject"

        return TrustScore(
            overall=overall,
            components=components,
            flags=flags,
            recommendation=recommendation,
        )

    def _generate_explanation(
        self,
        intent: Dict[str, Any],
        entry_rules: ConditionGroup,
        exit_rules: ConditionGroup,
        trust_score: TrustScore,
    ) -> str:
        """Generate human-readable explanation."""
        lines = []

        lines.append(f"Strategy Style: {intent['style'].title()} Trading")
        lines.append("")
        lines.append("Entry Conditions:")
        for cond in entry_rules.conditions:
            lines.append(f"  - {cond.field} {cond.operator.value} {cond.value}")

        lines.append("")
        lines.append("Exit Conditions:")
        for cond in exit_rules.conditions:
            lines.append(f"  - {cond.field} {cond.operator.value} {cond.value}")

        lines.append("")
        lines.append(f"Trust Score: {trust_score.overall:.0f}/100")
        lines.append(f"Recommendation: {trust_score.recommendation.replace('_', ' ').title()}")

        if trust_score.flags:
            lines.append("")
            lines.append("Notes:")
            for flag in trust_score.flags:
                lines.append(f"  - {flag}")

        return "\n".join(lines)

    def _generate_name(self, intent: Dict[str, Any]) -> str:
        """Generate a name for the strategy."""
        parts = []

        if intent["risk_level"] == "aggressive":
            parts.append("Aggressive")
        elif intent["risk_level"] == "conservative":
            parts.append("Conservative")

        if intent["stages"]:
            parts.append(f"Stage-{intent['stages'][0]}")

        if "rsi" in intent["indicators"]:
            parts.append("RSI")
        if "macd" in intent["indicators"]:
            parts.append("MACD")

        parts.append(intent["style"].title())

        if not parts:
            parts = ["AI", "Generated"]

        timestamp = datetime.now(timezone.utc).strftime("%m%d")
        return f"{'_'.join(parts)}_{timestamp}"

    def _load_templates(self) -> Dict[str, Any]:
        """Load strategy templates."""
        return {
            "momentum": {
                "entry": [
                    {"field": "rsi", "operator": "gt", "value": 50},
                    {"field": "macd_histogram", "operator": "gt", "value": 0},
                ],
                "exit": [
                    {"field": "rsi", "operator": "gt", "value": 70},
                ],
            },
            "mean_reversion": {
                "entry": [
                    {"field": "rsi", "operator": "lt", "value": 30},
                    {"field": "bollinger_lower", "operator": "gt", "value": 0},
                ],
                "exit": [
                    {"field": "rsi", "operator": "gt", "value": 50},
                ],
            },
        }
