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
  changes in PR #489 because…") and so ``sweep_open_prs`` can skip PRs it
  has already reviewed at the current head SHA.

Architecture note: Brain drives this itself — via chat, MCP, or the admin
sweep endpoint. There is deliberately no external cron or GitHub Actions
webhook pinging this module; Brain's agent loop + memory + GitHub tools are
sufficient, and the webhook was redundant state.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.episode import Episode
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


async def review_pr(
    db: AsyncSession, *, pr_number: int, org_id: str = "paperwork-labs"
) -> dict[str, Any]:
    """Fetch PR + diff, call Claude, post review, store memory episode.

    Returns a dict with keys: {posted: bool, verdict: str, summary: str, review_id: str}.
    """
    meta_text = await gh_tools.get_github_pr(pr_number)
    if meta_text.startswith("PR #") and "not found" in meta_text:
        return {"posted": False, "error": "pr_not_found", "number": pr_number}

    head_sha = await _fetch_head_sha(pr_number)
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
                "head_sha": head_sha,
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
            metadata={
                "pr_number": pr_number,
                "head_sha": head_sha,
                "verdict": verdict,
                "model": model,
            },
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
        "head_sha": head_sha,
    }


# ---- sweep: Brain's autonomous "review everything new" loop ------------------


# Labels that tell Brain to stay out. Dependabot bumps have their own Haiku
# triage pipeline (see docs/DEPENDABOT.md), so we skip the whole "dependencies"
# family by default.
_SKIP_LABELS = frozenset({
    "skip-brain-review",
    "deps:major",
    "dependencies",
    "do-not-merge",
})

_SKIP_AUTHORS = frozenset({
    "dependabot[bot]",
    "dependabot-preview[bot]",
    "renovate[bot]",
    "github-actions[bot]",
})


async def sweep_open_prs(
    db: AsyncSession,
    *,
    org_id: str = "paperwork-labs",
    limit: int = 30,
    force: bool = False,
) -> dict[str, Any]:
    """Find open PRs Brain hasn't reviewed yet at their current head SHA, review them.

    This is Brain's self-driven review loop. Called from:
    - the agent loop (e.g. user says "review open PRs")
    - the MCP tool ``brain_sweep_open_prs``
    - the admin endpoint ``POST /api/v1/admin/pr-sweep``
    - a cron / scheduler that hits the admin endpoint (optional)

    Memory is the source of truth for "has this been reviewed at this SHA?".
    No external bookkeeping — just a Postgres query.

    Returns a report: ``{reviewed: [numbers], skipped: [{number, reason}], errors: [...]}``.
    """
    owner, repo = _repo_parts_from_settings()

    prs = await _list_open_prs(owner, repo, limit=limit)
    reviewed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for pr in prs:
        number = int(pr.get("number", 0))
        if not number:
            continue

        author = ((pr.get("user") or {}).get("login") or "").strip()
        if author in _SKIP_AUTHORS:
            skipped.append({"number": number, "reason": f"skip author: {author}"})
            continue

        labels = {
            (lbl.get("name") or "").strip()
            for lbl in (pr.get("labels") or [])
            if isinstance(lbl, dict)
        }
        blocking = labels & _SKIP_LABELS
        if blocking:
            skipped.append({"number": number, "reason": f"skip label(s): {sorted(blocking)}"})
            continue

        if pr.get("draft"):
            skipped.append({"number": number, "reason": "draft"})
            continue

        head_sha = str(((pr.get("head") or {}).get("sha") or "")).strip()
        if not head_sha:
            skipped.append({"number": number, "reason": "no head SHA"})
            continue

        if not force and await _has_review_at_sha(db, org_id=org_id, pr_number=number, head_sha=head_sha):
            skipped.append({"number": number, "reason": f"already reviewed at {head_sha[:7]}"})
            continue

        try:
            result = await review_pr(db, pr_number=number, org_id=org_id)
            if result.get("posted"):
                reviewed.append({"number": number, "verdict": result.get("verdict")})
            else:
                errors.append({"number": number, "error": result.get("error", "unknown")})
        except Exception as e:
            logger.exception("sweep_open_prs: review_pr failed for #%s", number)
            errors.append({"number": number, "error": str(e)[:200]})

    logger.info(
        "sweep_open_prs complete: reviewed=%d skipped=%d errors=%d",
        len(reviewed),
        len(skipped),
        len(errors),
    )
    return {
        "reviewed": reviewed,
        "skipped": skipped,
        "errors": errors,
        "scanned": len(prs),
    }


# ---- helpers for sweep -------------------------------------------------------


def _repo_parts_from_settings() -> tuple[str, str]:
    raw = (settings.GITHUB_REPO or "").strip()
    parts = raw.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("GITHUB_REPO must be 'owner/repo'")
    return parts[0], parts[1]


async def _list_open_prs(owner: str, repo: str, *, limit: int) -> list[dict[str, Any]]:
    """Raw /pulls list — needs head.sha and labels, which ``list_github_prs`` doesn't surface."""
    capped = max(1, min(limit, 100))
    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        headers=headers,
        timeout=httpx.Timeout(30.0),
    ) as client:
        r = await client.get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": capped, "sort": "created", "direction": "desc"},
        )
        r.raise_for_status()
        data = r.json()
    if isinstance(data, list):
        return data
    return []


async def _fetch_head_sha(pr_number: int) -> str:
    """One-shot head SHA fetch; returns empty string on failure (non-fatal)."""
    try:
        owner, repo = _repo_parts_from_settings()
    except ValueError:
        return ""
    headers = {
        "Authorization": f"token {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=httpx.Timeout(15.0),
        ) as client:
            r = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
            if r.status_code != 200:
                return ""
            data = r.json()
    except (httpx.RequestError, ValueError):
        return ""
    return str(((data or {}).get("head") or {}).get("sha") or "")


async def _has_review_at_sha(
    db: AsyncSession,
    *,
    org_id: str,
    pr_number: int,
    head_sha: str,
) -> bool:
    """True if an episode exists for this PR+SHA with source 'brain:pr-review:*'."""
    if not head_sha:
        return False
    stmt = (
        select(func.count(Episode.id))
        .where(
            and_(
                Episode.organization_id == org_id,
                Episode.source_ref == str(pr_number),
                Episode.source.like("brain:pr-review:%"),
                Episode.metadata_["head_sha"].astext == head_sha,
            )
        )
    )
    try:
        result = await db.execute(stmt)
        count = int(result.scalar() or 0)
        return count > 0
    except Exception as e:
        logger.warning("_has_review_at_sha query failed (treating as unreviewed): %s", e)
        return False


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
