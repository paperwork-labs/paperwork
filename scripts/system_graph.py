#!/usr/bin/env python3
"""Generate the paperwork system graph — the single source of truth behind
Studio's /admin/architecture command-center DAG.

Output:
    apps/studio/src/data/system-graph.json

Contents:
    {
      "generated_at": "...",
      "commit_sha": "...",
      "nodes": [
        { id, label, product, layer, kind, module_path, github_url,
          health_url?, admin_url?, docs_url?, depends_on: [...],
          description, owner_persona?, llm_backed?: bool, severity?: str,
          medallion_summary?: { bronze: N, silver: N, gold: N, execution: N }
        },
        ...
      ]
    }

Design:
    - A curated NODES list in this file is the authoritative top-level graph.
      Editing it is a PR; Studio re-reads the JSON and the DAG changes.
    - The script validates every module_path against the working tree so a
      node cannot silently point at code that has moved.
    - For AxiomFolio it auto-counts medallion-tagged files per layer so
      the DAG shows "bronze: 14 / silver: 22 / gold: 9 / execution: 5"
      without needing to be hand-updated.
    - Zero runtime dependencies beyond the Python stdlib — CI friendly.

Usage:
    python scripts/system_graph.py
    python scripts/system_graph.py --check        # fail if output would change
    python scripts/system_graph.py --stdout       # print instead of write
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "apps" / "studio" / "src" / "data" / "system-graph.json"
GITHUB_REPO = "paperwork-labs/paperwork"
GITHUB_BLOB = f"https://github.com/{GITHUB_REPO}/blob/main"
GITHUB_TREE = f"https://github.com/{GITHUB_REPO}/tree/main"

# Authoritative node list. Columns in Studio lay out by `layer`.
# Every `module_path` is validated against the filesystem below.
#
# layer values:
#   bronze     : raw external data / provider clients
#   silver     : enriched / normalized domain data
#   gold       : decision-ready surfaces (scans, picks, features)
#   execution  : actions + orchestration (workers, schedulers, agents)
#   frontend   : customer UIs
#   platform   : developer platform (monitoring, secrets, docs)
#   infra      : managed services (postgres, redis, hosting)
#
# kind values: api | worker | frontend | agent | mcp | infra | workflow | platform
#
# Keep this list ordered roughly bronze -> silver -> gold -> execution -> frontend -> platform -> infra
# so Studio can render columns left to right.
NODES: list[dict] = [
    # -------- AxiomFolio (trading) --------
    {
        "id": "axiomfolio.bronze.market_data",
        "label": "Market Data Clients",
        "product": "axiomfolio",
        "layer": "bronze",
        "kind": "api",
        "module_path": "apis/axiomfolio/app/services/bronze",
        "description": "Raw provider clients: price, fundamentals, corporate actions.",
        "owner_persona": "market-data-guardian",
        "depends_on": [],
    },
    {
        "id": "axiomfolio.silver.features",
        "label": "Features + Indicators",
        "product": "axiomfolio",
        "layer": "silver",
        "kind": "api",
        "module_path": "apis/axiomfolio/app/services/silver",
        "description": "Stage analysis, indicators, point-in-time enrichments.",
        "owner_persona": "quant-analyst",
        "depends_on": ["axiomfolio.bronze.market_data"],
    },
    {
        "id": "axiomfolio.gold.picks",
        "label": "Picks + Portfolio",
        "product": "axiomfolio",
        "layer": "gold",
        "kind": "api",
        "module_path": "apis/axiomfolio/app/services/gold",
        "description": "Decision surfaces: scanner output, shadow trades, portfolio views.",
        "owner_persona": "portfolio-manager",
        "depends_on": ["axiomfolio.silver.features"],
    },
    {
        "id": "axiomfolio.execution.orders",
        "label": "Execution + Risk",
        "product": "axiomfolio",
        "layer": "execution",
        "kind": "worker",
        "module_path": "apis/axiomfolio/app/services/execution",
        "description": "Order routing, risk gate, circuit breakers.",
        "owner_persona": "risk-manager",
        "depends_on": ["axiomfolio.gold.picks"],
    },
    {
        "id": "axiomfolio.api",
        "label": "AxiomFolio API",
        "product": "axiomfolio",
        "layer": "execution",
        "kind": "api",
        "module_path": "apis/axiomfolio",
        "health_url": "https://api.axiomfolio.com/health",
        "admin_url": "https://axiomfolio.paperworklabs.com/settings/admin/system",
        "description": "FastAPI surface for the trading platform (web + workers).",
        "owner_persona": "trading",
        "depends_on": [
            "axiomfolio.gold.picks",
            "axiomfolio.silver.features",
            "axiomfolio.bronze.market_data",
        ],
    },
    {
        "id": "axiomfolio.frontend",
        "label": "AxiomFolio Web",
        "product": "axiomfolio",
        "layer": "frontend",
        "kind": "frontend",
        "module_path": "apps/axiomfolio",
        "health_url": "https://axiomfolio.paperworklabs.com",
        "admin_url": "https://axiomfolio.paperworklabs.com/settings/admin/system",
        "description": "Trading UI — React 19 + Vite 8. Pending migration to Next.js.",
        "owner_persona": "ux",
        "depends_on": ["axiomfolio.api"],
    },

    # -------- FileFree (tax filing) --------
    {
        "id": "filefree.api",
        "label": "FileFree API",
        "product": "filefree",
        "layer": "execution",
        "kind": "api",
        "module_path": "apis/filefree",
        "health_url": "https://api.filefree.ai/health",
        "description": "Tax filing backend — MeF, 1099/W-2 ingest, IRS schemas.",
        "owner_persona": "cpa",
        "depends_on": [],
    },
    {
        "id": "filefree.frontend",
        "label": "FileFree Web",
        "product": "filefree",
        "layer": "frontend",
        "kind": "frontend",
        "module_path": "apps/filefree",
        "health_url": "https://filefree.ai",
        "description": "Free AI tax filing — Next.js 16 on Vercel.",
        "owner_persona": "ux",
        "depends_on": ["filefree.api"],
    },

    # -------- LaunchFree (business formation) --------
    {
        "id": "launchfree.api",
        "label": "LaunchFree API",
        "product": "launchfree",
        "layer": "execution",
        "kind": "api",
        "module_path": "apis/launchfree",
        "description": "Business formation backend — registered agent, state filings.",
        "owner_persona": "legal",
        "depends_on": [],
    },
    {
        "id": "launchfree.frontend",
        "label": "LaunchFree Web",
        "product": "launchfree",
        "layer": "frontend",
        "kind": "frontend",
        "module_path": "apps/launchfree",
        "health_url": "https://launchfree.ai",
        "description": "Business formation UI — Next.js 16 on Vercel.",
        "owner_persona": "ux",
        "depends_on": ["launchfree.api"],
    },

    # -------- Distill (B2B compliance) --------
    {
        "id": "distill.frontend",
        "label": "Distill Web",
        "product": "distill",
        "layer": "frontend",
        "kind": "frontend",
        "module_path": "apps/distill",
        "health_url": "https://distill.tax",
        "description": "B2B compliance automation — Next.js 16 on Vercel.",
        "owner_persona": "legal",
        "depends_on": [],
    },

    # -------- Trinkets (merch / misc) --------
    {
        "id": "trinkets.frontend",
        "label": "Trinkets Web",
        "product": "trinkets",
        "layer": "frontend",
        "kind": "frontend",
        "module_path": "apps/trinkets",
        "description": "Brand merch / misc — Next.js 16 on Vercel.",
        "owner_persona": "brand",
        "depends_on": [],
    },

    # -------- Brain (executive agent) --------
    {
        "id": "brain.api",
        "label": "Brain API",
        "product": "brain",
        "layer": "execution",
        "kind": "agent",
        "module_path": "apis/brain",
        "health_url": "https://brain-api-zo5t.onrender.com/health",
        "docs_url": f"{GITHUB_TREE}/apis/brain",
        "description": "Executive agent: chat, /process, PR review, memory, personas. MCP over SSE.",
        "owner_persona": "ea",
        "llm_backed": True,
        "depends_on": [],
    },
    {
        "id": "brain.mcp",
        "label": "Brain MCP Tools",
        "product": "brain",
        "layer": "execution",
        "kind": "mcp",
        "module_path": "apis/brain/app/mcp_server.py",
        "description": "32 MCP tools: GitHub, Render, Vercel, Neon, Upstash, n8n, memory, trading.",
        "owner_persona": "brain-skill-engineer",
        "llm_backed": True,
        "depends_on": ["brain.api"],
    },
    {
        "id": "brain.personas",
        "label": "Persona Library",
        "product": "brain",
        "layer": "execution",
        "kind": "agent",
        "module_path": ".cursor/rules",
        "description": "48 .mdc persona rule files: ea, cpa, qa, cfo, trading, growth, etc.",
        "owner_persona": "agent-ops",
        "llm_backed": True,
        "depends_on": ["brain.api"],
    },

    # -------- Studio (command center) --------
    {
        "id": "studio.frontend",
        "label": "Studio",
        "product": "studio",
        "layer": "platform",
        "kind": "platform",
        "module_path": "apps/studio",
        "health_url": "https://www.paperworklabs.com",
        "admin_url": "https://www.paperworklabs.com/admin",
        "description": "Command center — Next.js 16. This DAG lives here.",
        "owner_persona": "engineering",
        "depends_on": [
            "brain.api",
            "axiomfolio.api",
            "filefree.api",
        ],
    },

    # -------- Infra --------
    {
        "id": "infra.n8n",
        "label": "n8n",
        "product": "infra",
        "layer": "platform",
        "kind": "workflow",
        "module_path": "infra/hetzner/workflows",
        "health_url": "https://n8n.paperworklabs.com",
        "admin_url": "https://n8n.paperworklabs.com",
        "description": "Scheduler + shuttle. LLM calls being migrated to Brain personas.",
        "owner_persona": "workflows",
        "depends_on": ["brain.api"],
    },
    {
        "id": "infra.postgres",
        "label": "Postgres (Neon)",
        "product": "infra",
        "layer": "infra",
        "kind": "infra",
        "module_path": "apis/brain/app/models",
        "admin_url": "https://console.neon.tech",
        "description": "Primary data store — Brain, AxiomFolio, FileFree branches.",
        "owner_persona": "prod-database",
        "depends_on": [],
    },
    {
        "id": "infra.redis",
        "label": "Redis (Upstash)",
        "product": "infra",
        "layer": "infra",
        "kind": "infra",
        "module_path": "apis/brain/app/redis.py",
        "admin_url": "https://console.upstash.com",
        "description": "Cache + rate limit + Celery broker + persona fatigue tracking.",
        "owner_persona": "infra-ops",
        "depends_on": [],
    },
    {
        "id": "infra.vercel",
        "label": "Vercel",
        "product": "infra",
        "layer": "infra",
        "kind": "infra",
        "module_path": "apps",
        "admin_url": "https://vercel.com/paperwork-labs",
        "description": "Frontend hosting: Studio, FileFree, LaunchFree, Distill, Trinkets.",
        "owner_persona": "infra-ops",
        "depends_on": [],
    },
    {
        "id": "infra.render",
        "label": "Render",
        "product": "infra",
        "layer": "infra",
        "kind": "infra",
        "module_path": "apis",
        "admin_url": "https://dashboard.render.com",
        "description": "API + worker hosting: Brain, AxiomFolio, FileFree.",
        "owner_persona": "infra-ops",
        "depends_on": [],
    },
    {
        "id": "infra.github_actions",
        "label": "GitHub Actions",
        "product": "infra",
        "layer": "platform",
        "kind": "infra",
        "module_path": ".github/workflows",
        "admin_url": f"https://github.com/{GITHUB_REPO}/actions",
        "description": "CI + Dependabot auto-approve + LLM triage + auto-merge-sweep.",
        "owner_persona": "infra-ops",
        "depends_on": [],
    },
]

LAYERS = ["bronze", "silver", "gold", "execution", "frontend", "platform", "infra"]


MEDALLION_TAG_RE = re.compile(
    r"^\s*medallion:\s*(bronze|silver|gold|execution|ops)\s*$",
    re.MULTILINE,
)


def count_medallion_layers(root: Path) -> dict[str, int]:
    """Walk `root` and count medallion-tagged .py files by layer tag."""
    counts: dict[str, int] = {}
    if not root.is_dir():
        return counts
    for py in root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "medallion:" not in text:
            continue
        m = MEDALLION_TAG_RE.search(text)
        if not m:
            continue
        layer = m.group(1)
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_graph() -> dict:
    errors: list[str] = []
    enriched: list[dict] = []

    ids = {n["id"] for n in NODES}
    for node in NODES:
        path = REPO_ROOT / node["module_path"]
        if not path.exists():
            errors.append(
                f"node {node['id']} module_path does not exist: {node['module_path']}"
            )
            continue

        for layer_check in ("layer",):
            if node[layer_check] not in LAYERS:
                errors.append(
                    f"node {node['id']} has invalid {layer_check}={node[layer_check]!r}"
                )

        for dep in node.get("depends_on", []):
            if dep not in ids:
                errors.append(
                    f"node {node['id']} depends_on unknown id: {dep}"
                )

        github_url = (
            f"{GITHUB_TREE}/{node['module_path']}"
            if path.is_dir()
            else f"{GITHUB_BLOB}/{node['module_path']}"
        )

        out = {
            **node,
            "github_url": github_url,
        }

        if node["product"] == "axiomfolio" and node["layer"] in {
            "bronze",
            "silver",
            "gold",
            "execution",
        }:
            counts = count_medallion_layers(path)
            if counts:
                out["medallion_summary"] = counts

        enriched.append(out)

    if errors:
        print("system_graph: validation errors", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(2)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_sha": git_sha(),
        "layers": LAYERS,
        "nodes": enriched,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the generated JSON differs from the current file.",
    )
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="Print JSON to stdout instead of writing to disk.",
    )
    args = ap.parse_args()

    graph = build_graph()
    rendered = json.dumps(graph, indent=2, sort_keys=False) + "\n"

    if args.stdout:
        sys.stdout.write(rendered)
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.check:
        if not OUTPUT_PATH.exists():
            print(f"{OUTPUT_PATH} missing — run: python scripts/system_graph.py")
            return 1
        current = OUTPUT_PATH.read_text()
        # `generated_at` and `commit_sha` change every run; compare the structural
        # payload (nodes + layers) by ignoring both. Otherwise CI would fail any
        # PR that doesn't also regenerate the snapshot — a bandaid that turns
        # every single PR into a two-step ritual.
        def _strip(text: str) -> str:
            text = re.sub(r'"generated_at":\s*"[^"]*",?\s*', "", text)
            text = re.sub(r'"commit_sha":\s*"[^"]*",?\s*', "", text)
            return text
        if _strip(current) != _strip(rendered):
            print(
                f"{OUTPUT_PATH} is stale — run: python scripts/system_graph.py",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT_PATH} is up to date ({len(graph['nodes'])} nodes).")
        return 0

    OUTPUT_PATH.write_text(rendered)
    print(
        f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} "
        f"({len(graph['nodes'])} nodes, commit {graph['commit_sha']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
