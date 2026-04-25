"""Keyword + channel persona router.

Moved from ``app/services/personas.py`` in Track F / H11 of the Infra &
Automation Hardening Sprint so every persona-related module lives under one
package. The old path (``app.services.personas``) re-exports everything here
as a shim for one release cycle, then gets deleted.

Channel context adds a +3 score boost to the channel's default persona but
does NOT override strong content signals. This means "what's the project
status" in #alerts still routes to EA (content wins) while a vague "hey" in
#engineering routes to Engineering (channel wins).

Keyword matching is intentionally stem-aware: a keyword like "position" will
match "position" and "positions" (trailing "s") so we don't have to curate
every plural. Long-term (D2) this module is replaced by semantic routing
through Brain itself, at which point this heuristic retires. Until then:
add roots, not plurals.
"""

from __future__ import annotations

import re

CHANNEL_BOOST = 3

SINGLE_WORD_KEYWORDS: dict[str, list[str]] = {
    "engineering": [
        "code",
        "deploy",
        "api",
        "bug",
        "pr",
        "merge",
        "build",
        "test",
        "lint",
        "infra",
        "render",
        "vercel",
    ],
    "strategy": ["strategy", "roadmap", "planning", "decision", "priority", "phase"],
    "legal": ["legal", "compliance", "efin", "privacy", "disclaimer", "upl"],
    "cfo": [
        "cost",
        "spend",
        "spent",
        "burn",
        "budget",
        "pricing",
        "revenue",
        "expense",
        "subscription",
    ],
    "qa": ["security", "audit", "vulnerability", "pii", "leak"],
    "tax-domain": ["tax", "irs", "1040", "mef", "refund", "deduction", "bracket"],
    "cpa": ["advisory", "cpa"],
    "growth": ["marketing", "seo", "viral", "referral", "conversion"],
    "social": ["tiktok", "instagram", "twitter", "reel", "creator"],
    "partnerships": ["partner", "outreach", "deal", "pipeline"],
    "ux": ["design", "ui", "ux", "accessibility", "animation", "component"],
    "agent-ops": ["model", "routing", "persona", "agent", "workflow", "n8n"],
    "ea": ["briefing", "schedule", "weekly", "daily", "status", "progress", "update"],
    "trading": [
        "trade", "stock", "portfolio", "position", "stage", "regime",
        "scan", "breakout", "stop", "entry", "exit", "order", "buy",
        "sell", "short", "cover", "pnl", "risk", "circuit",
    ],
    # Additions (Track F): previously orphan mdc entries — now routable.
    "brand": ["brand", "branding", "logo", "identity", "voice", "tone"],
    "infra-ops": ["incident", "runbook", "oncall", "pager", "outage"],
}

PHRASE_KEYWORDS: dict[str, list[str]] = {
    "legal": ["circular 230"],
    "tax-domain": ["w-2", "filing status"],
    "cpa": ["tax plan", "client guidance"],
    "growth": ["landing page", "content marketing"],
    "social": ["social media"],
    "ea": ["what should i", "work on", "project status", "how are we", "what's next"],
    "trading": [
        "stop loss", "take profit", "market regime", "stage analysis",
        "risk gate", "circuit breaker",
    ],
    "infra-ops": ["post mortem", "postmortem"],
}

CHANNEL_PERSONA_MAP: dict[str, str] = {
    "C0ALLEKR9FZ": "engineering",   # #engineering
    "C0ALLJWR1HV": "ea",            # #daily-briefing
    "C0AM2310P8A": "strategy",      # #decisions
    "C0AMWB887KJ": "engineering",   # #filing-engine
    "C0ALVM4PAE7": "engineering",   # #alerts
    "C0AM01NHQ3Y": "ea",            # #general
    "C0AMEQV199P": "ea",            # #all-paperwork-labs
    "C0AMJTZRVA6": "engineering",   # #deployment
    "C0AM014DFL6": "ea",            # #weekly-plan
    "C0ALVG3EW1Z": "social",        # #social-content
    "C0APN01LDJN": "cpa",           # #tax-insights
    "C0APFJSDB6X": "trading",       # #trading
}


def route_persona(
    message: str,
    channel_id: str | None = None,
    persona_pin: str | None = None,
) -> str:
    """Pick a persona for ``message``.

    ``persona_pin`` (Track F rename of ``parent_persona``) short-circuits the
    heuristic: if the caller already knows the persona (n8n, tool invocation,
    explicit Slack ``/persona`` command) we trust it.
    """
    if persona_pin:
        return persona_pin

    lower = message.lower()
    scores: dict[str, int] = {}

    if channel_id and channel_id in CHANNEL_PERSONA_MAP:
        channel_persona = CHANNEL_PERSONA_MAP[channel_id]
        scores[channel_persona] = scores.get(channel_persona, 0) + CHANNEL_BOOST

    for persona, phrases in PHRASE_KEYWORDS.items():
        for phrase in phrases:
            if phrase in lower:
                scores[persona] = scores.get(persona, 0) + 2

    for persona, keywords in SINGLE_WORD_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}s?\b", lower):
                scores[persona] = scores.get(persona, 0) + 1

    if scores:
        return max(scores, key=lambda p: scores[p])

    return "ea"
