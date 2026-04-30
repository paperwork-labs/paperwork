"""Expense routing rules — validated load/save with audit history (WS-69 PR O).

medallion: ops
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.expenses import ExpenseRoutingRules, ExpenseRoutingRulesUpdate

_ENV_RULES_JSON = "BRAIN_EXPENSE_RULES_JSON"
_ENV_REPO_ROOT = "REPO_ROOT"


def _brain_root() -> Path:
    here = Path(__file__).resolve()
    return here.parent.parent.parent


def _data_dir() -> Path:
    import os

    env = os.environ.get(_ENV_REPO_ROOT, "").strip()
    if env:
        return Path(env) / "apis" / "brain" / "data"
    return _brain_root() / "data"


def _rules_json_path() -> Path:
    import os

    env = os.environ.get(_ENV_RULES_JSON, "").strip()
    if env:
        return Path(env)
    return _data_dir() / "expense_routing_rules.json"


def _diff_dict(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = set(before) | set(after)
    out: dict[str, Any] = {}
    for k in sorted(keys):
        if before.get(k) != after.get(k):
            out[k] = {"from": before.get(k), "to": after.get(k)}
    return out


def load_rules() -> ExpenseRoutingRules:
    """Load and validate routing rules. Raises on corrupt JSON (no silent fallback)."""
    path = _rules_json_path()
    if not path.exists():
        return ExpenseRoutingRules()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"expense_routing_rules.json is not valid JSON: {exc}") from exc
    return ExpenseRoutingRules.model_validate(raw)


def validate_rules_payload(payload: ExpenseRoutingRulesUpdate) -> None:
    """Re-validate cross-field constraints (overlap, flag vs threshold)."""
    auto_s = set(payload.auto_approve_categories)
    always_s = set(payload.always_review_categories)
    overlap = auto_s & always_s
    if overlap:
        raise ValueError(
            f"Categories cannot appear in both auto-approve and always-review: {sorted(overlap)}"
        )
    if payload.flag_amount_cents_above < payload.auto_approve_threshold_cents:
        raise ValueError("flag_amount_cents_above must be >= auto_approve_threshold_cents")


def save_rules(rules: ExpenseRoutingRules, *, updated_by: str) -> ExpenseRoutingRules:
    """Persist rules, appending a history entry with timestamp + diff before overwrite."""
    path = _rules_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    previous: dict[str, Any] = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Cannot read existing rules file: {exc}") from exc

    now = datetime.now(UTC).isoformat()
    new_dump = rules.model_dump(mode="json")
    # Keys we track in history (tunable routing)
    track_keys = (
        "auto_approve_threshold_cents",
        "auto_approve_categories",
        "always_review_categories",
        "flag_amount_cents_above",
        "founder_card_default_source",
        "subscription_skip_approval",
    )
    before_sub = {k: previous.get(k) for k in track_keys}
    after_sub = {k: new_dump.get(k) for k in track_keys}
    diff = _diff_dict(before_sub, after_sub)
    hist_entry: dict[str, Any] = {
        "at": now,
        "updated_by": updated_by,
        "diff": diff,
    }
    history = list(new_dump.get("history") or [])
    history.append(hist_entry)
    # Cap history in memory/file growth
    if len(history) > 200:
        history = history[-200:]
    new_dump["history"] = history
    new_dump["updated_at"] = now
    new_dump["updated_by"] = updated_by

    validated = ExpenseRoutingRules.model_validate(new_dump)
    path.write_text(
        json.dumps(validated.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return validated


def merge_update(
    current: ExpenseRoutingRules,
    update: ExpenseRoutingRulesUpdate,
) -> ExpenseRoutingRules:
    """Apply an update payload onto current rules (preserves history until save_rules)."""
    validate_rules_payload(update)
    merged = current.model_dump(mode="json")
    merged.update(
        {
            "auto_approve_threshold_cents": update.auto_approve_threshold_cents,
            "auto_approve_categories": list(update.auto_approve_categories),
            "always_review_categories": list(update.always_review_categories),
            "flag_amount_cents_above": update.flag_amount_cents_above,
            "founder_card_default_source": update.founder_card_default_source,
            "subscription_skip_approval": update.subscription_skip_approval,
        }
    )
    return ExpenseRoutingRules.model_validate(merged)
