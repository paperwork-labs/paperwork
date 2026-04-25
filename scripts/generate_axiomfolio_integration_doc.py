#!/usr/bin/env python3
"""Track M.4 — regenerate docs/AXIOMFOLIO_INTEGRATION.generated.md.

Two docs have been drifting from code for weeks:

  * ``docs/AXIOMFOLIO_INTEGRATION.md`` — opens with "AxiomFolio stays as
    a separate repo," which has been false since the monorepo migration.
  * ``docs/AXIOMFOLIO_HANDOFF.md`` — has wrong endpoint paths
    (``/approve`` vs actual ``/approve-trade``) and wrong tier numbers
    (1/2/3 vs actual 0/2/3).

Track K says: stop hand-maintaining things that already have a machine-
readable source of truth. Track M.4 applies that rule here.

Source of truth: ``docs/axiomfolio/brain/axiomfolio_tools.yaml``.
CI: ``.github/workflows/brain-personas-doc.yaml`` runs this with
``--check`` on PR and fails on drift.

medallion: ops
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = REPO_ROOT / "docs" / "axiomfolio" / "brain" / "axiomfolio_tools.yaml"
DOC_PATH = REPO_ROOT / "docs" / "AXIOMFOLIO_INTEGRATION.generated.md"


TIER_EXPLANATIONS = {
    0: "**Read-only.** No approval gate; tool runs immediately.",
    2: (
        "**State-changing.** Requires agent autonomy level ≥ ``safe`` "
        "in AxiomFolio and enters the approval queue when autonomy is "
        "``ask``."
    ),
    3: (
        "**Execution / financial.** Always enters the approval queue "
        "regardless of autonomy level. Owner-only approval routes "
        "available via the ``approve_trade`` / ``reject_trade`` tools."
    ),
}


def _load() -> dict:
    with YAML_PATH.open() as fh:
        return yaml.safe_load(fh)


def _render_tool_row(t: dict) -> str:
    name = t.get("name", "?")
    method = t.get("method", "?")
    path = t.get("path", "?")
    tier = t.get("tier", "?")
    timeout = t.get("timeout_seconds", "?")
    desc = (t.get("description") or "").strip()
    return (
        f"| `{name}` | `{method}` | `{path}` | {tier} | {timeout}s | {desc} |"
    )


def _render_webhook_row(e: dict) -> str:
    name = e.get("name", "?")
    desc = (e.get("description") or "").strip()
    return f"| `{name}` | {desc} |"


def _render_doc(cfg: dict) -> str:
    tools = cfg.get("tools") or []
    webhook_cfg = cfg.get("webhook_events") or {}
    events = webhook_cfg.get("events") or []

    tier_counts: dict[int, int] = {}
    for t in tools:
        tier = t.get("tier")
        if isinstance(tier, int):
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
    tier_summary = ", ".join(
        f"Tier {k}: {v}" for k, v in sorted(tier_counts.items())
    )

    lines: list[str] = [
        "<!-- GENERATED — do not edit by hand.",
        "     Source: docs/axiomfolio/brain/axiomfolio_tools.yaml",
        "     Regen:  python scripts/generate_axiomfolio_integration_doc.py",
        "     CI:     .github/workflows/brain-personas-doc.yaml -->",
        "",
        "# AxiomFolio ↔ Paperwork Brain integration",
        "",
        (
            "> This file is auto-generated. The hand-written predecessors "
            "(`AXIOMFOLIO_INTEGRATION.md`, `AXIOMFOLIO_HANDOFF.md`) were "
            "removed as part of Track M.4 after they fell out of sync "
            "with code. Everything authoritative now lives in the YAML "
            "source and the webhook router."
        ),
        "",
        "## Overview",
        "",
        "Two directions, one contract:",
        "",
        (
            "* **Brain → AxiomFolio (tools)** — Paperwork Brain calls "
            f"{len(tools)} HTTP tools on AxiomFolio ({tier_summary}). "
            "These back the `trading` persona's tool-calling loop and "
            "also power the user-facing MCP surface for self-directed "
            "investors via Claude Desktop."
        ),
        (
            "* **AxiomFolio → Brain (webhooks)** — AxiomFolio posts "
            f"{len(events)} event types to Brain's webhook receiver. "
            "High-importance events (`risk.gate.activated`, "
            "`approval.required`, `stop.triggered`) wake the `trading` "
            "persona and post a narrated explanation to `#trading` "
            "(Track M.2)."
        ),
        "",
        "## Authentication",
        "",
        (
            "**Brain → AxiomFolio:** API key in "
            f"`{webhook_cfg.get('auth', {}).get('header') or cfg.get('auth', {}).get('header') or 'X-Brain-Api-Key'}`, "
            "value from `AXIOMFOLIO_API_KEY` env var on the Brain side. "
            "All `/api/v1/tools/*` routes require this header."
        ),
        "",
        (
            "**AxiomFolio → Brain:** HMAC-SHA256 of the raw body, sent as "
            "`X-Webhook-Signature: sha256=<hex>`. Shared secret in "
            "`BRAIN_WEBHOOK_SECRET` on AxiomFolio and "
            "`AXIOMFOLIO_WEBHOOK_SECRET` on Brain."
        ),
        "",
        "## Brain → AxiomFolio tool catalog",
        "",
        "| Tool | Method | Path | Tier | Timeout | Description |",
        "|---|---|---|---|---|---|",
        *[_render_tool_row(t) for t in tools],
        "",
        "### Tier meaning",
        "",
    ]
    for tier in sorted(tier_counts):
        lines.append(f"* **Tier {tier}** — {TIER_EXPLANATIONS.get(tier, '')}")
    lines.extend(
        [
            "",
            "## AxiomFolio → Brain webhook events",
            "",
            "| Event | Description |",
            "|---|---|",
            *[_render_webhook_row(e) for e in events],
            "",
            "### Events that wake the trading persona",
            "",
            (
                "The following events trigger a `#trading` Slack post narrated "
                "by the `trading` persona (default model: "
                "`claude-sonnet-4`). All others land as memory rows only."
            ),
            "",
            "* `risk.gate.activated` / `risk.alert`",
            "* `approval.required` / `approval.needed`",
            "* `stop.triggered`",
            "",
            (
                "See `apis/brain/app/routers/webhooks.py::_TRADING_WAKEUP_EVENTS` "
                "for the live list."
            ),
            "",
            "## LLM delegation (Track M.1)",
            "",
            (
                "When `AXIOMFOLIO_USE_PAPERWORK_BRAIN=True` and no BYOK key "
                "is configured for the caller, AxiomFolio's TradingAgent "
                "delegates its LLM turn to Paperwork Brain "
                "(`POST /brain/process?persona_pin=trading`) instead of "
                "calling OpenAI directly. Benefits:"
            ),
            "",
            (
                "* Single cost ledger — cost attributed to the `trading` "
                "persona ceiling."
            ),
            (
                "* Persona tone, rate limits, PII scrubbing, and episode "
                "memory all apply."
            ),
            "* Brain's router picks the model (Sonnet, not gpt-4o-mini).",
            "",
            "## BYOK surface (do not consolidate)",
            "",
            (
                "Paid-tier self-directed investors can set their own "
                "OpenAI/Anthropic key via "
                "`users.llm_provider_key_encrypted`. When a user has a "
                "valid BYOK key **and** their subscription tier is ≥ PRO, "
                "TradingAgent calls their provider directly — Brain is "
                "bypassed entirely. This path exists for privacy and "
                "quota isolation and must remain separate from the "
                "delegation shim."
            ),
            "",
            (
                "See `apis/axiomfolio/app/services/agent/brain.py::TradingAgent."
                "_resolve_llm_target` for the resolution logic."
            ),
            "",
            "## User-facing MCP surface (do not consolidate)",
            "",
            (
                "`apis/axiomfolio/app/api/routes/mcp.py` exposes JSON-RPC "
                "at `/api/v1/mcp/jsonrpc` for self-directed investors to "
                "point Claude Desktop and similar clients at their own "
                "AxiomFolio account. This is a separate product surface — "
                "not part of the two-brain delegation flow — and must "
                "keep working unchanged."
            ),
            "",
            "## Provenance stamps",
            "",
            (
                "Every AxiomFolio `agent_actions` row that results from a "
                "delegated Brain turn is stamped with "
                "`metadata.brain_episode_uri = brain://episode/<id>`, "
                "tying the tool call back to the Brain exchange that "
                "produced it. Audit trails stay end-to-end even as the "
                "LLM step moves between products."
            ),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    cfg = _load()
    generated = _render_doc(cfg)
    current = DOC_PATH.read_text() if DOC_PATH.exists() else ""

    if args.check:
        if current == generated:
            print(f"OK: {DOC_PATH.relative_to(REPO_ROOT)} is up to date.")
            return 0
        diff = difflib.unified_diff(
            current.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile=str(DOC_PATH.relative_to(REPO_ROOT)) + " (on disk)",
            tofile=str(DOC_PATH.relative_to(REPO_ROOT)) + " (expected)",
            n=3,
        )
        sys.stdout.writelines(diff)
        print(
            "\nERROR: stale. Run:\n  python scripts/generate_axiomfolio_integration_doc.py",
            file=sys.stderr,
        )
        return 1

    DOC_PATH.write_text(generated)
    tool_count = len(cfg.get("tools") or [])
    event_count = len((cfg.get("webhook_events") or {}).get("events") or [])
    print(
        f"Updated: {DOC_PATH.relative_to(REPO_ROOT)} "
        f"({tool_count} tools, {event_count} events)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
