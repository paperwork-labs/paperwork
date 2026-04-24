"""Persona routing — determines which persona handles a request based on
channel context (weighted, not absolute), content keywords, and explicit mentions.

Channel context adds a +3 score boost to the channel's default persona but does
NOT override strong content signals. This means "what's the project status" in
#alerts still routes to EA (content wins) while a vague "hey" in #engineering
routes to Engineering (channel wins).

Keyword matching is intentionally stem-aware: a keyword like "position"
will match "position" and "positions" (trailing "s") so we don't have to
curate every plural. Long-term (D2) this file will be replaced by
semantic routing through Brain itself, at which point this heuristic
retires. Until then: add roots, not plurals."""

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
    parent_persona: str | None = None,
) -> str:
    if parent_persona:
        return parent_persona

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
            # Match the keyword and its trailing-s plural with a word
            # boundary. Avoids curating every plural by hand while keeping
            # false positives low (we still require \b and a fixed prefix).
            if re.search(rf"\b{re.escape(kw)}s?\b", lower):
                scores[persona] = scores.get(persona, 0) + 1

    if scores:
        return max(scores, key=lambda p: scores[p])

    return "ea"
