#!/usr/bin/env python3
"""Claude Haiku triage for major Dependabot PRs.

Called by .github/workflows/dependabot-major-triage.yaml. Two modes:

  # Mode 1: produce structured triage JSON from PR metadata + diff.
  python3 dependabot_triage.py --pr-meta /tmp/pr.json --pr-diff /tmp/pr.diff --out /tmp/triage.json

  # Mode 2: render the triage JSON as a PR comment (markdown on stdout).
  python3 dependabot_triage.py --render-comment /tmp/triage.json

The two modes are combined in one script so the workflow doesn't need to
ship two Python files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("DEPENDABOT_TRIAGE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT = """You are a senior engineer triaging a major-version dependency bump in a
Python + TypeScript monorepo at Paperwork Labs.

You receive:
- PR metadata (title, body, changed files, additions/deletions, current labels).
- The raw diff (capped at 40k chars). For Dependabot bumps this is usually small:
  lockfile + pyproject.toml / package.json edits.

Decide a risk tier and list the breaking-change classes the maintainers flagged
that actually matter for this repo. Output STRICT JSON only — no markdown fences,
no preamble.

{
  "risk": "low" | "medium" | "high",
  "bump": "e.g. zod 3.25 → 4.3",
  "ecosystem": "npm" | "pip" | "github-actions" | "other",
  "summary": "one sentence you'd say in standup",
  "breaking_changes_that_matter": ["concrete item 1", ...],
  "breaking_changes_we_can_ignore": ["reason 1", ...],
  "affected_paths": ["apis/axiomfolio/app/...", ...],
  "recommendation": "merge" | "merge-with-caution" | "hold-for-human"
}

Risk tiering (strict):
- "low":   type-safe upgrade, deprecated APIs we don't call, no runtime behavior change.
- "medium": semantic changes in APIs this repo uses; needs a smoke test or quick manual sweep.
- "high":  breaks an API used widely, requires code changes across multiple files, or
          the dependency is in a security-critical path (auth, crypto, broker SDK, billing).

Keep your response under ~500 tokens. Be honest — do not hedge."""


def call_haiku(meta: dict[str, Any], diff: str) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {
            "risk": "medium",
            "summary": "ANTHROPIC_API_KEY not set in workflow env — skipping LLM triage.",
            "recommendation": "hold-for-human",
        }

    user_payload = {
        "pr_title": meta.get("title", ""),
        "pr_body": (meta.get("body") or "")[:8000],
        "labels": [lbl.get("name") for lbl in (meta.get("labels") or []) if isinstance(lbl, dict)],
        "additions": meta.get("additions"),
        "deletions": meta.get("deletions"),
        "changed_files": meta.get("changedFiles"),
    }

    user_text = (
        "## PR metadata\n```json\n"
        + json.dumps(user_payload, indent=2, default=str)
        + "\n```\n\n## Diff\n```diff\n"
        + diff
        + "\n```\n\nReturn the strict JSON schema from the system prompt."
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": MODEL,
        "max_tokens": 1200,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_text}],
    }

    try:
        with httpx.Client(timeout=90.0) as client:
            r = client.post(ANTHROPIC_URL, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        return {
            "risk": "medium",
            "summary": f"Anthropic call failed: {e}",
            "recommendation": "hold-for-human",
        }

    blocks = data.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()

    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return {
            "risk": "medium",
            "summary": f"Haiku returned non-JSON (likely a refusal or truncation): {e}",
            "raw": text[:1000],
            "recommendation": "hold-for-human",
        }

    if isinstance(parsed, dict):
        risk = str(parsed.get("risk", "medium")).lower()
        if risk not in ("low", "medium", "high"):
            parsed["risk"] = "medium"
        return parsed

    return {
        "risk": "medium",
        "summary": "Unexpected response shape",
        "raw": text[:1000],
        "recommendation": "hold-for-human",
    }


def render_comment(triage: dict[str, Any]) -> str:
    risk = str(triage.get("risk", "medium")).lower()
    bump = triage.get("bump") or ""
    eco = triage.get("ecosystem") or ""
    summary = triage.get("summary") or ""
    bcm = triage.get("breaking_changes_that_matter") or []
    bci = triage.get("breaking_changes_we_can_ignore") or []
    paths = triage.get("affected_paths") or []
    rec = triage.get("recommendation") or ""

    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "🟡")

    lines: list[str] = []
    lines.append(f"### {risk_emoji} Dependabot major-bump triage")
    lines.append("")
    if bump:
        lines.append(f"**Bump**: `{bump}` ({eco})")
    lines.append(f"**Risk**: `{risk}`  · **Recommendation**: `{rec or '—'}`")
    lines.append("")
    if summary:
        lines.append(summary)
        lines.append("")
    if bcm:
        lines.append("**Breaking changes that matter for this repo**")
        for x in bcm[:10]:
            lines.append(f"- {str(x)[:400]}")
        lines.append("")
    if bci:
        lines.append("**Breaking changes we can ignore**")
        for x in bci[:10]:
            lines.append(f"- {str(x)[:400]}")
        lines.append("")
    if paths:
        lines.append("**Likely affected paths**")
        for p in paths[:10]:
            lines.append(f"- `{str(p)[:200]}`")
        lines.append("")
    lines.append(f"<sub>model: `{MODEL}` · posted by .github/workflows/dependabot-major-triage.yaml</sub>")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr-meta", help="path to PR metadata JSON (from `gh pr view --json`)")
    ap.add_argument("--pr-diff", help="path to PR diff file")
    ap.add_argument("--out", help="path to write triage JSON")
    ap.add_argument(
        "--render-comment",
        help="path to existing triage JSON; emits markdown comment on stdout",
    )
    args = ap.parse_args()

    if args.render_comment:
        with open(args.render_comment) as f:
            triage = json.load(f)
        sys.stdout.write(render_comment(triage))
        return 0

    if not args.pr_meta or not args.pr_diff or not args.out:
        ap.error("--pr-meta, --pr-diff, --out are required (unless --render-comment is used)")

    with open(args.pr_meta) as f:
        meta = json.load(f)
    with open(args.pr_diff) as f:
        diff = f.read()

    triage = call_haiku(meta, diff)
    with open(args.out, "w") as f:
        json.dump(triage, f, indent=2)
    print(f"Wrote triage to {args.out} (risk={triage.get('risk')})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
