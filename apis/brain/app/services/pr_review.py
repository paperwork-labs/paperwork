"""Brain PR review pipeline.

This is Brain's executive reviewer. It fetches a PR's metadata and diff,
pulls historical context from memory (prior reviews, related episodes),
sends the bundle to Claude, and posts an honest review.

Design notes:
- Cheap by default (Haiku 4.5) — flip BRAIN_PR_REVIEW_MODEL to escalate for
  critical PRs (e.g. risk_gate, execution, migrations).
- Direct Anthropic call (not via ``llm.py`` complete_with_mcp) because we
  don't need tools here — just structured output. Keeps the path simple and
  auditable.
- Every review is persisted as a memory episode so the next review can
  reason about historical patterns (e.g. "we rejected similar risk_gate
  changes in PR #489 because…").
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings
from app.services import memory
from app.services.pii import scrub_pii
from app.tools import github as gh_tools

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
BIG_MODEL = "claude-sonnet-4-20250514"

# File-path prefixes that warrant escalation to the bigger model.
# Everything in execution/, risk/, migrations, auth, or billing deserves more care.
_CRITICAL_PATHS = (
    "apis/axiomfolio/app/services/execution/",
    "apis/axiomfolio/app/services/gold/risk/",
    "alembic/versions/",
    "apis/brain/app/services/llm.py",
    "apis/brain/app/routers/admin.py",
    "infra/",
    "scripts/medallion/",
)

SYSTEM_PROMPT = """You are Paperwork Labs' executive code reviewer — Brain's persona for PR review.

Your job: give an honest, decisive review. You are NOT a rubber-stamp.
You are the senior engineer who has seen every prior mistake in this repo
and knows which patterns fail in production.

What to check (in priority order):
1. Correctness — does the diff do what the PR title/description claims?
2. Safety — any risk of: data loss, unauthorized access, wrong user_id scoping (D88),
   racing conditions, unbounded loops, circular imports, or medallion-layer violations?
3. Test coverage — are the behaviors under test matched by the changes?
4. Historical patterns — if prior reviews (see context) rejected similar changes,
   call that out explicitly.
5. Strategic fit — does this move us toward revenue / the current sprint? If it's a
   yak-shave, say so.

What to output (strict JSON, no markdown fences, no preamble):
{
  "verdict": "APPROVE" | "COMMENT" | "REQUEST_CHANGES",
  "summary": "2-5 sentence summary of the PR and your overall take.",
  "concerns": ["bullet 1", "bullet 2", ...],
  "strengths": ["bullet 1", ...],
  "suggestions": [
    {"path": "relative/file/path.py", "line": 42, "body": "concrete suggestion"}
  ],
  "strategic_note": "optional: how this fits (or doesn't) with current priorities"
}

Rules:
- APPROVE only when you would merge this yourself. No hedging.
- REQUEST_CHANGES when you'd block this in review. Say why in `concerns`.
- COMMENT when it's net-positive but has non-blocking feedback.
- Inline `suggestions` must reference a file+line IN THE DIFF. Max 6 suggestions.
- Be terse. No filler. No "great work!" unless it genuinely is.
- If the diff is trivial (typo, docstring), just say APPROVE with a one-liner.
"""


def _choose_model(files: list[str]) -> str:
    """Escalate to Sonnet for critical paths or large diffs."""
    override = getattr(settings, "BRAIN_PR_REVIEW_MODEL", "").strip()
    if override:
        return override
    for f in files:
        for prefix in _CRITICAL_PATHS:
            if f.startswith(prefix):
                return BIG_MODEL
    return DEFAULT_MODEL


async def _fetch_historical_context(
    db: Any,
    org_id: str,
    pr_files: list[str],
    max_episodes: int = 4,
) -> str:
    """Pull recent PR-review episodes that touched overlapping paths.

    Returns a compact text block with prior verdicts + summaries. Empty
    string if no relevant history found. Kept small to save tokens.
    """
    if not pr_files:
        return ""
    try:
        recent = await memory.search_episodes(
            db,
            organization_id=org_id,
            query=" ".join(sorted({f.split("/")[0] for f in pr_files})[:6]),
            limit=max_episodes * 3,
            skip_embedding=False,
        )
    except Exception as e:
        logger.debug("Historical context fetch failed (non-fatal): %s", e)
        return ""

    if not recent:
        return ""
    filtered = [
        ep for ep in recent
        if (getattr(ep, "source", "") or "").startswith("brain:pr-review")
    ][:max_episodes]
    if not filtered:
        return ""
    lines: list[str] = ["PRIOR RELATED REVIEWS (for pattern-matching only):"]
    for ep in filtered:
        summary = getattr(ep, "summary", None) or ""
        ts = getattr(ep, "created_at", "")
        lines.append(f"- [{ts}] {summary}"[:400])
    return "\n".join(lines)


async def _call_anthropic(
    *,
    model: str,
    system_prompt: str,
    user_content: str,
    max_tokens: int = 1600,
) -> dict[str, Any]:
    """Direct Anthropic call returning parsed JSON (or {} on failure)."""
    api_key = settings.ANTHROPIC_API_KEY.strip()
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not configured; PR review skipped")
        return {}

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            r = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Anthropic call failed: %s", e)
        return {}
    except (httpx.RequestError, ValueError) as e:
        logger.warning("Anthropic call failed: %s", e)
        return {}

    blocks = data.get("content") or []
    text = ""
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            text += b.get("text", "")

    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError as e:
        logger.warning("Anthropic response was not valid JSON: %s | body=%r", e, text[:400])
    return {}


async def review_pr(db: Any, *, pr_number: int, org_id: str = "paperwork-labs") -> dict[str, Any]:
    """Fetch PR + diff, call Claude, post review, store memory episode.

    Returns a dict with keys: {posted: bool, verdict: str, summary: str, review_id: str}.
    """
    meta_text = await gh_tools.get_github_pr(pr_number)
    if meta_text.startswith("PR #") and "not found" in meta_text:
        return {"posted": False, "error": "pr_not_found", "number": pr_number}

    files = _extract_files(meta_text)
    diff = await gh_tools.get_github_pr_diff(pr_number, max_chars=60000)

    history = await _fetch_historical_context(db, org_id, files)

    model = _choose_model(files)

    user_content = _compose_user_content(
        meta_text=meta_text,
        diff=diff,
        history=history,
    )

    parsed = await _call_anthropic(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_content=user_content,
    )

    if not parsed:
        return {"posted": False, "error": "llm_empty", "number": pr_number}

    verdict = str(parsed.get("verdict") or "COMMENT").upper()
    if verdict not in ("APPROVE", "COMMENT", "REQUEST_CHANGES"):
        verdict = "COMMENT"

    review_body = _format_review_body(parsed, model=model)
    suggestions = parsed.get("suggestions") or []
    if not isinstance(suggestions, list):
        suggestions = []

    post_result = await gh_tools.review_github_pr(
        number=pr_number,
        body=review_body,
        event=verdict,
        comments=suggestions,
    )

    try:
        await memory.store_episode(
            db,
            organization_id=org_id,
            source=f"brain:pr-review:{verdict.lower()}",
            summary=f"PR #{pr_number}: {verdict} — {str(parsed.get('summary') or '')[:200]}",
            full_context=json.dumps({
                "pr_number": pr_number,
                "verdict": verdict,
                "model": model,
                "files": files[:40],
                "review": parsed,
            }, default=str),
            channel="github",
            persona="reviewer",
            product="brain",
            source_ref=str(pr_number),
            importance=0.6 if verdict == "REQUEST_CHANGES" else 0.4,
            metadata={"pr_number": pr_number, "verdict": verdict, "model": model},
        )
    except Exception as e:
        logger.warning("Failed to persist PR review episode: %s", e)

    return {
        "posted": not post_result.startswith(("review_github_pr error", "review_github_pr HTTP")),
        "verdict": verdict,
        "summary": parsed.get("summary", ""),
        "review_result": post_result,
        "model": model,
        "number": pr_number,
    }


# ---- helpers -----------------------------------------------------------------


def _extract_files(meta_text: str) -> list[str]:
    """Parse the `Files:` block out of get_github_pr()'s output."""
    marker = "\nFiles:\n"
    idx = meta_text.find(marker)
    if idx < 0:
        return []
    raw = meta_text[idx + len(marker):]
    files = [ln.strip() for ln in raw.splitlines() if ln.strip() and ln.strip() != "(none listed)"]
    return files


def _compose_user_content(*, meta_text: str, diff: str, history: str) -> str:
    parts: list[str] = []
    parts.append("## PR METADATA\n" + scrub_pii(meta_text))
    if history:
        parts.append("\n## HISTORICAL CONTEXT\n" + scrub_pii(history))
    parts.append("\n## DIFF\n```diff\n" + diff + "\n```")
    parts.append(
        "\nRespond with the strict JSON schema from the system prompt. "
        "Do not include any text outside the JSON object."
    )
    return "\n".join(parts)


def _format_review_body(parsed: dict[str, Any], *, model: str) -> str:
    """Render the JSON review into the markdown body that goes on the PR."""
    summary = str(parsed.get("summary") or "").strip()
    concerns = parsed.get("concerns") or []
    strengths = parsed.get("strengths") or []
    strategic = str(parsed.get("strategic_note") or "").strip()

    lines = ["### 🧠 Brain review", ""]
    if summary:
        lines.append(summary)
        lines.append("")
    if concerns:
        lines.append("**Concerns**")
        for c in concerns[:10]:
            lines.append(f"- {str(c)[:400]}")
        lines.append("")
    if strengths:
        lines.append("**Strengths**")
        for s in strengths[:8]:
            lines.append(f"- {str(s)[:400]}")
        lines.append("")
    if strategic:
        lines.append("**Strategic note**")
        lines.append(strategic)
        lines.append("")
    lines.append(f"<sub>model: `{model}` · generated by Brain</sub>")
    return "\n".join(lines)
