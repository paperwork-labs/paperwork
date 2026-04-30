"""CFO persona — focused expense category classification (WS-69 PR O).

Uses PersonaSpec default_model, enforces daily_cost_ceiling_usd via CostTracker,
and records estimated spend after each successful LLM call.

medallion: ops
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, cast

from app.personas import get_spec
from app.schemas.expenses import ExpenseCategory  # noqa: TC001
from app.services import llm
from app.services.cost_tracker import CostCeilingExceeded, check_ceiling, record_spend
from app.services.router import _provider_for_model

logger = logging.getLogger(__name__)

_CFO_SLUG = "cfo"
_ORG_FALLBACK = "paperwork-labs-expenses"

_VALID: tuple[ExpenseCategory, ...] = (
    "infra",
    "ai",
    "contractors",
    "tools",
    "legal",
    "tax",
    "misc",
    "domains",
    "ops",
)


def _estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    info = llm.get_model_info(model) or {}
    in_m = float(info.get("cost_per_1m_input", 1.0))
    out_m = float(info.get("cost_per_1m_output", 3.0))
    return (tokens_in * in_m + tokens_out * out_m) / 1_000_000.0


def _parse_category_json(content: str) -> tuple[ExpenseCategory, str | None]:
    raw = content.strip()
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    data = json.loads(raw)
    cat = str(data.get("category", "")).strip()
    if cat not in _VALID:
        raise ValueError(f"Invalid category from CFO classifier: {cat!r}")
    reason = data.get("flagged_reason")
    fr = str(reason).strip() if reason is not None else None
    return cast("ExpenseCategory", cat), fr or None


async def classify(
    *,
    amount_cents: int,
    merchant: str,
    description: str,
    organization_id: str = _ORG_FALLBACK,
    redis_client: Any | None = None,
) -> tuple[ExpenseCategory, str | None]:
    """Return (ExpenseCategory, optional flagged_reason). Raises on ceiling or invalid output."""
    spec = get_spec(_CFO_SLUG)
    if spec is None:
        raise RuntimeError("CFO PersonaSpec is not registered — cannot classify expenses")

    await check_ceiling(
        redis_client,
        organization_id=organization_id,
        persona=_CFO_SLUG,
        ceiling_usd=spec.daily_cost_ceiling_usd,
    )

    model = spec.default_model
    provider = _provider_for_model(model)
    cats = ", ".join(_VALID)
    system = (
        f"{spec.tone_prefix or ''}\n\n"
        "You classify a single business expense into exactly one category.\n"
        f"Valid categories: {cats}.\n"
        "Respond with JSON only, no markdown fences, shape:\n"
        '{"category":"<slug>","flagged_reason":null or "short string if suspicious"}\n'
    )
    user = f"merchant: {merchant}\namount_cents: {amount_cents}\ndescription: {description}\n"
    result = await llm.complete_text(
        system_prompt=system.strip(),
        messages=[{"role": "user", "content": user}],
        model=model,
        provider=provider,
        max_tokens=min(spec.max_output_tokens or 512, 512),
        temperature=0.2,
    )
    content = str(result.get("content") or "")
    tokens_in = int(result.get("tokens_in") or 0)
    tokens_out = int(result.get("tokens_out") or 0)
    try:
        category, flagged = _parse_category_json(content)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("cfo_classifier: invalid JSON from model: %s", content[:500])
        raise ValueError(f"CFO classifier returned invalid structured output: {exc}") from exc

    est = _estimate_cost_usd(model, tokens_in, tokens_out)
    await record_spend(
        redis_client,
        organization_id=organization_id,
        persona=_CFO_SLUG,
        amount_usd=est,
    )
    return category, flagged


__all__ = ["CostCeilingExceeded", "classify"]
