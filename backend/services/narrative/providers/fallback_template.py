"""Template-only narrative when the LLM path is unavailable.

medallion: gold
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, List, Mapping, Optional

from backend.services.narrative.provider import NarrativeResult


def _pct(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.2f}%"


def render_summary_text(summary: Mapping[str, Any]) -> str:
    movers: List[Mapping[str, Any]] = list(summary.get("top_movers") or [])
    val = summary.get("n_movers_over_threshold")
    n_movers = int(val) if val is not None else len(movers)
    top = movers[0] if movers else {}
    top_sym = str(top.get("symbol") or "—")
    top_pct = top.get("day_pnl_pct")
    regime = str(summary.get("regime") or summary.get("regime_state") or "unknown")
    parts = [
        f"Today: {n_movers} of your holdings moved more than 2%; "
        f"{top_sym} led at {_pct(float(top_pct) if top_pct is not None else None)}.",
        f"Macro regime: {regime}.",
    ]
    transitions = summary.get("stage_transitions") or []
    if transitions:
        t0 = transitions[0]
        parts.append(
            f"Stage change: {t0.get('symbol')} {t0.get('from')} → {t0.get('to')}."
        )
    ex = summary.get("ex_dividends") or []
    if ex:
        syms = ", ".join(str(x.get("symbol")) for x in ex[:5])
        parts.append(f"Ex-dividend: {syms}.")
    port = summary.get("portfolio_return_pct")
    spy = summary.get("spy_return_pct")
    if port is not None or spy is not None:
        parts.append(
            f"Portfolio return: {_pct(float(port) if port is not None else None)} "
            f"vs SPY {_pct(float(spy) if spy is not None else None)}."
        )
    return " ".join(parts)


class FallbackTemplateProvider:
    """Rule-based narrative; never raises."""

    def generate(self, prompt: str, *, max_tokens: int = 400) -> NarrativeResult:
        ph = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        text = (
            "Today: your portfolio had notable moves; macro context was unavailable "
            "in the degraded template path."
        )
        return NarrativeResult(
            text=text,
            provider="fallback_template",
            model=None,
            tokens_used=None,
            cost_usd=None,
            is_fallback=True,
            prompt_hash=ph,
        )


def render_from_summary(summary: Mapping[str, Any]) -> NarrativeResult:
    """Build :class:`NarrativeResult` from structured summary (preferred for fallback)."""
    raw = render_summary_text(summary)
    dumped = json.dumps(dict(summary), sort_keys=True, default=str)
    ph = hashlib.sha256(dumped.encode("utf-8")).hexdigest()
    return NarrativeResult(
        text=raw,
        provider="fallback_template",
        model=None,
        tokens_used=None,
        cost_usd=None,
        is_fallback=True,
        prompt_hash=ph,
    )
