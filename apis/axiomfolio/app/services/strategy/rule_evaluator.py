"""Composable rule evaluator for strategy conditions.

Medallion layer: gold. See docs/ARCHITECTURE.md and D127.

medallion: gold
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.models.broker_account import BrokerAccount
from app.services.strategy.account_strategy import get_strategy_profile

logger = logging.getLogger(__name__)


class ConditionOperator(str, Enum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"
    BETWEEN = "between"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    IN = "in"
    NOT_IN = "not_in"
    STARTS_WITH = "starts_with"
    CONTAINS = "contains"


class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"


@dataclass
class Condition:
    field: str  # e.g., "current_price", "rsi_14", "stage", "atr_pct"
    operator: ConditionOperator
    value: Any
    value_high: Any | None = None  # for BETWEEN

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Condition:
        """Parse condition from dict. Validates operator enum."""
        if not isinstance(data, dict):
            raise ValueError(f"Condition must be dict, got {type(data)}")

        field_name = data.get("field", "")
        if not field_name:
            raise ValueError("Condition missing 'field'")

        op_str = data.get("operator", "eq")
        try:
            operator = ConditionOperator(op_str)
        except ValueError:
            raise ValueError(
                f"Invalid operator '{op_str}'. Valid: {[e.value for e in ConditionOperator]}"
            )

        return cls(
            field=field_name,
            operator=operator,
            value=data.get("value"),
            value_high=data.get("value_high"),
        )


@dataclass
class ConditionGroup:
    logic: LogicalOperator = LogicalOperator.AND
    conditions: list[Condition] = field(default_factory=list)
    groups: list[ConditionGroup] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Any) -> ConditionGroup:
        """
        Parse ConditionGroup from JSON-compatible structure.

        Accepts:
        - None/empty: returns empty AND group
        - List of condition dicts: returns AND group with those conditions
        - Dict with logic/conditions/groups: returns full nested structure

        Raises ValueError on invalid input for clear error handling.
        """
        if not data:
            return cls(logic=LogicalOperator.AND, conditions=[], groups=[])

        # List of conditions -> AND group
        if isinstance(data, list):
            conditions = []
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    raise ValueError(f"Condition at index {i} must be dict, got {type(item)}")
                conditions.append(Condition.from_dict(item))
            return cls(logic=LogicalOperator.AND, conditions=conditions, groups=[])

        # Dict with full structure
        if isinstance(data, dict):
            logic_str = data.get("logic", "and")
            try:
                logic = LogicalOperator(logic_str)
            except ValueError:
                raise ValueError(f"Invalid logic '{logic_str}'. Valid: 'and', 'or'")

            conditions = []
            for i, c in enumerate(data.get("conditions", [])):
                try:
                    conditions.append(Condition.from_dict(c))
                except ValueError as e:
                    raise ValueError(f"Invalid condition at index {i}: {e}")

            groups = []
            for i, g in enumerate(data.get("groups", [])):
                try:
                    groups.append(cls.from_json(g))
                except ValueError as e:
                    raise ValueError(f"Invalid group at index {i}: {e}")

            return cls(logic=logic, conditions=conditions, groups=groups)

        raise ValueError(f"ConditionGroup must be list, dict, or None. Got {type(data)}")


@dataclass
class RuleEvalResult:
    matched: bool
    details: dict[str, Any] = field(default_factory=dict)


class RuleEvaluator:
    """Evaluate a ConditionGroup against a context dict (snapshot + position data)."""

    @staticmethod
    def with_account_profile(context: dict[str, Any], account: BrokerAccount) -> dict[str, Any]:
        """Attach account-aware strategy profile to evaluator context (G24)."""
        profile = get_strategy_profile(account)
        out = dict(context)
        out["account_strategy_profile"] = {
            "allow_wash_sale": profile.allow_wash_sale,
            "tax_lot_method": profile.tax_lot_method,
            "max_gain_holding_days_for_ltcg": profile.max_gain_holding_days_for_ltcg,
            "margin_available": profile.margin_available,
            "options_level": profile.options_level,
            "short_allowed": profile.short_allowed,
        }
        return out

    def evaluate(self, group: ConditionGroup, context: dict[str, Any]) -> RuleEvalResult:
        results: list[RuleEvalResult] = []
        for cond in group.conditions:
            results.append(self._eval_condition(cond, context))
        for sub in group.groups:
            results.append(self.evaluate(sub, context))

        if not results:
            return RuleEvalResult(matched=False, details={"reason": "empty_group"})

        if group.logic == LogicalOperator.AND:
            matched = all(r.matched for r in results)
        else:
            matched = any(r.matched for r in results)

        return RuleEvalResult(
            matched=matched,
            details={"sub_results": [{"matched": r.matched, **r.details} for r in results]},
        )

    def _eval_condition(self, cond: Condition, ctx: dict[str, Any]) -> RuleEvalResult:
        actual = ctx.get(cond.field)
        if actual is None:
            return RuleEvalResult(
                matched=False, details={"field": cond.field, "reason": "field_missing"}
            )

        try:
            actual_f = float(actual)
            target_f = float(cond.value)
        except (TypeError, ValueError):
            actual_f = None
            target_f = None

        op = cond.operator
        matched = False

        if op == ConditionOperator.EQ:
            matched = str(actual).lower() == str(cond.value).lower()
        elif op == ConditionOperator.NEQ:
            matched = str(actual).lower() != str(cond.value).lower()
        elif op == ConditionOperator.IN:
            allowed = cond.value if isinstance(cond.value, list) else [cond.value]
            matched = str(actual).upper() in {str(v).upper() for v in allowed}
        elif op == ConditionOperator.NOT_IN:
            blocked = cond.value if isinstance(cond.value, list) else [cond.value]
            matched = str(actual).upper() not in {str(v).upper() for v in blocked}
        elif op == ConditionOperator.STARTS_WITH:
            matched = str(actual).upper().startswith(str(cond.value).upper())
        elif op == ConditionOperator.CONTAINS:
            matched = str(cond.value).upper() in str(actual).upper()
        elif actual_f is not None and target_f is not None:
            if op == ConditionOperator.GT:
                matched = actual_f > target_f
            elif op == ConditionOperator.GTE:
                matched = actual_f >= target_f
            elif op == ConditionOperator.LT:
                matched = actual_f < target_f
            elif op == ConditionOperator.LTE:
                matched = actual_f <= target_f
            elif op == ConditionOperator.BETWEEN and cond.value_high is not None:
                matched = target_f <= actual_f <= float(cond.value_high)
            elif op == ConditionOperator.CROSSES_ABOVE:
                # Crossover detection: prior bar < threshold AND current bar >= threshold
                prev_key = f"{cond.field}_prev"
                prev_val = ctx.get(prev_key)
                if prev_val is not None:
                    try:
                        prev_f = float(prev_val)
                        matched = prev_f < target_f and actual_f >= target_f
                    except (TypeError, ValueError):
                        matched = False
            elif op == ConditionOperator.CROSSES_BELOW:
                # Crossunder detection: prior bar > threshold AND current bar <= threshold
                prev_key = f"{cond.field}_prev"
                prev_val = ctx.get(prev_key)
                if prev_val is not None:
                    try:
                        prev_f = float(prev_val)
                        matched = prev_f > target_f and actual_f <= target_f
                    except (TypeError, ValueError):
                        matched = False

        return RuleEvalResult(
            matched=matched,
            details={
                "field": cond.field,
                "operator": op.value,
                "actual": actual,
                "target": cond.value,
            },
        )
