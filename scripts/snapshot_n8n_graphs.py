#!/usr/bin/env python3
"""Buffer Week 4 — snapshot n8n workflow graphs for Studio's Graph tab.

The /admin/workflows?tab=graph view needs trigger → action DAGs to
render. Rather than make Studio hit n8n on every request (adds latency,
leaks credentials to the browser), we snapshot the graph structure at
build time and ship the JSON as a static asset.

Source: ``infra/hetzner/workflows/*.json`` (the checked-in n8n exports
are the canonical workflow definitions, so this works even before a
live n8n instance exists in dev).

Output: ``apps/studio/src/data/n8n-graph.json``. CI job `snapshot-n8n`
in ``.github/workflows/brain-personas-doc.yaml`` runs this nightly and
commits changes.

Shape:

    {
        "generated_at": "2026-04-23T12:00:00Z",
        "workflows": [
            {
                "name": "CPA Tax Review",
                "file": "cpa-tax-review.json",
                "node_count": 2,
                "nodes": [
                    {"id": "webhook-cpa", "name": "Webhook", "type": "n8n-nodes-base.webhook", "x": 240, "y": 300},
                    ...
                ],
                "edges": [
                    {"from": "Webhook", "to": "Brain: persona=cpa"}
                ],
                "pattern": "webhook|schedule|manual",
                "calls_brain": true,
                "persona_pin": "cpa"
            },
            ...
        ]
    }

medallion: ops
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / "infra" / "hetzner" / "workflows"
OUT_PATH = REPO_ROOT / "apps" / "studio" / "src" / "data" / "n8n-graph.json"


BRAIN_URL_PATTERN = re.compile(
    r"BRAIN_API_URL.*brain/process|persona_pin", re.IGNORECASE
)
PERSONA_PIN_PATTERN = re.compile(
    r"persona_pin['\"]?\s*[:=]\s*['\"]([a-z0-9_-]+)['\"]",
    re.IGNORECASE,
)


def _classify_trigger(nodes: list[dict]) -> str:
    """Categorise the workflow's trigger to help Studio colour-code."""
    for n in nodes:
        t = str(n.get("type") or "")
        if "webhook" in t.lower():
            return "webhook"
        if "schedule" in t.lower() or "cron" in t.lower():
            return "schedule"
        if "manualtrigger" in t.lower() or "manual" in t.lower():
            return "manual"
    return "unknown"


def _extract_persona_pin(raw: str) -> str | None:
    """If the workflow calls Brain with persona_pin, extract the pin."""
    m = PERSONA_PIN_PATTERN.search(raw)
    if m:
        return m.group(1)
    return None


def _walk_connections(connections: dict) -> list[dict]:
    """n8n stores edges as ``{source: {main: [[{node, type, index}, ...]]}}``.

    Flatten to a simple ``[{from, to}]`` list, only preserving the main
    connection channel (no error/if-else variants — we just need the
    skeleton for a DAG preview).
    """
    edges: list[dict] = []
    for src, channels in (connections or {}).items():
        main = channels.get("main") if isinstance(channels, dict) else None
        if not isinstance(main, list):
            continue
        for lane in main:
            if not isinstance(lane, list):
                continue
            for conn in lane:
                if not isinstance(conn, dict):
                    continue
                tgt = conn.get("node")
                if tgt:
                    edges.append({"from": src, "to": tgt})
    return edges


def _summarise(file_path: Path) -> dict:
    raw_text = file_path.read_text()
    cfg = json.loads(raw_text)
    nodes_raw = cfg.get("nodes") or []
    nodes: list[dict] = []
    for n in nodes_raw:
        pos = n.get("position") or [0, 0]
        nodes.append(
            {
                "id": n.get("id") or n.get("name") or "?",
                "name": n.get("name") or n.get("id") or "?",
                "type": n.get("type") or "unknown",
                "x": pos[0] if isinstance(pos, list) and len(pos) >= 1 else 0,
                "y": pos[1] if isinstance(pos, list) and len(pos) >= 2 else 0,
            }
        )
    edges = _walk_connections(cfg.get("connections") or {})
    persona_pin = _extract_persona_pin(raw_text)
    return {
        "name": cfg.get("name") or file_path.stem,
        "file": file_path.name,
        "node_count": len(nodes),
        "nodes": nodes,
        "edges": edges,
        "pattern": _classify_trigger(nodes_raw),
        "calls_brain": bool(BRAIN_URL_PATTERN.search(raw_text)),
        "persona_pin": persona_pin,
    }


def main() -> int:
    if not WORKFLOWS_DIR.is_dir():
        print(f"Workflows dir not found: {WORKFLOWS_DIR}")
        return 1
    workflows: list[dict] = []
    for f in sorted(WORKFLOWS_DIR.glob("*.json")):
        try:
            workflows.append(_summarise(f))
        except Exception as exc:
            print(f"skip {f.name}: {exc}")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "infra/hetzner/workflows/*.json",
        "workflows": workflows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"Wrote {OUT_PATH.relative_to(REPO_ROOT)} — "
        f"{len(workflows)} workflows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
