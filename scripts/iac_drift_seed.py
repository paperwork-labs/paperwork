#!/usr/bin/env python3
"""Seed canonical IaC state from live provider state."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apis" / "brain"))

from app.schemas.iac_state import VercelStateFile  # noqa: E402
from app.services.iac_drift import VercelEnvSurface  # noqa: E402


def _seed_vercel() -> None:
    state_path = REPO_ROOT / "infra" / "state" / "vercel.yaml"
    live = VercelEnvSurface(state_path=state_path).fetch_live()
    payload: dict[str, Any] = {
        "schema": {
            "description": (
                "Canonical Vercel project envs/config. Drift detector reconciles this vs "
                "live API state every 30 min."
            )
        },
        "version": 1,
        "projects": live.get("projects", []),
        "last_reconciled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    VercelStateFile.model_validate(payload)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    print(f"seeded Vercel canonical state: {state_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("surface", choices=["vercel", "cloudflare", "render", "clerk"])
    args = parser.parse_args()

    if args.surface != "vercel":
        print("TODO: WS-42 follow-up — implement after Vercel")
        return 0

    _seed_vercel()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
