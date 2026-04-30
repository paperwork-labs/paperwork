"""Public Brain routes for WS-67.E auto-distillation (staged procedural rules).

medallion: ops
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.schemas.base import success_response
from app.services.auto_distillation import load_proposed_rules, run_distillation

router = APIRouter(prefix="/audits/auto-distillation", tags=["auto-distillation"])


@router.post("/run")
def run_audit() -> Any:
    """Execute distillation over pr_outcomes + agent_dispatch_log; stage YAML proposals."""
    _written, proposals = run_distillation()
    return success_response(
        {
            "proposed_rules_count": len(proposals),
            "newly_staged_count": _written,
        }
    )


@router.get("/proposed")
def list_proposed_rules() -> Any:
    """Return the current contents of ``proposed_rules.yaml``."""
    memory = load_proposed_rules()
    rules_json = [r.model_dump(mode="json") for r in memory.rules]
    return success_response({"version": memory.version, "rules": rules_json})
