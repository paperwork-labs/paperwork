"""Persona routing — determines which persona handles a request based on
channel, content keywords, and explicit mentions."""

import re

SINGLE_WORD_KEYWORDS: dict[str, list[str]] = {
    "engineering": ["code", "deploy", "api", "bug", "pr", "merge", "build", "test", "lint", "infra", "render", "vercel"],
    "strategy": ["strategy", "roadmap", "planning", "decision", "priority", "phase"],
    "legal": ["legal", "compliance", "efin", "privacy", "disclaimer", "upl"],
    "cfo": ["cost", "spend", "spent", "burn", "budget", "pricing", "revenue", "expense", "subscription"],
    "qa": ["security", "audit", "vulnerability", "pii", "leak"],
    "tax-domain": ["tax", "irs", "1040", "mef", "refund", "deduction", "bracket"],
    "cpa": ["advisory", "cpa"],
    "growth": ["marketing", "seo", "viral", "referral", "conversion"],
    "social": ["tiktok", "instagram", "twitter", "reel", "creator"],
    "partnerships": ["partner", "outreach", "deal", "pipeline"],
    "ux": ["design", "ui", "ux", "accessibility", "animation", "component"],
    "agent-ops": ["model", "routing", "persona", "agent", "workflow", "n8n"],
    "ea": ["briefing", "schedule", "weekly", "daily"],
}

PHRASE_KEYWORDS: dict[str, list[str]] = {
    "legal": ["circular 230"],
    "tax-domain": ["w-2", "filing status"],
    "cpa": ["tax plan", "client guidance"],
    "growth": ["landing page", "content marketing"],
    "social": ["social media"],
    "ea": ["what should i", "work on"],
}

CHANNEL_PERSONA_MAP: dict[str, str] = {
    "C0ALLEKR9FZ": "engineering",
    "C0ALLJWR1HV": "ea",
    "C0AM2310P8A": "strategy",
    "C0AMWB887KJ": "engineering",
    "C0ALVM4PAE7": "engineering",
    "C0AM01NHQ3Y": "ea",
}


def route_persona(
    message: str,
    channel_id: str | None = None,
    parent_persona: str | None = None,
) -> str:
    if parent_persona:
        return parent_persona

    if channel_id and channel_id in CHANNEL_PERSONA_MAP:
        return CHANNEL_PERSONA_MAP[channel_id]

    lower = message.lower()
    scores: dict[str, int] = {}

    for persona, phrases in PHRASE_KEYWORDS.items():
        for phrase in phrases:
            if phrase in lower:
                scores[persona] = scores.get(persona, 0) + 2

    for persona, keywords in SINGLE_WORD_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", lower):
                scores[persona] = scores.get(persona, 0) + 1

    if scores:
        return max(scores, key=lambda p: scores[p])

    return "ea"
