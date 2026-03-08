"""Composable rule evaluator for strategy conditions."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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


class LogicalOperator(str, Enum):
    AND = "and"
    OR = "or"


@dataclass
class Condition:
    field: str  # e.g., "current_price", "rsi_14", "stage", "atr_pct"
    operator: ConditionOperator
    value: Any
    value_high: Optional[Any] = None  # for BETWEEN


@dataclass
class ConditionGroup:
    logic: LogicalOperator = LogicalOperator.AND
    conditions: List[Condition] = field(default_factory=list)
    groups: List["ConditionGroup"] = field(default_factory=list)


@dataclass
class RuleEvalResult:
    matched: bool
    details: Dict[str, Any] = field(default_factory=dict)


class RuleEvaluator:
    """Evaluate a ConditionGroup against a context dict (snapshot + position data)."""

    def evaluate(self, group: ConditionGroup, context: Dict[str, Any]) -> RuleEvalResult:
        results: List[RuleEvalResult] = []
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

    def _eval_condition(self, cond: Condition, ctx: Dict[str, Any]) -> RuleEvalResult:
        actual = ctx.get(cond.field)
        if actual is None:
            return RuleEvalResult(matched=False, details={"field": cond.field, "reason": "field_missing"})

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

        return RuleEvalResult(
            matched=matched,
            details={"field": cond.field, "operator": op.value, "actual": actual, "target": cond.value},
        )
