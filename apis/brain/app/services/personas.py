"""Persona routing — determines which persona handles a request based on
channel, content keywords, and explicit mentions."""

import re

PERSONA_KEYWORDS: dict[str, list[str]] = {
    "engineering": ["code", "deploy", "api", "bug", "pr", "merge", "build", "test", "lint", "infra", "render", "vercel"],
    "strategy": ["strategy", "roadmap", "planning", "decision", "priority", "phase"],
    "legal": ["legal", "compliance", "efin", "privacy", "disclaimer", "circular 230", "upl"],
    "cfo": ["cost", "spend", "spent", "burn", "budget", "pricing", "revenue", "expense", "subscription"],
    "qa": ["test", "security", "audit", "vulnerability", "pii", "leak"],
    "tax-domain": ["tax", "irs", "w-2", "1040", "mef", "filing", "refund", "deduction", "bracket"],
    "cpa": ["advisory", "tax plan", "client guidance", "cpa"],
    "growth": ["marketing", "seo", "content", "landing page", "viral", "referral", "conversion"],
    "social": ["tiktok", "instagram", "twitter", "post", "reel", "creator", "social media"],
    "partnerships": ["partner", "outreach", "deal", "pipeline", "co-founder"],
    "ux": ["design", "ui", "ux", "mobile", "accessibility", "animation", "component"],
    "agent-ops": ["model", "routing", "persona", "agent", "workflow", "n8n"],
    "ea": ["briefing", "task", "schedule", "weekly", "daily", "what should i"],
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
    for persona, keywords in PERSONA_KEYWORDS.items():
        score = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", lower))
        if score > 0:
            scores[persona] = score

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    return "ea"
