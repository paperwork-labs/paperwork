#!/usr/bin/env python3
"""Dependabot major-version triage — calls Anthropic Claude Haiku.

Invoked by ``.github/workflows/dependabot-major-triage.yaml``.

Inputs (environment):
  ANTHROPIC_API_KEY  — required. If missing, writes a stub JSON and exits 0
                       (workflow still posts a graceful "secret missing"
                       comment rather than failing hard).
  ECOSYSTEM          — npm | pip | github_actions | ...
  DEPS               — space-separated dependency names
  PREV, NEW          — previous and new version strings

Inputs (files via CLI):
  --diff   path to truncated PR diff (bounded by caller, e.g. head -n 200)
  --usages path to usage grep results (one line per dep)
  --out    path to write the resulting JSON to

Output:
  A JSON object, written to --out, matching the schema described in the
  workflow comment. If the model returns malformed JSON we wrap it in an
  "unknown"/"review" fallback so the downstream jq pipeline never breaks.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 800
API_URL = "https://api.anthropic.com/v1/messages"

PROMPT_TEMPLATE = """\
You are a dependency-upgrade risk assessor for the Paperwork Labs monorepo.

Bump details:
  ecosystem: {ecosystem}
  packages:  {deps}
  version:   {prev}  ->  {new}

Usage in our codebase (approximate import-site counts):
{usages}

Truncated PR diff (first ~200 lines):
```diff
{diff}
```

Return ONLY a JSON object, no prose, matching exactly this schema:
{{
  "risk": "low" | "medium" | "high",
  "summary": "one-line plain-English summary of the breaking changes in this major version (<=160 chars)",
  "breaking_changes": ["bullet of known breaking changes from the package's major release"],
  "affected_paths": ["brief note about which parts of our repo likely need attention, or 'none — interface unchanged'"],
  "recommendation": "merge" | "review" | "hold",
  "confidence": "low" | "medium" | "high"
}}

Guidance:
- If the diff is only a lockfile/manifest version bump AND usage is <=3 sites of stable APIs, risk=low, recommendation=merge.
- Packages known for breaking-heavy majors (zod, framer-motion, pillow, google-cloud-*, eslint, typescript, vite, vitest) lean higher.
- confidence=low if you don't recognize the package.
"""


def _fallback(reason: str, **extra: str) -> dict:
    return {
        "risk": "unknown",
        "summary": reason,
        "breaking_changes": [],
        "affected_paths": [],
        "recommendation": "review",
        "confidence": "low",
        **extra,
    }


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # Drop first fence (``` or ```json) and trailing fence if present.
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        if t.endswith("```"):
            t = t[:-3]
    return t.strip()


def call_haiku(prompt: str, api_key: str) -> dict:
    payload = json.dumps(
        {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return _fallback(
            f"LLM HTTP {e.code}",
            raw=e.read().decode("utf-8", errors="replace")[:400],
        )
    except Exception as e:  # noqa: BLE001 — surface any transport error
        return _fallback(f"LLM transport error: {type(e).__name__}: {e}")

    try:
        text = body["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return _fallback("LLM response missing content[0].text", raw=json.dumps(body)[:400])

    cleaned = _strip_fences(text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return _fallback("LLM returned malformed JSON", raw=cleaned[:400])

    if not isinstance(parsed, dict):
        return _fallback("LLM returned non-object JSON", raw=cleaned[:400])

    return parsed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diff", required=True)
    ap.add_argument("--usages", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        result = _fallback(
            "ANTHROPIC_API_KEY secret not configured; configure it to enable automated triage"
        )
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2)
        return 0

    try:
        diff = open(args.diff).read()
    except OSError:
        diff = "(no diff available)"
    try:
        usages = open(args.usages).read() or "(no usage sites found)"
    except OSError:
        usages = "(no usage sites found)"

    prompt = PROMPT_TEMPLATE.format(
        ecosystem=os.environ.get("ECOSYSTEM", "?"),
        deps=os.environ.get("DEPS", "?"),
        prev=os.environ.get("PREV", "?"),
        new=os.environ.get("NEW", "?"),
        usages=usages.strip() or "(no usage sites found)",
        diff=diff.strip() or "(diff empty)",
    )

    result = call_haiku(prompt, api_key)

    with open(args.out, "w") as f:
        json.dump(result, f, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
